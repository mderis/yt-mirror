"""Checks of channels: reading the video list from YouTube into the catalogue.

Implements the flow of docs/ARCHITECTURE.md section 7.1 for milestone M2:
the first listing in the background with progress (R-CH-11), quick and full
checks started by hand (R-CH-23), one after another (R-CH-24), a full check
that shows progress and can be cancelled (R-CH-27), and a failed check that
keeps the catalogue and leaves its error code on the channel (R-CH-25).
What a check changes is decided by ``core/catalogue.py``.

One worker takes the checks one after another, so two listings never ask
YouTube at the same time. The checks that run by themselves on a schedule
arrive in milestone M4.

Tests: backend/tests/unit/services/test_catalogue.py
"""

import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, replace

import structlog
from structlog.typing import FilteringBoundLogger

from ytmirror.core.catalogue import (
    CheckChanges,
    changes_of_check,
    listing_is_implausible,
    read_for_quick_check,
)
from ytmirror.core.channels import (
    Channel,
    ChannelListing,
    CheckKind,
    ListedVideo,
    TaskKind,
    TaskProgress,
)
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.ports.catalogue_repository import CatalogueRepository
from ytmirror.ports.clock import Clock
from ytmirror.services.channel_views import ChannelViews
from ytmirror.services.youtube_access import YouTubeAccess

_log: FilteringBoundLogger = structlog.get_logger(__name__)

PROGRESS_EVERY = 30
"""A long check tells its progress after this many videos: one page of a listing."""


@dataclass(frozen=True, slots=True)
class _Request:
    """One check that waits for the worker or runs."""

    channel_id: str
    kind: CheckKind
    by_user: bool
    preview_count: int | None = None


class _CancelledError(Exception):
    """The running check was cancelled, or the app stops."""


class CatalogueService:
    """Runs the checks of channels, one after another."""

    def __init__(
        self,
        repository: CatalogueRepository,
        youtube: YouTubeAccess,
        views: ChannelViews,
        clock: Clock,
        run_in_background: Callable[[Callable[[], None]], None],
        after_check: Callable[[str, CheckKind], None] | None = None,
    ) -> None:
        """Create the service. Nothing runs before ``start``.

        Args:
            repository: The stored channels and videos.
            youtube: The access to YouTube.
            views: Publishes how a channel is now.
            clock: The source of time.
            run_in_background: Runs the worker without blocking the caller.
            after_check: Told the channel ID and the kind of check after every
                successful check, for work that follows a check, such as caching
                its pictures.
        """
        self._repository = repository
        self._youtube = youtube
        self._views = views
        self._clock = clock
        self._run_in_background = run_in_background
        self._after_check = after_check
        self._wake = threading.Condition()
        self._waiting: deque[_Request] = deque()
        self._running: _Request | None = None
        self._cancelled: set[str] = set()
        self._stopped = False

    def start(self) -> None:
        """Start the worker, and take up the first listings that a quit interrupted (R-CH-11)."""
        self._youtube.when_asking_again(self.resume_first_listings)
        self._run_in_background(self._work_until_stopped)
        self.resume_first_listings()

    def stop(self) -> None:
        """Stop the worker. A check that is running ends at the next video and stores nothing."""
        with self._wake:
            self._stopped = True
            self._wake.notify_all()

    def request_check(
        self,
        channel_id: str,
        kind: CheckKind,
        *,
        by_user: bool = True,
        preview_count: int | None = None,
    ) -> None:
        """Put a check of a channel in line (R-CH-23).

        A channel that was never listed gets its first listing, whatever was
        asked for. A check of a channel that already waits or runs is not put
        in line twice. A quick check that waits becomes a full one when a full
        one is asked for.

        Args:
            channel_id: The channel ID.
            kind: A quick or a full check.
            by_user: Whether the user started it. Otherwise a pause of the app holds it up.
            preview_count: For a first listing, the video count the preview showed.

        Raises:
            AppError: ``NOT_FOUND`` for an unknown channel. ``INVALID_REQUEST`` for
                a paused channel: it is not checked, by hand either (R-CH-31).
        """
        channel = self._repository.channel(channel_id)
        if channel is None:
            raise AppError(ErrorCode.NOT_FOUND, {"channel": channel_id})
        if channel.paused:
            raise AppError(ErrorCode.INVALID_REQUEST, {"reason": "paused", "channel": channel_id})
        if channel.first_listed_at is None:
            kind = CheckKind.FULL
        request = _Request(channel_id, kind, by_user, preview_count)
        with self._wake:
            if not self._put_in_line(request):
                return
            self._wake.notify_all()
        self._views.set_checking(channel_id, True)

    def request_check_all(self) -> int:
        """Put a quick check of every channel that is not paused in line (R-CH-23).

        Returns:
            How many channels are checked.
        """
        channels = [channel for channel in self._repository.channels() if not channel.paused]
        for channel in channels:
            self.request_check(channel.id, CheckKind.QUICK)
        return len(channels)

    def resume_first_listings(self) -> None:
        """Put the first listing of every channel in line that has none yet (R-CH-11).

        A channel whose first listing failed is left to the user: its error
        and "Try again" are on its page (R-CH-25).
        """
        for channel in self._repository.channels():
            if channel.first_listed_at is None and channel.last_check_error is None:
                self.request_check(channel.id, CheckKind.FULL, by_user=False)

    def cancel(self, channel_id: str) -> bool:
        """Cancel the full check of a channel that waits or runs (R-CH-27).

        A first listing cannot be cancelled: it ends only with the channel.

        Args:
            channel_id: The channel ID.

        Returns:
            Whether there was a check to cancel.
        """
        channel = self._repository.channel(channel_id)
        if channel is None or channel.first_listed_at is None:
            return False
        return self._drop(channel_id)

    def forget(self, channel_id: str) -> None:
        """Drop every check of a channel, because the channel is paused or removed.

        Args:
            channel_id: The channel ID.
        """
        self._drop(channel_id)

    def work_once(self) -> bool:
        """Run the next check that waits, if there is one.

        Returns:
            Whether a check ran.
        """
        with self._wake:
            if not self._waiting:
                return False
            request = self._waiting.popleft()
            self._running = request
            self._cancelled.discard(request.channel_id)
        try:
            self._check(request)
        finally:
            with self._wake:
                self._running = None
                self._cancelled.discard(request.channel_id)
            self._views.set_checking(request.channel_id, False)
        return True

    def _work_until_stopped(self) -> None:
        while True:
            with self._wake:
                self._wake.wait_for(lambda: self._stopped or bool(self._waiting))
                if self._stopped:
                    return
            self.work_once()

    def _put_in_line(self, request: _Request) -> bool:
        """Add a request unless its channel is in line already. Call with the lock held."""
        if self._running is not None and self._running.channel_id == request.channel_id:
            return False
        for index, waiting in enumerate(self._waiting):
            if waiting.channel_id == request.channel_id:
                if waiting.kind is CheckKind.QUICK and request.kind is CheckKind.FULL:
                    self._waiting[index] = request
                return False
        self._waiting.append(request)
        return True

    def _drop(self, channel_id: str) -> bool:
        with self._wake:
            waiting = [request for request in self._waiting if request.channel_id == channel_id]
            for request in waiting:
                self._waiting.remove(request)
            running = self._running is not None and self._running.channel_id == channel_id
            if running:
                self._cancelled.add(channel_id)
        if waiting and not running:
            self._views.set_checking(channel_id, False)
        return bool(waiting) or running

    def _check(self, request: _Request) -> None:
        """Run one check from its first log line to its last. Nothing is raised."""
        channel = self._repository.channel(request.channel_id)
        if channel is None or channel.paused:
            return
        started = self._clock.monotonic()
        kind = request.kind.value
        log = _log.bind(channel_id=channel.id, kind=kind)
        log.info(
            "check.started", msg="Check started", first_listing=channel.first_listed_at is None
        )
        try:
            changes = self._read_and_store(channel, request)
        except _CancelledError:
            log.info("check.cancelled", msg="Check cancelled. Nothing was changed")
        except AppError as error:
            self._failed(channel, error, kind)
        except Exception:
            log.error(
                "check.failed",
                msg="Check failed with an unexpected error",
                error_code=ErrorCode.INTERNAL.value,
                exc_info=True,
            )
            self._repository.save_channel(replace(channel, last_check_error=ErrorCode.INTERNAL))
        else:
            if changes is not None:
                log.info(
                    "check.finished",
                    msg="Check finished",
                    new=changes.new,
                    updated=changes.changed,
                    gone=changes.removed,
                    returned=changes.returned,
                    read=changes.read,
                    inserted=len(changes.inserted),
                    duration_ms=round((self._clock.monotonic() - started) * 1000),
                )

    def _read_and_store(self, channel: Channel, request: _Request) -> CheckChanges | None:
        first_listing = channel.first_listed_at is None
        known = self._repository.videos(channel.id)
        listing = self._youtube.list_channel(channel.id, by_user=request.by_user)
        if request.kind is CheckKind.QUICK:
            read = read_for_quick_check(listing.videos, {video.id for video in known})
        else:
            read = self._read_all(listing, channel.id, first_listing, len(known) or None)
        if listing_is_implausible(request.kind, len(known), len(read)):
            raise AppError(
                ErrorCode.YOUTUBE_CHANGED,
                {"message": "The listing came back empty for a channel that has videos"},
            )
        now = int(self._clock.now().timestamp())
        changes = changes_of_check(
            request.kind, known, read, channel_id=channel.id, now=now, first_listing=first_listing
        )
        checked = replace(
            channel,
            title=listing.facts.title or channel.title,
            handle=listing.facts.handle or channel.handle,
            avatar_url=listing.facts.avatar_url or channel.avatar_url,
            last_check_at=now,
            last_check_error=None,
            last_full_check_at=now
            if request.kind is CheckKind.FULL
            else channel.last_full_check_at,
            first_listed_at=now if first_listing else channel.first_listed_at,
        )
        if not self._repository.apply_check(checked, changes):
            return None
        if first_listing and request.preview_count not in (None, len(changes.inserted)):
            _log.info(
                "channel.count_differs",
                msg="The first listing found another number of videos than the preview showed",
                channel_id=channel.id,
                preview_count=request.preview_count,
                listed=len(changes.inserted),
            )
        if self._after_check is not None:
            self._after_check(channel.id, request.kind)
        return changes

    def _read_all(
        self, listing: ChannelListing, channel_id: str, first_listing: bool, total: int | None
    ) -> list[ListedVideo]:
        """Read a whole listing, telling the progress after every page (R-CH-11, R-CH-27)."""
        kind = TaskKind.FIRST_LISTING if first_listing else TaskKind.FULL_CHECK
        self._views.set_progress(TaskProgress(channel_id, kind, 0, total))
        read: list[ListedVideo] = []
        for video in listing.videos:
            with self._wake:
                if self._stopped or channel_id in self._cancelled:
                    raise _CancelledError
            read.append(video)
            if len(read) % PROGRESS_EVERY == 0:
                self._views.set_progress(TaskProgress(channel_id, kind, len(read), total))
        with self._wake:
            if self._stopped or channel_id in self._cancelled:
                raise _CancelledError
        return read

    def _failed(self, channel: Channel, error: AppError, kind: str) -> None:
        """Log a failed check, and leave its code on the channel (R-CH-25).

        The "not a bot" check is a condition of the whole app, not of this
        channel (R-ER-05): the channel gets no error, and the checks that
        still wait are dropped, because they would be refused as well.
        """
        _log.warning(
            "check.failed",
            msg="Check failed. The catalogue stays as it was",
            channel_id=channel.id,
            kind=kind,
            error_code=error.code.value,
            **error.details,
        )
        if error.code is not ErrorCode.BOT_CHECK:
            self._repository.save_channel(replace(channel, last_check_error=error.code))
            return
        with self._wake:
            dropped = list(self._waiting)
            self._waiting.clear()
        for request in dropped:
            self._views.set_checking(request.channel_id, False)
