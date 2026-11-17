"""The scheduler: all background work that runs by itself while the app is open.

Implements R-CH-20 to R-CH-22, R-CH-25 and R-CH-26, and runs the exact-date
fetch of R-DT-05 and R-DT-06 (docs/IMPLEMENTATION-PLAN.md, milestone M4).
When the app opens it checks all channels (setting, default on); a channel
selected more than 5 minutes after its last successful check is checked; all
channels are checked again on the interval (setting, default 30 minutes); a
failed check is tried again after 5, 15 and 60 minutes, then every hour; and
a full check runs by itself when the last one is older than the setting
(default 7 days), one channel at a time and never while downloads of that
channel wait or run. The rules of when are in ``core/schedule.py``.

Nothing is put in line while the app pauses what it asks of YouTube
(R-ER-05): a check the app starts by itself would only be refused, and its
refusal would drop the checks the user asked for. The end of the pause
wakes the scheduler.

One thread runs ``tick`` and waits until the next work is due or it is
woken. Tests call ``tick`` themselves, with a fake clock.

Tests: backend/tests/unit/services/test_scheduler.py
"""

import dataclasses
import threading

import structlog
from structlog.typing import FilteringBoundLogger

from ytmirror.core.channels import CheckKind, CheckTrigger
from ytmirror.core.errors import AppError
from ytmirror.core.schedule import full_check_due, is_stale, next_interval_check, retry_at
from ytmirror.ports.catalogue_repository import CatalogueRepository
from ytmirror.ports.clock import Clock
from ytmirror.services.catalogue import CatalogueService
from ytmirror.services.channel_views import ChannelViews
from ytmirror.services.dates import IDLE_S, DatesService
from ytmirror.services.download_state import DownloadState
from ytmirror.services.settings import SettingsService
from ytmirror.services.youtube_access import YouTubeAccess

_log: FilteringBoundLogger = structlog.get_logger(__name__)

BLOCKED_RETRY_S = 60.0
"""How soon a full check that downloads hold back is looked at again."""


class Scheduler:
    """Starts checks by themselves and runs the exact-date fetch."""

    def __init__(
        self,
        *,
        catalogue: CatalogueService,
        repository: CatalogueRepository,
        views: ChannelViews,
        settings: SettingsService,
        youtube: YouTubeAccess,
        downloads: DownloadState,
        dates: DatesService,
        clock: Clock,
    ) -> None:
        """Create the scheduler.

        Args:
            catalogue: Runs the checks.
            repository: The stored channels.
            views: Knows which channels are being checked.
            settings: The settings of checks.
            youtube: Its pause holds every check the app starts by itself.
            downloads: A full check waits while downloads of its channel wait or run.
            dates: The exact-date fetch, run by this scheduler.
            clock: The source of time.
        """
        self._catalogue = catalogue
        self._repository = repository
        self._views = views
        self._settings = settings
        self._youtube = youtube
        self._downloads = downloads
        self._dates = dates
        self._clock = clock
        self._wake = threading.Condition()
        self._woken = False
        self._stopped = False
        self._thread: threading.Thread | None = None
        self._opened = False
        self._last_all: int | None = None
        self._full: str | None = None
        self._dates_due = 0.0
        youtube.when_asking_again(self.wake)
        dates.connect_waker(self.wake)

    # --- the thread

    def start(self) -> None:
        """Start the scheduler on a thread of its own."""
        self._thread = threading.Thread(target=self._run, name="scheduler", daemon=True)
        self._thread.start()

    def stop(self, timeout_s: float = 5.0) -> None:
        """Stop the scheduler. A lookup of the exact-date fetch that runs is not interrupted."""
        with self._wake:
            self._stopped = True
            self._wake.notify_all()
        if self._thread is not None:
            self._thread.join(timeout_s)

    def wake(self) -> None:
        """Look at once whether work is due: the exact-date fetch may go on."""
        with self._wake:
            self._woken = True
            self._dates_due = 0.0
            self._wake.notify_all()

    def _run(self) -> None:
        while True:
            try:
                wait_s = self.tick()
            except Exception:  # noqa: BLE001  (the scheduler must outlive any fault, and say so)
                _log.exception("scheduler.failed", msg="The scheduler failed; it goes on")
                wait_s = BLOCKED_RETRY_S
            with self._wake:
                if self._stopped:
                    return
                if not self._woken and wait_s > 0:
                    self._wake.wait(wait_s)
                self._woken = False
                if self._stopped:
                    return

    # --- the work that is due

    def tick(self) -> float:
        """Start what is due now.

        Returns:
            Seconds until something is due again.
        """
        now = int(self._clock.now().timestamp())
        waits = [IDLE_S]
        if self._youtube.pause() is None:
            waits += self._checks(now)
        waits.append(self._run_dates())
        return max(0.0, min(waits))

    def channel_selected(self, channel_id: str) -> None:
        """Check a channel the user selected, when its last check is older than 5 minutes.

        Implements R-CH-21. Nothing happens while the app pauses what it asks of
        YouTube, or while a check of the channel waits or runs.

        Args:
            channel_id: The channel ID.
        """
        channel = self._repository.channel(channel_id)
        now = int(self._clock.now().timestamp())
        if (
            channel is None
            or not is_stale(channel, now)
            or self._views.is_checking(channel_id)
            or self._youtube.pause() is not None
        ):
            return
        _log.info("scheduler.selected", msg="A selected channel is checked", channel_id=channel_id)
        self._request(channel_id, CheckKind.QUICK, CheckTrigger.SCHEDULE)

    def _checks(self, now: int) -> list[float]:
        settings = self._settings.current()
        waits: list[float] = []
        if not self._opened:
            self._opened = True
            self._last_all = now
            if settings.check_on_open:
                self._check_all("open")
        assert self._last_all is not None
        due = next_interval_check(self._last_all, settings.recheck_interval_min)
        if due is not None and due <= now:
            self._last_all = now
            self._check_all("interval")
            due = next_interval_check(now, settings.recheck_interval_min)
        if due is not None:
            waits.append(due - now)
        waits += self._retries(now)
        waits += self._full_check(now, settings.full_check_days)
        return waits

    def _check_all(self, reason: str) -> None:
        count = self._catalogue.request_check_all(by_user=False)
        if count == 0:
            return
        _log.info(
            "scheduler.check_all",
            msg="All channels are checked by themselves",
            reason=reason,
            channels=count,
        )

    def _retries(self, now: int) -> list[float]:
        waits: list[float] = []
        for channel in self._repository.channels():
            at = retry_at(channel)
            if at is None or self._views.is_checking(channel.id):
                continue
            if at > now:
                waits.append(at - now)
                continue
            retried = dataclasses.replace(channel, check_retries=channel.check_retries + 1)
            self._repository.save_channel(retried)
            _log.info(
                "scheduler.retry",
                msg="A failed check is tried again",
                channel_id=channel.id,
                retry=retried.check_retries,
                error_code=None if channel.last_check_error is None else channel.last_check_error,
            )
            self._request(channel.id, CheckKind.QUICK, CheckTrigger.RETRY)
            # A view of the channel says when the next retry comes.
            self._views.publish(channel.id)
        return waits

    def _full_check(self, now: int, days: int) -> list[float]:
        if self._full is not None:
            if self._views.is_checking(self._full):
                return [BLOCKED_RETRY_S]
            self._full = None
        blocked = False
        for channel in self._repository.channels():
            if not full_check_due(channel, now, days) or self._views.is_checking(channel.id):
                continue
            if self._downloads.mirroring(channel.id) is not None:
                blocked = True
                continue
            _log.info(
                "scheduler.full_check",
                msg="A full check runs by itself",
                channel_id=channel.id,
                days=days,
            )
            self._full = channel.id
            self._request(channel.id, CheckKind.FULL, CheckTrigger.SCHEDULE)
            return [BLOCKED_RETRY_S]
        return [BLOCKED_RETRY_S] if blocked else []

    def _request(self, channel_id: str, kind: CheckKind, trigger: CheckTrigger) -> None:
        try:
            self._catalogue.request_check(channel_id, kind, by_user=False, trigger=trigger)
        except AppError as error:
            # Removed or paused in the meantime: nothing to check.
            _log.info(
                "scheduler.skipped",
                msg="A check by itself was not started",
                channel_id=channel_id,
                error_code=error.code.value,
            )

    def _run_dates(self) -> float:
        now = self._clock.monotonic()
        with self._wake:
            due = self._dates_due
        if due > now:
            return due - now
        wait_s = self._dates.step()
        waited = IDLE_S if wait_s is None else wait_s
        with self._wake:
            self._dates_due = self._clock.monotonic() + waited
        return waited
