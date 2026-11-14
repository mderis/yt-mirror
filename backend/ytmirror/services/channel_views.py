"""Channels as the interface shows them, and what is running on them.

One place builds the view of a channel: its stored values, its derived
status (R-FB-01), its totals (R-CH-35) and the progress of a long check. The
services that change a channel publish its new view through here, so the
interface hears of every change within a second (R-FB-03).

This module must not start or change anything itself.

Tests: backend/tests/unit/services/test_channel_views.py
"""

import threading
from pathlib import Path

from ytmirror.core.channels import (
    Channel,
    ChannelTotals,
    ChannelUpdated,
    ChannelView,
    TaskProgress,
    TaskProgressed,
    VideoView,
)
from ytmirror.core.dates import moment_to_show
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.status import NEW_FOR_S, channel_status, is_new
from ytmirror.ports.catalogue_repository import CatalogueRepository
from ytmirror.ports.clock import Clock
from ytmirror.services.events import EventBus
from ytmirror.services.settings import SettingsService


class ChannelViews:
    """Builds and publishes the views of channels, and knows which ones are being checked."""

    def __init__(
        self,
        repository: CatalogueRepository,
        settings: SettingsService,
        clock: Clock,
        events: EventBus,
    ) -> None:
        """Create the views.

        Args:
            repository: The stored channels and videos.
            settings: The general settings, for the library folder.
            clock: The source of time.
            events: Where changes are published.
        """
        self._repository = repository
        self._settings = settings
        self._clock = clock
        self._events = events
        self._lock = threading.Lock()
        self._checking: set[str] = set()
        self._progress: dict[str, TaskProgress] = {}
        self._pictures: dict[str, int] = {}
        self._avatars: dict[str, int] = {}
        self._catalogues: dict[str, int] = {}

    def folder_of(self, channel: Channel) -> Path:
        """Return the folder of a channel as a real path (R-FI-01).

        Args:
            channel: The channel.
        """
        if channel.folder_is_custom:
            return Path(channel.folder)
        return self._settings.library_folder() / channel.folder

    def all(self) -> tuple[ChannelView, ...]:
        """Return every channel as the interface shows it, in the order of the sidebar."""
        totals = self._repository.totals(self._new_since())
        return tuple(
            self._view(channel, totals.get(channel.id, ChannelTotals()))
            for channel in self._repository.channels()
        )

    def of(self, channel_id: str) -> ChannelView | None:
        """Return one channel as the interface shows it, or None when it is not stored.

        Args:
            channel_id: The channel ID.
        """
        channel = self._repository.channel(channel_id)
        if channel is None:
            return None
        totals = self._repository.totals(self._new_since())
        return self._view(channel, totals.get(channel_id, ChannelTotals()))

    def videos(self, channel_id: str) -> tuple[VideoView, ...]:
        """Return the catalogue of a channel as a list shows it, in channel order (R-CH-10).

        Args:
            channel_id: The channel ID.

        Raises:
            AppError: ``NOT_FOUND`` for an unknown channel.
        """
        if self._repository.channel(channel_id) is None:
            raise AppError(ErrorCode.NOT_FOUND, {"channel": channel_id})
        now = int(self._clock.now().timestamp())
        return tuple(
            VideoView(
                video=video,
                is_new=is_new(video, now),
                published_around=None
                if video.published_at is None or video.published_precision is None
                else moment_to_show(video.published_at, video.published_precision),
            )
            for video in self._repository.videos(channel_id)
        )

    def publish(self, channel_id: str) -> None:
        """Tell the interface how a channel is now. A removed channel is not told.

        Args:
            channel_id: The channel ID.
        """
        view = self.of(channel_id)
        if view is not None:
            self._events.publish(ChannelUpdated(view))

    def set_checking(self, channel_id: str, checking: bool) -> None:
        """Remember whether a check of a channel is waiting or running, and tell the interface.

        Args:
            channel_id: The channel ID.
            checking: Whether a check is waiting or running.
        """
        with self._lock:
            if checking:
                self._checking.add(channel_id)
            else:
                self._checking.discard(channel_id)
                self._progress.pop(channel_id, None)
        self.publish(channel_id)

    def is_checking(self, channel_id: str) -> bool:
        """Return whether a check of a channel is waiting or running.

        Args:
            channel_id: The channel ID.
        """
        with self._lock:
            return channel_id in self._checking

    def set_progress(self, progress: TaskProgress) -> None:
        """Remember how far a long check has come, and tell the interface (R-CH-11, R-CH-27).

        Args:
            progress: The progress.
        """
        with self._lock:
            self._progress[progress.channel_id] = progress
        self._events.publish(TaskProgressed(progress))

    def catalogue_read(self, channel_id: str) -> None:
        """Note that a check of a channel was stored: its catalogue may have changed (R-FB-03).

        The interface hears of it with the next ``publish`` of the channel.
        Times are whole seconds, so they cannot tell two checks apart.

        Args:
            channel_id: The channel ID.
        """
        with self._lock:
            self._catalogues[channel_id] = self._catalogues.get(channel_id, 0) + 1

    def more_pictures(self, channel_id: str, *, avatar: bool = False) -> None:
        """Note that more pictures of a channel are cached, and tell the interface (R-CH-16).

        Args:
            channel_id: The channel ID.
            avatar: Whether the avatar of the channel was among them (R-CH-12).
        """
        with self._lock:
            self._pictures[channel_id] = self._pictures.get(channel_id, 0) + 1
            if avatar:
                self._avatars[channel_id] = self._avatars.get(channel_id, 0) + 1
        self.publish(channel_id)

    def forget(self, channel_id: str) -> None:
        """Drop what is remembered about a channel that was removed.

        Args:
            channel_id: The channel ID.
        """
        with self._lock:
            self._checking.discard(channel_id)
            self._progress.pop(channel_id, None)
            self._pictures.pop(channel_id, None)
            self._avatars.pop(channel_id, None)
            self._catalogues.pop(channel_id, None)

    def _view(self, channel: Channel, totals: ChannelTotals) -> ChannelView:
        with self._lock:
            checking = channel.id in self._checking
            progress = self._progress.get(channel.id)
            pictures = self._pictures.get(channel.id, 0)
            avatar_version = self._avatars.get(channel.id, 0)
            catalogue_version = self._catalogues.get(channel.id, 0)
        return ChannelView(
            channel=channel,
            status=channel_status(channel, checking=checking, new_videos=totals.new),
            totals=totals,
            progress=progress,
            folder=str(self.folder_of(channel)),
            pictures=pictures,
            avatar_version=avatar_version,
            catalogue_version=catalogue_version,
        )

    def _new_since(self) -> int:
        return int(self._clock.now().timestamp()) - NEW_FOR_S
