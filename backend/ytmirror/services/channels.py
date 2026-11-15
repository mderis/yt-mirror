"""Channels: look one up, add it, pause it, remove it, open its folder.

Implements R-CH-01 to R-CH-06 and R-CH-30 to R-CH-32 for milestone M2.
Changing the settings of a channel and moving its folder arrive in M7,
and the choice to move files to the Trash when removing arrives in M3.

Tests: backend/tests/unit/services/test_channels.py
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

import structlog
from structlog.typing import FilteringBoundLogger

from ytmirror.core.channel_file import CHANNEL_FILE, channel_file_with, channel_file_without
from ytmirror.core.channel_input import parse_channel_input
from ytmirror.core.channels import (
    Channel,
    ChannelFacts,
    ChannelView,
    CheckKind,
    CheckTrigger,
    Quality,
    ReferenceKind,
)
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.naming import HIDDEN_DIR, TEMP_DIR, channel_folder_name
from ytmirror.ports.catalogue_repository import CatalogueRepository
from ytmirror.ports.clock import Clock
from ytmirror.ports.file_system import FileSystem
from ytmirror.ports.folder_picker import FolderPicker
from ytmirror.services.catalogue import CatalogueService
from ytmirror.services.channel_views import ChannelViews
from ytmirror.services.settings import SettingsService
from ytmirror.services.thumbnails import ThumbnailService
from ytmirror.services.youtube_access import YouTubeAccess

_log: FilteringBoundLogger = structlog.get_logger(__name__)

COUNT_TIME_LIMIT_S = 8.0
"""How long the video count of a preview may take before the preview goes without (R-CH-03)."""

MOST_PLAUSIBLE_VIDEOS = 1_000_000
"""A count above this is not believed."""


@dataclass(frozen=True, slots=True)
class FilesToTrash:
    """What "Delete the files" moves to the Trash when a channel is removed (R-CH-32).

    Attributes:
        paths: The files and the hidden folder, in the order they are moved.
        files: How many visible files: videos and their thumbnails.
        size_bytes: How much room they take, the hidden folder included.
    """

    paths: tuple[Path, ...]
    files: int
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ChannelLookup:
    """What the add channel dialog shows before the user confirms (R-CH-03 to R-CH-06).

    Attributes:
        facts: The channel as YouTube describes it.
        existing: Whether this channel was added before (R-CH-04).
        folder: The folder the channel gets when the user chooses none (R-CH-05).
        video_files: How many video files that folder already contains (R-CH-06).
    """

    facts: ChannelFacts
    existing: bool
    folder: str
    video_files: int


@dataclass(frozen=True, slots=True)
class ChosenFolder:
    """A folder the user chose in the dialog of macOS (R-CH-05, R-CH-06).

    Attributes:
        folder: The folder.
        video_files: How many video files it already contains.
    """

    folder: str
    video_files: int


@dataclass(frozen=True, slots=True)
class NewChannel:
    """What the user chose in step 2 of the add channel dialog (R-CH-05).

    Attributes:
        channel_id: The channel that was looked up.
        folder: A folder the user chose in the dialog, or None for the default.
        quality: The quality of this channel, or None for "use default".
        auto_mirror: Whether everything is mirrored automatically.
        mirror_after: Auto-mirror only videos uploaded after this time, or None.
    """

    channel_id: str
    folder: str | None = None
    quality: Quality | None = None
    auto_mirror: bool = False
    mirror_after: int | None = None


@dataclass(frozen=True, slots=True)
class AddedChannel:
    """The answer to adding a channel.

    Attributes:
        view: The channel as it is now.
        existing: True when the channel was there already and nothing was added (R-CH-04).
    """

    view: ChannelView
    existing: bool


class _Count:
    """The video count of one preview, which arrives in the background."""

    def __init__(self, started: float) -> None:
        self.started = started
        self.done = threading.Event()
        self.value: int | None = None


class ChannelsService:
    """The use cases around one channel."""

    def __init__(
        self,
        repository: CatalogueRepository,
        youtube: YouTubeAccess,
        files: FileSystem,
        picker: FolderPicker,
        settings: SettingsService,
        views: ChannelViews,
        catalogue: CatalogueService,
        thumbnails: ThumbnailService,
        clock: Clock,
        run_in_background: Callable[[Callable[[], None]], None],
        cancel_downloads: Callable[[str], None] = lambda _channel_id: None,
    ) -> None:
        """Create the service.

        Args:
            repository: The stored channels and videos.
            youtube: The access to YouTube.
            files: Folders on this Mac.
            picker: The folder dialog of macOS.
            settings: The general settings, for the library folder.
            views: Publishes how a channel is now.
            catalogue: Runs the checks.
            thumbnails: Caches the pictures.
            clock: The source of time.
            run_in_background: Runs the request for a video count without blocking.
            cancel_downloads: Cancels the downloads of a channel and waits for them
                to end, before the channel is removed.
        """
        self._repository = repository
        self._youtube = youtube
        self._files = files
        self._picker = picker
        self._cancel_downloads = cancel_downloads
        self._settings = settings
        self._views = views
        self._catalogue = catalogue
        self._thumbnails = thumbnails
        self._clock = clock
        self._run_in_background = run_in_background
        self._lock = threading.Lock()
        self._looked_up: dict[str, ChannelFacts] = {}
        self._counts: dict[str, _Count] = {}
        self._preview_avatars: dict[str, bytes] = {}
        self._chosen: set[str] = set()

    def lookup(self, text: str) -> ChannelLookup:
        """Look up the channel the user named, for the preview of the dialog (R-CH-03).

        The video count is not part of the answer: it is asked for at the
        same time and fetched with ``video_count``, so it never delays the
        preview.

        Args:
            text: What the user pasted or typed.

        Raises:
            AppError: ``INVALID_CHANNEL_INPUT`` (R-CH-02), ``CHANNEL_NOT_FOUND``, or
                the code of a request that failed.
        """
        reference = parse_channel_input(text)
        if reference.kind is ReferenceKind.CHANNEL_ID:
            self._start_count(reference.value)
        facts = self._youtube.lookup_channel(reference)
        self._start_count(facts.channel_id)
        with self._lock:
            self._looked_up[facts.channel_id] = facts
        folder = self._default_folder(facts)
        return ChannelLookup(
            facts=facts,
            existing=self._repository.channel(facts.channel_id) is not None,
            folder=str(folder),
            video_files=self._files.count_video_files(folder),
        )

    def video_count(self, channel_id: str) -> int | None:
        """Return the video count of a channel that was looked up, or None (R-CH-03).

        Waits for the count at most until 8 seconds after it was asked for.
        A count that failed, came too late or is implausible is None.

        Args:
            channel_id: The channel ID.
        """
        with self._lock:
            count = self._counts.get(channel_id)
        if count is None:
            return None
        left = COUNT_TIME_LIMIT_S - (self._clock.monotonic() - count.started)
        if not count.done.wait(max(left, 0.0)):
            _unavailable(channel_id, "It took longer than the time limit")
            return None
        return count.value

    def preview_avatar(self, channel_id: str) -> bytes | None:
        """Return the avatar of a channel that was looked up, for its preview (R-CH-03).

        The user waits for this one picture, so it is fetched when it is asked
        for. It is kept in memory until the channel is added or the app ends.

        Args:
            channel_id: The channel ID.

        Returns:
            The picture, or None when the channel was not looked up, has no avatar,
            or the avatar could not be fetched.
        """
        with self._lock:
            facts = self._looked_up.get(channel_id)
            kept = self._preview_avatars.get(channel_id)
        if kept is not None or facts is None or facts.avatar_url is None:
            return kept
        try:
            picture = self._youtube.fetch_image(facts.avatar_url, by_user=True)
        except AppError:
            return None
        with self._lock:
            self._preview_avatars[channel_id] = picture
        return picture

    def choose_folder(self) -> ChosenFolder | None:
        """Let the user choose a folder for a channel in the dialog of macOS (R-CH-05).

        Returns:
            The chosen folder with the number of video files in it (R-CH-06), or
            None when the user cancelled or the app has no window.
        """
        chosen = self._picker.choose(self._settings.library_folder())
        if chosen is None:
            return None
        with self._lock:
            self._chosen.add(str(chosen))
        return ChosenFolder(str(chosen), self._files.count_video_files(chosen))

    def add(self, new: NewChannel) -> AddedChannel:
        """Add a channel that was looked up, and start its first listing (R-CH-05, R-CH-11).

        Args:
            new: The channel and what the user chose for it.

        Raises:
            AppError: ``INVALID_REQUEST`` when the channel was not looked up or the
                folder was not chosen in the dialog of macOS. ``FOLDER_UNAVAILABLE``
                or ``PERMISSION_DENIED`` when its folder cannot be created.
        """
        existing = self._views.of(new.channel_id)
        if existing is not None:
            return AddedChannel(existing, existing=True)
        with self._lock:
            facts = self._looked_up.get(new.channel_id)
            folder_was_chosen = new.folder is None or new.folder in self._chosen
        if facts is None:
            raise AppError(ErrorCode.INVALID_REQUEST, {"reason": "The channel was not looked up"})
        if not folder_was_chosen:
            raise AppError(
                ErrorCode.INVALID_REQUEST, {"reason": "The folder was not chosen in the dialog"}
            )
        folder = Path(new.folder) if new.folder is not None else self._default_folder(facts)
        self._files.make_folder(folder)
        channel = Channel(
            id=facts.channel_id,
            url=facts.url,
            title=facts.title,
            handle=facts.handle,
            avatar_url=facts.avatar_url,
            folder=new.folder if new.folder is not None else folder.name,
            folder_is_custom=new.folder is not None,
            quality=new.quality,
            auto_mirror=new.auto_mirror,
            mirror_after=new.mirror_after,
            position=1 + max((other.position for other in self._repository.channels()), default=-1),
        )
        self._repository.add_channel(channel)
        self.write_channel_file(channel.id)
        _log.info(
            "channel.added",
            msg="Channel added",
            channel_id=channel.id,
            folder=str(folder),
            folder_is_custom=channel.folder_is_custom,
            auto_mirror=channel.auto_mirror,
        )
        with self._lock:
            avatar = self._preview_avatars.pop(channel.id, None)
        if avatar is not None:
            self._thumbnails.keep_avatar(channel.id, avatar)
        self._catalogue.request_check(
            channel.id,
            CheckKind.FULL,
            trigger=CheckTrigger.ADD,
            preview_count=self._finished_count(channel.id),
        )
        self._thumbnails.fill(channel.id)
        return AddedChannel(self._view(channel.id), existing=False)

    def set_paused(self, channel_id: str, paused: bool) -> ChannelView:
        """Pause or resume a channel (R-CH-30, R-CH-31).

        A paused channel is not checked: its checks that wait or run are
        dropped. A resumed channel that was never listed gets its first listing.

        Args:
            channel_id: The channel ID.
            paused: True to pause, False to resume.

        Raises:
            AppError: ``NOT_FOUND`` for an unknown channel.
        """
        channel = self._known(channel_id)
        if channel.paused != paused:
            self._repository.save_channel(replace(channel, paused=paused))
            _log.info(
                "channel.paused" if paused else "channel.resumed",
                msg="Channel paused" if paused else "Channel resumed",
                channel_id=channel_id,
            )
            if paused:
                self._catalogue.forget(channel_id)
            elif channel.first_listed_at is None:
                self._catalogue.request_check(
                    channel_id, CheckKind.FULL, trigger=CheckTrigger.RESUME
                )
            self._views.publish(channel_id)
        return self._view(channel_id)

    def write_channel_file(self, channel_id: str) -> None:
        """Add or update the entry of a channel in the channel file of its folder (R-FI-05).

        It is written when the channel folder is created and whenever the
        title or the handle of the channel changed. Two channels can share a
        folder: the entries of the others stay. The write is atomic, so a
        crash never leaves a broken file. Nothing is written while the folder
        is not there: that would create it again.

        Args:
            channel_id: The channel ID. An unknown one writes nothing.
        """
        channel = self._repository.channel(channel_id)
        if channel is None:
            return
        folder = self._views.folder_of(channel)
        if not self._files.folder_exists(folder):
            return
        path = folder / HIDDEN_DIR / CHANNEL_FILE
        existing = self._files.read_bytes(path)
        content = channel_file_with(existing, channel)
        if content != existing:
            self._write_channel_file(channel_id, path, content)

    def _forget_in_channel_file(self, channel_id: str, folder: Path) -> None:
        """Remove the entry of a removed channel; the file goes when no entry is left (R-FI-05)."""
        path = folder / HIDDEN_DIR / CHANNEL_FILE
        existing = self._files.read_bytes(path)
        if existing is None:
            return
        content = channel_file_without(existing, channel_id)
        if content is None:
            try:
                self._files.trash(path)
            except AppError as error:
                _log.warning(
                    "channel.file_failed",
                    msg="The channel file could not be moved to the Trash",
                    channel_id=channel_id,
                    error_code=error.code.value,
                )
            return
        if content != existing:
            self._write_channel_file(channel_id, path, content)

    def _write_channel_file(self, channel_id: str, path: Path, content: bytes) -> None:
        try:
            self._files.write_file(path, content, overwrite=True)
        except AppError as error:
            _log.warning(
                "channel.file_failed",
                msg="The channel file could not be written",
                channel_id=channel_id,
                error_code=error.code.value,
            )
            return
        _log.info("channel.file_written", msg="Channel file written", channel_id=channel_id)

    def files_to_trash(self, channel_id: str) -> FilesToTrash:
        """Return what "Delete the files" would move to the Trash (R-CH-32).

        That is every file the app tracks for the channel: the video files,
        a thumbnail next to a video that is the app's own copy, and the
        metadata and thumbnails of its videos in the hidden folder. Its entry
        in the channel file goes in any case (R-FI-05). A file of
        the user's own stays, and so does anything a symlink leads to outside
        the folder. Two channels can share a custom folder, so only what
        belongs to this channel is taken from the hidden folder.

        Args:
            channel_id: The channel ID.

        Raises:
            AppError: ``NOT_FOUND`` for an unknown channel.
        """
        channel = self._known(channel_id)
        folder = self._views.folder_of(channel)
        hidden = folder / HIDDEN_DIR
        candidates: list[Path] = []
        hidden_files: list[Path] = []
        for video in self._repository.videos(channel_id):
            hidden_files += [hidden / f"{video.id}.info.json", hidden / f"{video.id}.jpg"]
            if not video.file_name:
                continue
            candidates.append(folder / video.file_name)
            cover = (folder / video.file_name).with_suffix(".jpg")
            own_copy = self._files.read_bytes(hidden / f"{video.id}.jpg")
            if own_copy is not None and self._files.read_bytes(cover) == own_copy:
                candidates.append(cover)
        candidates += hidden_files
        paths: list[Path] = []
        for path in candidates:
            if not self._files.exists(path):
                continue
            if not self._files.is_inside(path, folder):
                _log.warning(
                    "file.kept",
                    msg="A file leads out of the channel folder and is not moved to the Trash",
                    channel_id=channel_id,
                    file=str(path),
                )
                continue
            paths.append(path)
        return FilesToTrash(
            paths=tuple(paths),
            files=sum(1 for path in paths if path.parent != hidden),
            size_bytes=sum(self._files.size_of(path) for path in paths),
        )

    def remove(self, channel_id: str, *, keep_files: bool = True) -> None:
        """Remove a channel with its catalogue (R-CH-32).

        With ``keep_files`` its folder and files stay. Otherwise the files the
        app tracks go to the Trash, never away for good, and the folder goes
        too when nothing else is left in it.

        Args:
            channel_id: The channel ID.
            keep_files: Whether the files stay where they are.

        Raises:
            AppError: ``NOT_FOUND`` for an unknown channel.
        """
        channel = self._known(channel_id)
        folder = self._views.folder_of(channel)
        self._cancel_downloads(channel_id)
        self._forget_in_channel_file(channel_id, folder)
        trashed = 0 if keep_files else self._trash_files(channel_id, folder)
        self._catalogue.forget(channel_id)
        video_ids = self._repository.video_ids(channel_id)
        self._repository.remove_channel(channel_id)
        self._thumbnails.forget(channel_id, video_ids)
        self._views.forget(channel_id)
        _log.info(
            "channel.removed",
            msg="Channel removed. Its folder was left as it is"
            if keep_files
            else "Channel removed. Its files went to the Trash",
            channel_id=channel_id,
            videos=len(video_ids),
            folder=str(folder),
            files_trashed=trashed,
        )

    def _trash_files(self, channel_id: str, folder: Path) -> int:
        """Move the tracked files of a channel to the Trash. Returns how many paths went."""
        moved = 0
        for path in self.files_to_trash(channel_id).paths:
            try:
                self._files.trash(path)
            except AppError as error:
                _log.warning(
                    "file.trash_failed",
                    msg="A file of the channel could not be moved to the Trash",
                    channel_id=channel_id,
                    file=str(path),
                    error_code=error.code.value,
                )
                continue
            moved += 1
            _log.info("file.trashed", msg="File moved to the Trash", file=str(path))
        hidden = folder / HIDDEN_DIR
        if self._is_empty(hidden, ignore=(TEMP_DIR,)) and self._files.exists(hidden):
            self._files.trash(hidden)
            _log.info(
                "file.trashed", msg="The empty hidden folder went to the Trash", file=str(hidden)
            )
        if self._is_empty(folder) and self._files.folder_exists(folder):
            self._files.trash(folder)
            _log.info(
                "file.trashed", msg="Empty channel folder moved to the Trash", file=str(folder)
            )
        return moved

    def _is_empty(self, folder: Path, ignore: tuple[str, ...] = ()) -> bool:
        """Whether a folder holds nothing but .DS_Store and empty folders named in ``ignore``."""
        for name in self._files.file_names(folder, hidden=True):
            if name == ".DS_Store":
                continue
            if name in ignore and self._is_empty(folder / name):
                continue
            return False
        return True

    def open_folder(self, channel_id: str) -> None:
        """Show the folder of a channel in Finder (R-CH-30).

        Args:
            channel_id: The channel ID.

        Raises:
            AppError: ``NOT_FOUND`` for an unknown channel, ``FOLDER_UNAVAILABLE``
                when its folder is not there.
        """
        self._files.open_folder(self._views.folder_of(self._known(channel_id)))

    def _known(self, channel_id: str) -> Channel:
        channel = self._repository.channel(channel_id)
        if channel is None:
            raise AppError(ErrorCode.NOT_FOUND, {"channel": channel_id})
        return channel

    def _view(self, channel_id: str) -> ChannelView:
        view = self._views.of(channel_id)
        if view is None:
            raise AppError(ErrorCode.NOT_FOUND, {"channel": channel_id})
        return view

    def _default_folder(self, facts: ChannelFacts) -> Path:
        """Return the folder inside the library that is named after the channel (R-FI-01)."""
        taken = [
            other.folder
            for other in self._repository.channels()
            if not other.folder_is_custom and other.id != facts.channel_id
        ]
        name = channel_folder_name(facts.title, facts.channel_id, taken)
        return self._settings.library_folder() / name

    def _start_count(self, channel_id: str) -> None:
        with self._lock:
            if channel_id in self._counts:
                return
            count = self._counts[channel_id] = _Count(self._clock.monotonic())
        self._run_in_background(lambda: self._fetch_count(channel_id, count))

    def _fetch_count(self, channel_id: str, count: _Count) -> None:
        try:
            value = self._youtube.preview_video_count(channel_id)
        except AppError as error:
            _unavailable(channel_id, error.details.get("message", "The request failed"), error.code)
        else:
            if 0 <= value <= MOST_PLAUSIBLE_VIDEOS:
                count.value = value
            else:
                _unavailable(channel_id, f"{value} is not a plausible number of videos")
        finally:
            count.done.set()

    def _finished_count(self, channel_id: str) -> int | None:
        with self._lock:
            count = self._counts.pop(channel_id, None)
            self._looked_up.pop(channel_id, None)
        return count.value if count is not None and count.done.is_set() else None


def _unavailable(channel_id: str, reason: str, code: ErrorCode | None = None) -> None:
    """Log why a preview has no video count. The preview is shown without it (R-CH-03)."""
    _log.info(
        "channel.count_unavailable",
        msg="The preview of a channel has no video count",
        channel_id=channel_id,
        reason=reason,
        error_code=None if code is None else code.value,
    )
