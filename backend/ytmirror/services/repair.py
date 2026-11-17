"""Missing files, date repair and the rename of a file whose video got a new title.

Implements R-MI-06, R-DT-09, R-DT-10, R-FN-06 and the work of R-CH-28 that
needs no listing. After every check, and when a channel is opened, each
synced file is looked for by its name, without reading it: a file that is
not there makes its video "File missing", and the file of a "File missing"
video that is back under its name, with this video's ID inside, makes it
synced again (for example after "Put Back" from the Trash). A file renamed
or moved by the user counts as missing; finding it is adoption. Only single
files missing from a folder that is there are marked (D-087): a channel
folder gone from a connected drive (moved, renamed or deleted) gives the
channel the status "Folder not found" and leaves its videos as they are,
and while the drive of the folder is not connected nothing is marked at all
(R-QU-11).

After every check (and on demand, "Repair dates" in the channel menu) the
dates of each synced file are compared with the published time and set
again where they differ, then read back (R-DT-07). A synced file whose name
no longer fits its video's title is renamed to the title (also a file named
by its video ID whose title can now be stored, R-FN-01): never over another
file, its dates set and read back afterwards (R-DT-10).

A rename moves the file first and then stores its new name, only if the
stored one is still the old one. Should the app end between the two, the
next check finds the file under its new name, makes sure by the video ID
inside it that it is this video, and stores the name: a file is never lost
and never moved to the Trash by a rename.

Only synced and missing videos are touched; in milestone M4 neither is
being downloaded while their files are looked at: a status change is stored
only when the video still has the status it was read with.
One lock keeps the repairs of a check and those asked for by hand apart.
The activity log of R-FN-06 arrives in milestone M7; until then a rename is
the log event ``file.renamed``.

Tests: backend/tests/unit/services/test_repair.py
"""

import threading
from dataclasses import dataclass
from pathlib import Path

import structlog
from structlog.typing import FilteringBoundLogger

from ytmirror.core.channels import Channel, Video, VideoStatus
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.naming import same_name_key, video_file_name
from ytmirror.core.status import change_status
from ytmirror.ports.catalogue_repository import CatalogueRepository
from ytmirror.ports.file_system import FileSystem
from ytmirror.ports.media_tools import MediaTools
from ytmirror.services.channel_views import ChannelViews
from ytmirror.services.settings import SettingsService

_log: FilteringBoundLogger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RepairResult:
    """What a repair of a channel's file dates did (R-DT-09).

    Attributes:
        checked: How many synced files were compared.
        repaired: How many had other dates and were set again.
        failed: How many could not be set or did not read back.
    """

    checked: int = 0
    repaired: int = 0
    failed: int = 0


def apply_dates(files: FileSystem, path: Path, published: int) -> None:
    """Set both dates of a file to the published time and read them back (R-DT-07).

    Args:
        files: The file system.
        path: The file.
        published: The exact published time.

    Raises:
        AppError: ``DATES_NOT_APPLIED`` when they cannot be set or do not read back.
    """
    files.set_dates(path, published)
    verify_dates(files, path, published)


def verify_dates(files: FileSystem, path: Path, published: int) -> None:
    """Read both dates of a file back and compare them with the published time (R-DT-07).

    Raises:
        AppError: ``DATES_NOT_APPLIED`` when they differ.
    """
    dates = files.read_dates(path)
    if (dates.created, dates.modified) != (published, published):
        raise AppError(
            ErrorCode.DATES_NOT_APPLIED,
            {
                "expected": str(published),
                "created": str(dates.created),
                "modified": str(dates.modified),
            },
        )


def fits_title(file_name: str, video: Video) -> bool:
    """Return whether a file name is what the title of its video gives (R-FN-01, R-FN-05).

    Either the plain name, or the name with the video ID that a taken or a
    too long name gets.
    """
    plain = video_file_name(video.title, video.id, ())
    with_id = video_file_name(video.title, video.id, (plain,))
    return same_name_key(file_name) in {same_name_key(plain), same_name_key(with_id)}


class RepairService:
    """Repairs the dates of synced files and renames them after their titles."""

    def __init__(
        self,
        *,
        repository: CatalogueRepository,
        files: FileSystem,
        media: MediaTools,
        views: ChannelViews,
        settings: SettingsService,
    ) -> None:
        """Create the service.

        Args:
            repository: The stored channels and videos.
            files: The folders and files of this Mac.
            media: Reads the video ID inside a file.
            views: The folder of a channel, and tells the interface about a video.
            settings: Whether every check repairs dates.
        """
        self._repository = repository
        self._files = files
        self._media = media
        self._views = views
        self._settings = settings
        self._lock = threading.Lock()

    def after_check(self, channel_id: str) -> None:
        """The work of a check that needs no listing (R-CH-28): renames, then date repair.

        A failure here never fails the check: the check is stored already, and the
        work is tried again at the next one.

        Args:
            channel_id: The channel that was checked.
        """
        try:
            self.verify_files(channel_id)
            self.rename_retitled(channel_id)
            if self._settings.current().repair_dates:
                self.repair_dates(channel_id)
        except Exception as error:  # noqa: BLE001  (a stored check must stay stored)
            _log.warning(
                "dates.repair.failed",
                msg="The renames and the date repair after a check failed; tried at the next",
                channel_id=channel_id,
                error_code=error.code.value
                if isinstance(error, AppError)
                else ErrorCode.INTERNAL.value,
                error=str(error),
            )

    def channel_opened(self, channel_id: str) -> None:
        """Look for the files of a channel the user opened (R-MI-06). Never raises."""
        try:
            self.verify_files(channel_id)
        except Exception as error:  # noqa: BLE001  (opening a channel never fails for this)
            _log.warning(
                "file.check_failed",
                msg="The files of an opened channel could not be looked for",
                channel_id=channel_id,
                error=str(error),
            )

    def verify_files(self, channel_id: str) -> tuple[int, int]:
        """Mark synced videos whose file is gone as missing, and those whose file is back as synced.

        Implements R-MI-06 with R-QU-11. Files are looked for by name; only a
        file that came back is read, for the video ID inside it.

        Args:
            channel_id: The channel.

        Returns:
            How many videos became missing, and how many synced again.
        """
        channel = self._repository.channel(channel_id)
        if channel is None:
            return 0, 0
        folder = self._views.folder_of(channel)
        missing = back = 0
        with self._lock:
            if not self._files.folder_exists(folder):
                if not self._files.drive_connected(folder):
                    _log.info(
                        "file.unchecked",
                        msg="The drive of a channel folder is not connected; no file is marked",
                        channel_id=channel_id,
                        folder=str(folder),
                    )
                elif self._views.set_folder_missing(channel_id, True):
                    _log.warning(
                        "channel.folder_missing",
                        msg="The channel folder is not there; its videos keep their status",
                        channel_id=channel_id,
                        folder=str(folder),
                    )
                return 0, 0
            if self._views.set_folder_missing(channel_id, False):
                _log.info(
                    "channel.folder_found",
                    msg="The channel folder is there again",
                    channel_id=channel_id,
                    folder=str(folder),
                )
            for video in self._repository.videos(channel_id):
                if not video.file_name or video.placing_file:
                    continue
                path = folder / video.file_name
                if video.status is VideoStatus.SYNCED and not self._files.exists(path):
                    # A rename the app's end interrupted is completed, not counted as missing.
                    if not self._take_moved(video, folder, video.file_name):
                        missing += self._mark(
                            video, VideoStatus.FILE_MISSING, "file_not_found", path
                        )
                elif video.status is VideoStatus.FILE_MISSING and self._is_own(video, path):
                    back += self._mark(video, VideoStatus.SYNCED, "file_back", path)
        if missing or back:
            self._views.publish(channel_id)
        return missing, back

    def _is_own(self, video: Video, path: Path) -> bool:
        if not self._files.exists(path):
            return False
        try:
            return self._media.probe(path).tags.get("video_id") == video.id
        except AppError:
            return False

    def _mark(self, video: Video, status: VideoStatus, reason: str, path: Path) -> bool:
        if not self._repository.change_status(
            change_status(video.id, video.status, status, reason)
        ):
            return False
        _log.info(
            "file.missing" if status is VideoStatus.FILE_MISSING else "file.returned",
            msg="A synced file is not in its folder"
            if status is VideoStatus.FILE_MISSING
            else "The file of a missing video is back",
            video_id=video.id,
            file=str(path),
        )
        self._views.tell_video(video.id)
        return True

    def repair_dates(self, channel_id: str) -> RepairResult:
        """Set the dates of every synced file of a channel that differ (R-DT-09).

        Args:
            channel_id: The channel.

        Raises:
            AppError: ``NOT_FOUND`` for an unknown channel.
        """
        channel = self._channel(channel_id)
        folder = self._views.folder_of(channel)
        checked = repaired = failed = 0
        with self._lock:
            if not self._files.folder_exists(folder):
                return RepairResult()
            for video in self._synced(channel_id):
                assert video.file_name is not None and video.published_at is not None
                path = folder / video.file_name
                if not self._files.exists(path):
                    continue
                checked += 1
                outcome = self._repair_one(video, path, video.published_at)
                repaired += outcome is True
                failed += outcome is False
        if repaired or failed:
            _log.info(
                "dates.repair.finished",
                msg="The file dates of a channel were compared and repaired",
                channel_id=channel_id,
                checked=checked,
                repaired=repaired,
                failed=failed,
            )
        return RepairResult(checked, repaired, failed)

    def repair_video(self, video_id: str) -> None:
        """Repair the dates of one synced file, for example after its exact time changed.

        Args:
            video_id: The video.
        """
        video = self._repository.video(video_id)
        if video is None or video.status is not VideoStatus.SYNCED or not video.file_name:
            return
        if video.published_at is None or not video.published_exact:
            return
        channel = self._repository.channel(video.channel_id)
        if channel is None:
            return
        path = self._views.folder_of(channel) / video.file_name
        with self._lock:
            if self._files.exists(path):
                self._repair_one(video, path, video.published_at)

    def rename_retitled(self, channel_id: str) -> int:
        """Rename the synced files whose names no longer fit their titles (R-FN-06).

        Args:
            channel_id: The channel.

        Returns:
            How many files were renamed.
        """
        channel = self._repository.channel(channel_id)
        if channel is None:
            return 0
        folder = self._views.folder_of(channel)
        renamed = 0
        with self._lock:
            if not self._files.folder_exists(folder):
                return 0
            for video in self._synced(channel_id):
                assert video.file_name is not None
                if fits_title(video.file_name, video):
                    continue
                renamed += self._rename(channel, video, folder)
        return renamed

    def _rename(self, channel: Channel, video: Video, folder: Path) -> bool:
        assert video.file_name is not None and video.published_at is not None
        old = video.file_name
        source = folder / old
        if not self._files.exists(source):
            # The app ended between the move and storing the name: take the moved file.
            return self._take_moved(video, folder, old)
        taken = [
            *(
                name
                for name in self._files.file_names(folder)
                if same_name_key(name) != same_name_key(old)
            ),
            *self._names_tracked_in(folder, video.id),
        ]
        new = video_file_name(video.title, video.id, taken)
        if same_name_key(new) == same_name_key(old):
            return False
        target = folder / new
        try:
            moved = self._files.move(source, target)
        except (AppError, OSError) as error:
            self._rename_failed(video, error)
            return False
        if not moved:
            return False
        if not self._repository.set_file_name(video.id, old, new):
            # The video changed meanwhile: put the file back where the catalogue expects it.
            self._files.move(target, source)
            return False
        self._move_cover(folder, old, new)
        _log.info(
            "file.renamed",
            msg="A file was renamed after the new title of its video",
            channel_id=channel.id,
            video_id=video.id,
            old=old,
            new=new,
        )
        self._repair_one(video, target, video.published_at)
        self._views.tell_video(video.id)
        return True

    def _take_moved(self, video: Video, folder: Path, old: str) -> bool:
        """Store the name of a file a rename moved, found by the video ID inside it."""
        plain = video_file_name(video.title, video.id, ())
        for new in (plain, video_file_name(video.title, video.id, (plain,))):
            target = folder / new
            if not self._files.exists(target):
                continue
            try:
                own = self._media.probe(target).tags.get("video_id") == video.id
            except AppError:
                own = False
            if not own or not self._repository.set_file_name(video.id, old, new):
                continue
            _log.info(
                "file.renamed",
                msg="A rename that was interrupted was completed",
                video_id=video.id,
                old=old,
                new=new,
            )
            assert video.published_at is not None
            self._repair_one(video, target, video.published_at)
            self._views.tell_video(video.id)
            return True
        return False

    def _move_cover(self, folder: Path, old: str, new: str) -> None:
        """Rename the thumbnail next to the video with it (R-MD-05), if there is one."""
        cover, renamed = (
            folder / Path(old).with_suffix(".jpg"),
            folder / Path(new).with_suffix(".jpg"),
        )
        try:
            if self._files.exists(cover):
                self._files.move(cover, renamed)
        except (AppError, OSError) as error:
            _log.warning(
                "file.move_failed",
                msg="The thumbnail next to a renamed video could not be renamed",
                file=str(cover),
                error=str(error),
            )

    def _repair_one(self, video: Video, path: Path, published: int) -> bool | None:
        """Set the dates of one file when they differ. Returns None when they were right."""
        try:
            dates = self._files.read_dates(path)
            if (dates.created, dates.modified) == (published, published):
                return None
            apply_dates(self._files, path, published)
        except (AppError, OSError) as error:
            _log.warning(
                "dates.verify_failed",
                msg="The dates of a file could not be repaired",
                video_id=video.id,
                error_code=error.code.value
                if isinstance(error, AppError)
                else ErrorCode.DATES_NOT_APPLIED.value,
            )
            return False
        _log.info(
            "dates.repaired",
            msg="The dates of a file were set to the published time again",
            video_id=video.id,
            published=published,
            created=dates.created,
            modified=dates.modified,
        )
        return True

    def _rename_failed(self, video: Video, error: Exception) -> None:
        _log.warning(
            "file.rename_failed",
            msg="A file could not be renamed after the new title of its video",
            video_id=video.id,
            error_code=error.code.value
            if isinstance(error, AppError)
            else ErrorCode.PERMISSION_DENIED.value,
        )

    def _synced(self, channel_id: str) -> list[Video]:
        return [
            video
            for video in self._repository.videos(channel_id)
            if video.status is VideoStatus.SYNCED
            and video.file_name
            and video.published_at is not None
            and video.published_exact
            and not video.placing_file
        ]

    def _names_tracked_in(self, folder: Path, except_video: str) -> list[str]:
        """Every name the app tracks in a folder, of every channel that shares it."""
        names: list[str] = []
        for channel in self._repository.channels():
            if self._views.folder_of(channel) != folder:
                continue
            for other in self._repository.videos(channel.id):
                if other.id != except_video:
                    names += [name for name in (other.file_name, other.placing_file) if name]
        return names

    def _channel(self, channel_id: str) -> Channel:
        channel = self._repository.channel(channel_id)
        if channel is None:
            raise AppError(ErrorCode.NOT_FOUND, {"channel": channel_id})
        return channel
