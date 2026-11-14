"""The snapshot of the app that the window loads when it connects.

Implements ``GET /api/state`` for milestone M2 (docs/ARCHITECTURE.md section
7.6): the channels as the sidebar shows them (R-CH-34), the library folder
and its disk (R-UI-01), the channel that was open last (R-UI-02), whether a
folder can be chosen, and the pause of the whole app (R-ER-05). Later
milestones add the queue, the banners and the settings.

Tests: backend/tests/unit/services/test_state.py
"""

from dataclasses import dataclass

from ytmirror.core.channels import ChannelView, YouTubePause
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.ports.app_meta_repository import AppMetaRepository
from ytmirror.ports.file_system import Disk, FileSystem
from ytmirror.ports.folder_picker import FolderPicker
from ytmirror.services.channel_views import ChannelViews
from ytmirror.services.settings import SettingsService
from ytmirror.services.youtube_access import YouTubeAccess

OPEN_CHANNEL_KEY = "last_open_channel"
"""The fact in ``app_meta`` that holds the ID of the channel that was open last."""


@dataclass(frozen=True, slots=True)
class AppState:
    """Everything the window needs to draw itself.

    Attributes:
        channels: Every channel as the interface shows it, in the order of the sidebar.
        open_channel_id: The channel that was open last, or None (R-UI-02).
        library_folder: The library folder as a path.
        disk: The disk the library is on (R-UI-01).
        can_choose_folder: Whether the folder dialog of macOS can be shown.
        youtube_pause: The pause of what the app asks of YouTube by itself, or None.
    """

    channels: tuple[ChannelView, ...]
    open_channel_id: str | None
    library_folder: str
    disk: Disk
    can_choose_folder: bool
    youtube_pause: YouTubePause | None


class StateService:
    """Builds the snapshot and remembers which channel is open."""

    def __init__(
        self,
        views: ChannelViews,
        settings: SettingsService,
        files: FileSystem,
        picker: FolderPicker,
        meta: AppMetaRepository,
        youtube: YouTubeAccess,
    ) -> None:
        """Create the service.

        Args:
            views: The channels as the interface shows them.
            settings: The general settings.
            files: Folders and disks of this Mac.
            picker: The folder dialog of macOS.
            meta: Where the open channel is remembered.
            youtube: The access to YouTube, for its pause.
        """
        self._views = views
        self._settings = settings
        self._files = files
        self._picker = picker
        self._meta = meta
        self._youtube = youtube

    def snapshot(self) -> AppState:
        """Return the app as it is right now."""
        channels = self._views.all()
        library = self._settings.library_folder()
        remembered = self._meta.get(OPEN_CHANNEL_KEY)
        known = {view.channel.id for view in channels}
        return AppState(
            channels=channels,
            open_channel_id=remembered if remembered in known else None,
            library_folder=str(library),
            disk=self._files.disk_of(library),
            can_choose_folder=self._picker.available(),
            youtube_pause=self._youtube.pause(),
        )

    def open_channel(self, channel_id: str | None) -> None:
        """Remember which channel the user has open, for the next start (R-UI-02).

        Args:
            channel_id: The channel ID, or None when no channel is open.

        Raises:
            AppError: ``NOT_FOUND`` for an unknown channel.
        """
        if channel_id is not None and self._views.of(channel_id) is None:
            raise AppError(ErrorCode.NOT_FOUND, {"channel": channel_id})
        self._meta.put(OPEN_CHANNEL_KEY, channel_id or "")
