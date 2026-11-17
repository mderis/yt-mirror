"""Everything the app asks of YouTube goes through here.

Implements R-ER-05 (docs/DECISIONS.md D-071). YouTube sometimes refuses
requests with its "not a bot" check, which depends on the network address
and not on the channel or the video. This module remembers that for the
whole app: what the app would ask by itself waits, first 15 minutes and
then twice as long each time. What the user starts by hand is still tried,
and the pause ends as soon as YouTube answers the kind of request it had
refused. An answer to another kind of request proves nothing: YouTube can
refuse lookups from an address and still answer listings.

It also keeps the budget of lookups of R-DT-06 (D-084): the metadata
lookup of every download and every lookup of the exact-date fetch are
counted, at most 300 an hour together. Downloads are never held back by it;
the exact-date fetch asks how long to wait before its next lookup. After a
"not a bot" check the budget is halved until midnight in the Mac's time
zone. The lookups of each hour are logged, so that real use shows whether
the number is right.

This module must not know what a request is for, only whether the user
started it and whether it is counted.

Tests: backend/tests/unit/services/test_youtube_access.py
"""

import datetime
import json
import threading
from collections.abc import Callable, Iterator, Mapping

import structlog
from structlog.typing import FilteringBoundLogger

from ytmirror.core.channels import (
    ChannelFacts,
    ChannelListing,
    ChannelReference,
    ListedVideo,
    YouTubePause,
    YouTubePauseChanged,
)
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.jobs import DownloadProgress, DownloadRequest, DownloadResult
from ytmirror.core.pacing import HourCounts, LookupBudget, LookupKind
from ytmirror.core.pauses import next_pause_s
from ytmirror.ports.app_meta_repository import AppMetaRepository
from ytmirror.ports.clock import Clock
from ytmirror.ports.youtube_gateway import YouTubeGateway
from ytmirror.services.events import EventBus

_log: FilteringBoundLogger = structlog.get_logger(__name__)

BUDGET_KEY = "lookup_budget"
"""Where the budget of lookups is kept in ``app_meta``, as JSON (R-DT-06)."""

type CallLater = Callable[[float, Callable[[], None]], None]
"""Runs something after a number of seconds, without blocking the caller."""


def next_local_midnight(now: datetime.datetime) -> float:
    """Return the next midnight in the Mac's time zone after ``now``, in seconds since the epoch.

    Args:
        now: A timezone-aware time.
    """
    tomorrow = now.astimezone().date() + datetime.timedelta(days=1)
    # A naive time is read in the Mac's time zone, with its summer time on that day.
    return datetime.datetime.combine(tomorrow, datetime.time()).astimezone().timestamp()


class YouTubeAccess:
    """Asks YouTube, and pauses the whole app when YouTube refuses it."""

    def __init__(
        self,
        gateway: YouTubeGateway,
        clock: Clock,
        events: EventBus,
        call_later: CallLater,
        *,
        budget: LookupBudget | None = None,
        midnight_after: Callable[[datetime.datetime], float] = next_local_midnight,
        memory: AppMetaRepository | None = None,
    ) -> None:
        """Create the access.

        Args:
            gateway: The gateway to YouTube.
            clock: The source of time.
            events: Where a change of the pause is published.
            call_later: Runs the end of a pause when its time has come.
            budget: The budget of lookups. Default: 300 an hour (D-084).
            midnight_after: Says when the day of a time ends, for the halved budget.
            memory: Where the budget is kept across restarts: the lookups of the last
                hour and the halving until midnight (R-DT-06).
        """
        self._gateway = gateway
        self._clock = clock
        self._events = events
        self._call_later = call_later
        self._lock = threading.Lock()
        self._pause: YouTubePause | None = None
        self._last_pause_s: int | None = None
        self._refused: str | None = None
        self._on_resume: list[Callable[[], None]] = []
        self._budget = budget if budget is not None else LookupBudget()
        self._midnight_after = midnight_after
        self._memory = memory
        self._restored = memory is None

    def pause(self) -> YouTubePause | None:
        """Return the pause that is in force, or None."""
        with self._lock:
            return self._pause

    def when_asking_again(self, work: Callable[[], None]) -> None:
        """Register work that the app does by itself and that a pause holds up.

        It runs when a pause ends: when its time has come, when YouTube
        answered something else, or when the user says "Try now".

        Args:
            work: What to do. It must come back quickly.
        """
        self._on_resume.append(work)

    def try_now(self) -> None:
        """End the pause because the user asked for it, and take up the work that waited."""
        self._end_pause("the user asked to try now")

    def exact_date_wait_s(self) -> float:
        """Return how long the exact-date fetch waits before its next lookup (R-DT-06)."""
        with self._lock:
            return self._budget_now().wait_s(self._now())

    def lookups_per_hour(self) -> int:
        """Return the budget of an hour as it is now: halved after a check (R-DT-06)."""
        with self._lock:
            return self._budget_now().limit(self._now())

    def exact_date(self, video_id: str) -> int | None:
        """Look up the exact published time of a video for the exact-date fetch (R-DT-05).

        The app asks this by itself: a pause holds it up, and it is counted in
        the budget. The caller waits ``exact_date_wait_s`` first.

        Args:
            video_id: The video ID.

        Returns:
            Seconds since the Unix epoch, or None for a video not released yet.

        Raises:
            AppError: ``BOT_CHECK`` without asking while the app pauses, or as the
                gateway raises it.
        """
        return self._ask(
            "exact_date",
            lambda: self._gateway.exact_date(video_id),
            by_user=False,
            counted=LookupKind.EXACT_DATE,
        )

    def log_finished_hour(self) -> None:
        """Log the lookups of the hour that ended, if it was not logged yet (R-DT-06)."""
        with self._lock:
            finished = self._budget.finish_hour(self._now())
        _log_hour(finished)

    def log_open_hour(self) -> None:
        """Log the lookups of the hour that is open. For the end of the app (R-DT-06)."""
        with self._lock:
            finished = self._budget.close(self._now())
        _log_hour(finished)

    def lookup_channel(self, reference: ChannelReference) -> ChannelFacts:
        """Look a channel up for the user. A pause does not hold this up.

        Args:
            reference: The channel as the user named it.

        Raises:
            AppError: As the gateway raises it.
        """
        return self._ask("lookup", lambda: self._gateway.lookup_channel(reference), by_user=True)

    def preview_video_count(self, channel_id: str) -> int:
        """Ask for the video count of a preview for the user.

        Args:
            channel_id: The channel ID.

        Raises:
            AppError: As the gateway raises it.
        """
        return self._ask(
            "count", lambda: self._gateway.preview_video_count(channel_id), by_user=True
        )

    def list_channel(self, channel_id: str, *, by_user: bool) -> ChannelListing:
        """Start a listing of a channel.

        Args:
            channel_id: The channel ID.
            by_user: Whether the user started the check. Otherwise a pause holds it up.

        Raises:
            AppError: ``BOT_CHECK`` without asking YouTube while the app pauses, or as
                the gateway raises it, here or while the videos are read.
        """
        listing = self._ask(
            "listing", lambda: self._gateway.list_channel(channel_id), by_user=by_user
        )
        return ChannelListing(listing.facts, self._watched(listing.videos))

    def fetch_image(self, url: str, *, by_user: bool = False) -> bytes:
        """Fetch a picture. Unless the user waits for it, a pause holds it up.

        Args:
            url: The address of the picture.
            by_user: Whether the user waits for this picture, as for the avatar of a preview.

        Raises:
            AppError: ``BOT_CHECK`` without asking while the app pauses, or as the
                gateway raises it.
        """
        return self._ask("image", lambda: self._gateway.fetch_image(url), by_user=by_user)

    def download(
        self,
        request: DownloadRequest,
        on_progress: Callable[[DownloadProgress], None],
        is_cancelled: Callable[[], bool],
        *,
        by_user: bool,
        start_writing: Callable[[], None] = lambda: None,
    ) -> DownloadResult:
        """Download one video. Unless the user started it, a pause holds it up (D-071).

        Args:
            request: What to download, and where to.
            on_progress: Told how far the download is.
            is_cancelled: Asked while the download runs.
            by_user: Whether the user started this download by hand.
            start_writing: Called right before the first file is written.

        Raises:
            AppError: ``BOT_CHECK`` without asking while the app pauses, or as the
                gateway raises it.
            DownloadCancelledError: When it was cancelled.
            SubtitlesFailedError: When only the subtitles failed.
        """
        return self._ask(
            "download",
            lambda: self._gateway.download(
                request,
                on_progress,
                is_cancelled,
                start_writing=start_writing,
                on_lookup_again=self._count_again,
            ),
            by_user=by_user,
            counted=LookupKind.DOWNLOAD,
        )

    def _now(self) -> float:
        return self._clock.now().timestamp()

    def _count_again(self) -> None:
        """Count a metadata lookup a download made again (R-DT-06, D-089)."""
        _log.info("youtube.lookup_again", msg="A download read the metadata of its video again")
        with self._lock:
            finished = self._budget_now().count(LookupKind.DOWNLOAD, self._now())
            saved = self._budget.saved()
        self._remember(saved)
        _log_hour(finished)

    def _budget_now(self) -> LookupBudget:
        """Return the budget, read back from where it was kept the first time it is needed.

        Not when the access is made: the database is brought up to date only after the
        container is built. The caller holds the lock.
        """
        if not self._restored and self._memory is not None:
            self._restored = True
            try:
                self._budget.restore(
                    json.loads(self._memory.get(BUDGET_KEY) or "null"), self._now()
                )
            except Exception:  # noqa: BLE001  (an unreadable budget only starts afresh)
                _log.warning("youtube.budget_unreadable", msg="The saved budget was not read")
        return self._budget

    def _remember(self, saved: Mapping[str, object]) -> None:
        """Keep the budget for the next start (R-DT-06). A failure only loses that."""
        if self._memory is None:
            return
        try:
            self._memory.put(BUDGET_KEY, json.dumps(saved))
        except Exception:  # noqa: BLE001  (a lookup never fails because the budget was not kept)
            _log.warning("youtube.budget_unsaved", msg="The budget of lookups was not kept")

    def _ask[T](
        self,
        request: str,
        ask: Callable[[], T],
        *,
        by_user: bool,
        counted: LookupKind | None = None,
    ) -> T:
        pause = self.pause()
        if pause is not None and not by_user:
            raise AppError(ErrorCode.BOT_CHECK, {"paused_until": str(pause.until)})
        if counted is not None:
            with self._lock:
                finished = self._budget_now().count(counted, self._now())
                saved = self._budget.saved()
            self._remember(saved)
            _log_hour(finished)
        try:
            answer = ask()
        except AppError as error:
            self._note_failure(request, error)
            raise
        self._note_answer(request)
        return answer

    def _watched(self, videos: Iterator[ListedVideo]) -> Iterator[ListedVideo]:
        """Hand the videos of a listing on, and see whether YouTube refuses part of the way."""
        try:
            yield from videos
        except AppError as error:
            self._note_failure("listing", error)
            raise

    def _note_failure(self, request: str, error: AppError) -> None:
        if error.code is not ErrorCode.BOT_CHECK:
            return
        now = self._clock.now()
        with self._lock:
            finished = self._budget_now().halve(now.timestamp(), self._midnight_after(now))
            length = next_pause_s(self._last_pause_s)
            self._last_pause_s = length
            self._refused = request
            self._pause = YouTubePause(
                ErrorCode.BOT_CHECK, int(self._clock.now().timestamp()) + length
            )
            pause = self._pause
        _log.warning(
            "youtube.paused",
            msg="YouTube asked to confirm that the app is not a bot. The app pauses",
            error_code=ErrorCode.BOT_CHECK.value,
            request=request,
            pause_s=length,
            until=pause.until,
        )
        with self._lock:
            saved = self._budget.saved()
        self._remember(saved)
        _log_hour(finished)
        self._events.publish(YouTubePauseChanged(pause))
        self._call_later(length, lambda: self._pause_is_over(pause))

    def _note_answer(self, request: str) -> None:
        """End the pause when YouTube answered the kind of request it had refused."""
        with self._lock:
            if self._refused != request:
                return
            self._last_pause_s = None
        self._end_pause("YouTube answered")

    def _pause_is_over(self, pause: YouTubePause) -> None:
        """End a pause when its time has come, unless a newer one took its place."""
        if self.pause() == pause:
            self._end_pause("the time of the pause is over")

    def _end_pause(self, reason: str) -> None:
        with self._lock:
            if self._pause is None:
                return
            self._pause = None
            self._refused = None
        _log.info("youtube.resumed", msg="The app asks YouTube again", reason=reason)
        self._events.publish(YouTubePauseChanged(None))
        for work in list(self._on_resume):
            work()


def _log_hour(counts: HourCounts | None) -> None:
    """Log the lookups of one hour, so that real use shows whether the budget is right."""
    if counts is None:
        return
    _log.info(
        "youtube.lookups.hour",
        msg="The lookups the app asked of YouTube in one hour",
        hour_start=counts.hour_start,
        exact_date=counts.exact_date,
        download=counts.download,
        bot_checks=counts.bot_checks,
        limit=counts.limit,
    )
