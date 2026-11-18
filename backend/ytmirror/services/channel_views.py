"""Channels as the interface shows them, and what is running on them.

One place builds the view of a channel: its stored values, its derived
status (R-FB-01), its totals (R-CH-35) and the progress of a long check. The
services that change a channel publish its new view through here, so the
interface hears of every change within a second (R-FB-03).

A channel also shows how far its exact dates are, with the time left, the
key offer and a notice when a saved key is not working (R-DT-12 to R-DT-15),
and a video shows whether its approximate date is waiting, updating or
unavailable (R-DT-13).

A channel also shows when the app holds work for it until YouTube answers
again (R-ER-05, R-FB-01). The views listen for the beginning and the end of
that pause and tell the interface about the channels it concerns.

This module must not start or change anything itself.

Tests: backend/tests/unit/services/test_channel_views.py
"""

import threading
from collections.abc import Callable, Mapping
from pathlib import Path

from ytmirror.core.channels import (
    Channel,
    ChannelTotals,
    ChannelUpdated,
    ChannelView,
    ChecksProgressed,
    TaskProgress,
    TaskProgressed,
    Video,
    VideoView,
    YouTubePauseChanged,
)
from ytmirror.core.dates import moment_to_show
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.exact_dates import DateShown, FetchState, date_shown
from ytmirror.core.jobs import VideoUpdated
from ytmirror.core.models import AppEvent
from ytmirror.core.schedule import retry_at
from ytmirror.core.status import NEW_FOR_S, channel_status, is_new, waits_for_youtube
from ytmirror.ports.catalogue_repository import CatalogueRepository
from ytmirror.ports.clock import Clock
from ytmirror.services.date_fetch_state import DateFetchState
from ytmirror.services.download_state import DownloadState
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
        youtube_paused: Callable[[], bool] = lambda: False,
        downloads: DownloadState | None = None,
        dates: DateFetchState | None = None,
        fetch_states: Callable[[str], Mapping[str, FetchState]] = lambda channel_id: {},
    ) -> None:
        """Create the views.

        Args:
            repository: The stored channels and videos.
            settings: The general settings, for the library folder.
            clock: The source of time.
            events: Where changes are published, and where the pause of YouTube is heard.
            youtube_paused: Tells whether the app pauses what it asks of YouTube by itself.
            downloads: The downloads that wait or run.
            dates: How the exact-date fetch stands.
            fetch_states: What the fetch keeps for the videos of a channel.
        """
        self._repository = repository
        self._settings = settings
        self._clock = clock
        self._events = events
        self._youtube_paused = youtube_paused
        self._downloads = downloads if downloads is not None else DownloadState()
        self._dates = dates if dates is not None else DateFetchState()
        self._fetch_states = fetch_states
        events.subscribe(self._on_event)
        self._lock = threading.Lock()
        self._checking: set[str] = set()
        self._progress: dict[str, TaskProgress] = {}
        self._pictures: dict[str, int] = {}
        self._avatars: dict[str, int] = {}
        self._catalogues: dict[str, int] = {}
        self._batch: dict[str, bool] = {}
        self._folders_missing: set[str] = set()
        """The channels whose folder is gone from a connected drive (R-MI-06, D-087)."""
        """The channels of a check of all channels, and whether their check ended."""

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
        states = self._fetch_states(channel_id)
        return tuple(
            self._video_view(video, now, states.get(video.id))
            for video in self._repository.videos(channel_id)
        )

    def video(self, video_id: str) -> VideoView | None:
        """Return one video as the interface shows it, or None when no catalogue has it.

        Args:
            video_id: The video ID.
        """
        video = self._repository.video(video_id)
        if video is None:
            return None
        states: Mapping[str, FetchState] = (
            {} if video.published_exact else self._fetch_states(video.channel_id)
        )
        return self._video_view(video, int(self._clock.now().timestamp()), states.get(video.id))

    def tell_video(self, video_id: str) -> None:
        """Tell the interface how a video is now (R-FB-03). An unknown video is not told.

        Args:
            video_id: The video ID.
        """
        view = self.video(video_id)
        if view is not None:
            self._events.publish(VideoUpdated(view))

    def _video_view(self, video: Video, now: int, state: FetchState | None) -> VideoView:
        return VideoView(
            video=video,
            is_new=is_new(video, now),
            published_around=None
            if video.published_at is None or video.published_precision is None
            else moment_to_show(video.published_at, video.published_precision),
            job_id=self._downloads.job_of(video.id),
            progress=self._downloads.progress_of(video.id),
            date=self._date_of(video, now, state),
            paced_until=self._downloads.paced_until(video.id),
            retry_at=self._downloads.retry_at(video.id),
        )

    def _date_of(self, video: Video, now: int, state: FetchState | None) -> DateShown | None:
        """Return what an approximate date shows (R-DT-13), or None for an exact one."""
        if video.published_exact or video.published_at is None or video.gone:
            return None
        return date_shown(
            state, updating=self._dates.updating(video.id), hold=self._dates.hold(), now=now
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
        batch: tuple[int, int] | None = None
        with self._lock:
            if checking:
                self._checking.add(channel_id)
            else:
                self._checking.discard(channel_id)
                self._progress.pop(channel_id, None)
            told = not checking and self._batch.get(channel_id) is False
            if told:
                self._batch[channel_id] = True
                batch = self._batch_progress()
                if batch is not None and batch[0] == batch[1]:
                    self._batch.clear()
                    batch = None
        self.publish(channel_id)
        if told:
            self._events.publish(ChecksProgressed(batch))

    def set_folder_missing(self, channel_id: str, missing: bool) -> bool:
        """Note whether the folder of a channel is gone from a connected drive, and tell it.

        Args:
            channel_id: The channel ID.
            missing: Whether its folder was not found.

        Returns:
            Whether that changed.
        """
        with self._lock:
            changed = (channel_id in self._folders_missing) != missing
            if missing:
                self._folders_missing.add(channel_id)
            else:
                self._folders_missing.discard(channel_id)
        if changed:
            self.publish(channel_id)
        return changed

    def start_batch(self, channel_ids: list[str]) -> None:
        """Count checks of all channels together, for "Checking channels: 3 of 5" (R-CH-20).

        Channels of a batch that still runs are counted on.

        Args:
            channel_ids: The channels whose checks are put in line.
        """
        if not channel_ids:
            return
        with self._lock:
            for channel_id in channel_ids:
                self._batch[channel_id] = False
            progress = self._batch_progress()
        self._events.publish(ChecksProgressed(progress))

    def leave_batch(self, channel_id: str) -> None:
        """Count a channel of a check of all channels as done without its check.

        For a channel that was removed, or whose check could not be put in line.

        Args:
            channel_id: The channel ID.
        """
        with self._lock:
            if channel_id not in self._batch:
                return
            self._batch[channel_id] = True
            batch = self._batch_progress()
            if batch is not None and batch[0] == batch[1]:
                self._batch.clear()
                batch = None
        self._events.publish(ChecksProgressed(batch))

    def checking_all(self) -> tuple[int, int] | None:
        """Return how many checks of the batch of all channels ended, and how many there are."""
        with self._lock:
            return self._batch_progress()

    def _batch_progress(self) -> tuple[int, int] | None:
        if not self._batch:
            return None
        return sum(self._batch.values()), len(self._batch)

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
        self.leave_batch(channel_id)
        with self._lock:
            self._checking.discard(channel_id)
            self._batch.pop(channel_id, None)
            self._folders_missing.discard(channel_id)
            self._progress.pop(channel_id, None)
            self._pictures.pop(channel_id, None)
            self._avatars.pop(channel_id, None)
            self._catalogues.pop(channel_id, None)

    def _on_event(self, event: AppEvent | None) -> None:
        """Tell the interface about the channels whose status follows the pause of YouTube."""
        if not isinstance(event, YouTubePauseChanged):
            return
        for channel in self._repository.channels():
            # These are the channels that wait when the pause is in force (R-FB-01).
            if waits_for_youtube(channel, youtube_paused=True):
                self.publish(channel.id)

    def _view(self, channel: Channel, totals: ChannelTotals) -> ChannelView:
        with self._lock:
            checking = channel.id in self._checking
            progress = self._progress.get(channel.id)
            pictures = self._pictures.get(channel.id, 0)
            avatar_version = self._avatars.get(channel.id, 0)
            catalogue_version = self._catalogues.get(channel.id, 0)
            folder_missing = channel.id in self._folders_missing
        mirroring = self._downloads.mirroring(channel.id)
        exact_dates = self._dates.progress(channel.id)
        dates_wait = self._dates.waits_for_youtube(channel.id)
        hold = self._dates.hold() if dates_wait else None
        return ChannelView(
            channel=channel,
            status=channel_status(
                channel,
                checking=checking,
                new_videos=totals.new,
                waiting_for_youtube=waits_for_youtube(
                    channel, youtube_paused=self._youtube_paused()
                ),
                mirroring=mirroring is not None,
                exact_dates=self._dates.running(channel.id),
                exact_dates_wait=dates_wait,
                folder_missing=folder_missing,
            ),
            totals=totals,
            progress=progress,
            folder=str(self.folder_of(channel)),
            pictures=pictures,
            avatar_version=avatar_version,
            catalogue_version=catalogue_version,
            mirroring=None if mirroring is None else (mirroring.done, mirroring.total),
            exact_dates=exact_dates,
            key_notice=exact_dates is not None and self._dates.key().failing,
            waiting_until=None if hold is None else hold.until,
            retry_at=retry_at(channel),
        )

    def _new_since(self) -> int:
        return int(self._clock.now().timestamp()) - NEW_FOR_S
