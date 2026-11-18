"""The exact-date fetch: exact published times for the videos that have only approximate ones.

Implements R-DT-05, R-DT-06 and R-DT-12 (docs/DECISIONS.md D-082 to D-085).
With a key that works, the videos are asked of the YouTube API by ID, 50 at
a time; a video the API leaves out keeps its date and waits for the next
check of its channel. Without a key, or while the key fails, the videos are
looked up one at a time through yt-dlp, within the budget of lookups that
downloads share (``YouTubeAccess``): only while no download waits or runs,
never during the pause of the whole app (R-ER-05), and not during the
fetch's own back-off after YouTube asked it to slow down. The order is the
order of the repository: videos a decision waits for, then the newest.

The key is read from its store only when the fetch first needs it. A key
that cannot be read, is refused or has used up its quota is done without,
with no dialog: the key setting and a notice by the progress say so, with
until when (R-DT-12). An unreadable key is logged once.

The scheduler runs the fetch (``services/scheduler.py``): ``step`` does
one piece of work and says how long to wait before the next; ``wake`` ends
the wait early, for example after a check, when the last download ended or
when the pause of YouTube is over. Tests call ``step`` themselves.

Tests: backend/tests/unit/services/test_dates.py
"""

import datetime
import threading
import zoneinfo
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import structlog
from structlog.typing import FilteringBoundLogger

from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.exact_dates import (
    VIDEO_FAILURES,
    FetchHold,
    KeyState,
    KeyStateChanged,
    KeyStatus,
    PendingDate,
    RateMeter,
    retry_after_s,
    time_left_s,
)
from ytmirror.core.pauses import next_pause_s
from ytmirror.ports.api_key_store import ApiKeyStore
from ytmirror.ports.clock import Clock
from ytmirror.ports.date_repository import DateRepository
from ytmirror.ports.exact_date_source import MOST_IDS_PER_REQUEST, ExactDateSource
from ytmirror.services.date_fetch_state import DateFetchState
from ytmirror.services.download_state import DownloadState
from ytmirror.services.events import EventBus
from ytmirror.services.settings import SettingsService
from ytmirror.services.youtube_access import YouTubeAccess

_log: FilteringBoundLogger = structlog.get_logger(__name__)

IDLE_S = 60 * 60.0
"""How long the fetch waits when nothing is to be done, unless it is woken earlier."""

URGENT_RETRY_S = 60.0
"""How soon the fetch looks again when a date a decision waits for finds no room."""

_API_FIRST_BACKOFF_S = 60
_API_LONGEST_BACKOFF_S = 30 * 60
_QUOTA_ZONE = zoneinfo.ZoneInfo("America/Los_Angeles")
"""The daily quota of the YouTube API starts anew at midnight Pacific time."""


@dataclass(frozen=True, slots=True)
class KeyTest:
    """The answer of "Test key" (R-DT-12).

    Attributes:
        works: Whether the API answered.
        code: Why not, or None.
    """

    works: bool
    code: ErrorCode | None = None


def next_quota_reset(now: int) -> int:
    """Return when the daily quota of the YouTube API starts anew: the next midnight Pacific time.

    Args:
        now: The time now, in seconds since the Unix epoch.
    """
    local = datetime.datetime.fromtimestamp(now, _QUOTA_ZONE)
    tomorrow = local.date() + datetime.timedelta(days=1)
    return int(datetime.datetime.combine(tomorrow, datetime.time(), _QUOTA_ZONE).timestamp())


class DatesService:
    """Looks up exact dates in the background, with the key or without."""

    def __init__(
        self,
        *,
        dates: DateRepository,
        youtube: YouTubeAccess,
        api: ExactDateSource,
        keys: ApiKeyStore,
        settings: SettingsService,
        downloads: DownloadState,
        state: DateFetchState,
        clock: Clock,
        events: EventBus,
        register_secret: Callable[[str], None],
        tell_video: Callable[[str], None],
        tell_channel: Callable[[str], None],
        found_exact: Callable[[str], None] = lambda video_id: None,
        look_up: bool = True,
    ) -> None:
        """Create the service.

        Args:
            dates: The videos that wait for an exact date.
            youtube: Every question to YouTube, with the budget of lookups.
            api: The YouTube API, for a key.
            keys: Where the key is kept.
            settings: The general settings: whether to look up without a key.
            downloads: The downloads that wait or run: the fetch yields to them.
            state: What the views read about the fetch.
            clock: The source of time.
            events: Where a change of the key is published.
            register_secret: Makes the key a secret of the logs (R-LG-07).
            tell_video: Tells the interface how a video is now.
            tell_channel: Tells the interface how a channel is now.
            found_exact: Called with a video that just got its exact time, so that
                the dates of its file are repaired if it has one (R-DT-09).
            look_up: False to never look dates up without a key. Only for an app on the
                fake YouTube whose tests ask for that (``YTM_FAKE_LOOKUPS_PER_HOUR=0``).
        """
        self._dates = dates
        self._youtube = youtube
        self._api = api
        self._keys = keys
        self._settings = settings
        self._downloads = downloads
        self._state = state
        self._clock = clock
        self._events = events
        self._register_secret = register_secret
        self._tell_video = tell_video
        self._tell_channel = tell_channel
        self._found_exact = found_exact
        self._look_up_allowed = look_up
        self._lock = threading.Lock()
        self._waker: Callable[[], None] = lambda: None
        self._key: str | None = None
        self._key_read = False
        self._key_failure: tuple[KeyStatus, int | None] | None = None
        self._backoff: tuple[ErrorCode, int, int] | None = None
        """The fetch's own back-off: why, until when, and its length."""
        self._api_backoff: tuple[int, int] | None = None
        self._meter = RateMeter()
        self._state.set_key(self._key_state())
        youtube.when_asking_again(self.wake)
        downloads.when_idle(self.wake)

    # --- waking the scheduler

    def connect_waker(self, waker: Callable[[], None]) -> None:
        """Tell the fetch how to end the wait of the scheduler that runs it."""
        self._waker = waker

    def wake(self) -> None:
        """End the wait of the fetch: there may be work, or work that was held may go on."""
        self._waker()

    # --- one piece of work

    def step(self) -> float | None:
        """Do one piece of work: one request of the API, or one lookup.

        Returns:
            Seconds to wait before the next piece, 0 to go on at once, or None to
            wait until woken (or an hour at most).
        """
        self._youtube.log_finished_hour()
        now = self._now()
        if not self._dates.pending(now, limit=1, by_api=False):
            # Nothing waits: the key is not even read (D-085).
            self._hold(None)
            self._refresh(now, by_api=False)
            return IDLE_S
        key = self._working_key(now)
        self._refresh(now, by_api=key is not None)
        if key is not None:
            self._show_active(active=True)
            return self._ask_api(key, now)
        return self._look_up(now)

    def _ask_api(self, key: str, now: int) -> float | None:
        if self._api_backoff is not None and self._api_backoff[0] > now:
            self._hold(FetchHold(ErrorCode.NETWORK_UNREACHABLE, self._api_backoff[0]))
            return self._api_backoff[0] - now
        self._hold(None)
        batch = self._dates.pending(now, limit=MOST_IDS_PER_REQUEST, by_api=True)
        if not batch:
            return None
        ids = [entry.video_id for entry in batch]
        self._updating(batch, updating=True)
        try:
            try:
                found = self._api.video_dates(key, ids)
            except AppError as error:
                return self._api_failed(error, now)
            self._api_backoff = None
            stored = 0
            for entry in batch:
                published = found.get(entry.video_id)
                if published is not None and self._dates.set_exact(entry.video_id, published):
                    stored += 1
                    self._state.found(entry.channel_id)
                    self._found_exact(entry.video_id)
            left_out = [video_id for video_id in ids if found.get(video_id) is None]
            if left_out:
                self._dates.left_out(left_out, now)
            _log.info(
                "dates.fetch.batch",
                msg="The YouTube API gave exact dates",
                asked=len(ids),
                stored=stored,
                left_out=len(left_out),
            )
        finally:
            # Whatever happened, no video is shown as being fetched any more.
            self._updating(batch, updating=False)
        self._refresh(self._now(), by_api=True)
        return 0

    def _api_failed(self, error: AppError, now: int) -> float | None:
        if error.code in (ErrorCode.API_KEY_INVALID, ErrorCode.API_QUOTA_EXCEEDED):
            if error.code is ErrorCode.API_KEY_INVALID:
                failure = (KeyStatus.INVALID, None)
            else:
                failure = (KeyStatus.QUOTA_EXCEEDED, next_quota_reset(now))
            self._key_fails(*failure)
            _log.warning(
                "dates.source_fell_back",
                msg="The API key does not work now; exact dates are looked up without it",
                error_code=error.code.value,
                until=failure[1],
                reason=error.details.get("reason", ""),
            )
            return 0
        length = (
            _API_FIRST_BACKOFF_S
            if self._api_backoff is None
            else min(self._api_backoff[1] * 2, _API_LONGEST_BACKOFF_S)
        )
        self._api_backoff = (now + length, length)
        self._hold(FetchHold(error.code, now + length))
        _log.warning(
            "dates.fetch.backoff",
            msg="The YouTube API could not be asked; it is asked again later",
            error_code=error.code.value,
            source="api",
            pause_s=length,
        )
        return length

    def _look_up(self, now: int) -> float | None:
        if not self._look_up_allowed or not self._settings.current().fetch_exact_dates:
            self._show_active(active=False)
            self._hold(None)
            self._refresh(now, by_api=False)
            return None
        self._show_active(active=True)
        pause = self._youtube.pause()
        if pause is not None:
            self._hold(FetchHold(ErrorCode.BOT_CHECK, pause.until))
            self._meter.restart()
            return None
        if self._backoff is not None and self._backoff[1] > now:
            self._hold(FetchHold(self._backoff[0], self._backoff[1]))
            return self._backoff[1] - now
        self._hold(None)
        if self._downloads.busy():
            # Downloads go first. Only a date a decision waits for is looked up meanwhile,
            # when the budget has room, so that the decision is not held up (R-MI-03, D-090).
            batch = self._dates.pending(now, limit=1, by_api=False)
            if not batch or not batch[0].urgent:
                return None
            if self._youtube.download_room() <= 0:
                return URGENT_RETRY_S
        else:
            wait_s = self._youtube.exact_date_wait_s()
            if wait_s > 0:
                return wait_s
            batch = self._dates.pending(now, limit=1, by_api=False)
        if not batch:
            self._refresh(now, by_api=False)
            return IDLE_S
        entry = batch[0]
        self._updating(batch, updating=True)
        try:
            try:
                published = self._youtube.exact_date(entry.video_id)
            except AppError as error:
                self._updating(batch, updating=False)
                return self._lookup_failed(entry, error, now)
            self._backoff = None
            self._meter.finished(self._clock.monotonic())
            if published is None:
                self._dates.failed(entry.video_id, ErrorCode.NOT_YET_AVAILABLE, now, retry_after_s)
            elif self._dates.set_exact(entry.video_id, published):
                self._state.found(entry.channel_id)
                self._found_exact(entry.video_id)
                _log.debug("dates.fetched", msg="An exact date was found", video_id=entry.video_id)
        finally:
            # Whatever happened, the video is no longer shown as being fetched.
            if self._state.updating(entry.video_id):
                self._updating(batch, updating=False)
        self._refresh(self._now(), by_api=False)
        return 0

    def _lookup_failed(self, entry: PendingDate, error: AppError, now: int) -> float | None:
        if error.code is ErrorCode.BOT_CHECK:
            # The pause of the whole app began, or was in force: its end wakes the fetch.
            pause = self._youtube.pause()
            self._hold(FetchHold(ErrorCode.BOT_CHECK, None if pause is None else pause.until))
            self._meter.restart()
            return None
        if error.code in VIDEO_FAILURES:
            self._meter.finished(self._clock.monotonic())
            state = self._dates.failed(entry.video_id, error.code, now, retry_after_s)
            _log.info(
                "dates.lookup_failed",
                msg="The exact date of a video could not be looked up; it is tried again later",
                video_id=entry.video_id,
                error_code=error.code.value,
                attempts=state.attempts,
                next_try_at=state.next_try_at,
            )
            self._tell_video(entry.video_id)
            self._refresh(self._now(), by_api=False)
            return 0
        length = next_pause_s(None if self._backoff is None else self._backoff[2])
        self._backoff = (error.code, now + length, length)
        self._meter.restart()
        self._hold(FetchHold(error.code, now + length))
        _log.warning(
            "dates.fetch.backoff",
            msg="YouTube did not answer the exact-date lookups; they wait",
            error_code=error.code.value,
            source="lookup",
            pause_s=length,
        )
        return length

    # --- the key (R-DT-12)

    def key_state(self) -> KeyState:
        """Return how the API key stands, for the key setting."""
        return self._state.key()

    def save_key(self, key: str) -> KeyState:
        """Save a new key in place of the old one, and use it from now on.

        Args:
            key: The key as the user pasted it.

        Raises:
            AppError: ``INVALID_REQUEST`` for an empty key or one with spaces inside,
                ``API_KEY_UNREADABLE`` when it cannot be written.
        """
        key = _cleaned(key)
        self._register_secret(key)
        self._keys.write(key)
        with self._lock:
            self._key, self._key_read, self._key_failure = key, True, None
            self._api_backoff = None
        _log.info("apikey.saved", msg="An API key was saved")
        self._publish_key()
        self.wake()
        return self.key_state()

    def remove_key(self) -> KeyState:
        """Remove the key: exact dates are looked up without it (R-DT-12).

        The key leaves the memory of the app whatever deleting its files does.
        """
        try:
            self._keys.remove()
        finally:
            with self._lock:
                self._key, self._key_read, self._key_failure = None, True, None
            self.tidy_key_store()
        _log.info("apikey.removed", msg="The API key was removed")
        self._publish_key()
        self.wake()
        return self.key_state()

    def test_key(self, key: str | None = None) -> KeyTest:
        """Ask the YouTube API once with a key, the saved one when none is given.

        A saved key that passes is used again at once, whatever failed before.

        Args:
            key: The key as the user pasted it, or None for the saved key.

        Raises:
            AppError: ``INVALID_REQUEST`` for a key that is no key, or when none is given
                or saved.
        """
        saved = key is None
        if key is None:
            self._working_key(self._now(), ignore_failure=True)
            key = self._key
            if key is None:
                raise AppError(ErrorCode.INVALID_REQUEST, {"message": "no key is saved"})
        key = _cleaned(key)
        self._register_secret(key)
        try:
            self._api.test_key(key)
        except AppError as error:
            _log.info(
                "apikey.tested",
                msg="An API key was tested",
                works=False,
                error_code=error.code.value,
                saved=saved,
            )
            return KeyTest(works=False, code=error.code)
        _log.info("apikey.tested", msg="An API key was tested", works=True, saved=saved)
        if saved or key == self._key:
            with self._lock:
                self._key_failure = None
                self._api_backoff = None
            self._publish_key()
            self.wake()
        return KeyTest(works=True)

    def tidy_key_store(self) -> None:
        """Delete the copies of a key an interrupted save left. Called once at the start."""
        try:
            self._keys.clean_leftovers()
        except OSError as error:
            _log.warning(
                "apikey.leftover_kept", msg="A left copy of a key was not deleted", error=str(error)
            )

    def prioritize(self, video_ids: Sequence[str]) -> None:
        """Put videos at the front of the fetch: a decision waits for their date (R-MI-03).

        Args:
            video_ids: The videos.
        """
        self._dates.prioritize(video_ids)
        self.wake()

    def _working_key(self, now: int, *, ignore_failure: bool = False) -> str | None:
        """Return the key when it can be used now, reading it the first time it is needed."""
        expired = False
        with self._lock:
            failure = self._key_failure
            if failure is not None and failure[1] is not None and failure[1] <= now:
                self._key_failure = failure = None
                expired = True
                if self._key is None:
                    self._key_read = False
            known = self._key_read
            key = self._key
        if expired:
            # The quota started anew: the key setting and the notice say so at once.
            self._publish_key()
        if failure is not None and not ignore_failure:
            return None
        if known:
            return key
        try:
            key = self._keys.read()
        except AppError as error:
            with self._lock:
                self._key_read = True
            self._key_fails(KeyStatus.UNREADABLE, None)
            _log.warning(
                "apikey.unreadable",
                msg="An API key is saved but cannot be read; exact dates are looked up without it",
                error_code=error.code.value,
                error=error.details.get("error", ""),
            )
            return None
        if key is not None:
            self._register_secret(key)
        with self._lock:
            if self._key_read:
                # Saved or removed meanwhile: that is newer than what was read.
                return self._key
            self._key, self._key_read = key, True
        self._publish_key()
        return key

    def _key_fails(self, status: KeyStatus, until: int | None) -> None:
        with self._lock:
            self._key_failure = (status, until)
        self._publish_key()

    def _key_state(self) -> KeyState:
        with self._lock:
            if self._key_failure is not None:
                return KeyState(*self._key_failure)
            if self._key_read:
                return KeyState(KeyStatus.SAVED if self._key else KeyStatus.NONE)
        return KeyState(KeyStatus.SAVED if self._keys_saved() else KeyStatus.NONE)

    def _keys_saved(self) -> bool:
        try:
            return self._keys.is_saved()
        except OSError:
            return True

    def _publish_key(self) -> None:
        key = self._key_state()
        if self._state.set_key(key):
            self._events.publish(KeyStateChanged(key))
            for channel_id in self._state_channels():
                self._tell_channel(channel_id)

    # --- what the interface is told

    def _updating(self, batch: Sequence[PendingDate], *, updating: bool) -> None:
        self._state.set_updating([entry.video_id for entry in batch], updating)
        for entry in batch:
            self._tell_video(entry.video_id)

    def _hold(self, hold: FetchHold | None) -> None:
        if self._state.set_hold(hold):
            for channel_id in self._state_channels():
                self._tell_channel(channel_id)

    def _show_active(self, *, active: bool) -> None:
        if self._state.set_active(active):
            for channel_id in self._state_channels():
                self._tell_channel(channel_id)

    def _refresh(self, now: int, *, by_api: bool) -> None:
        order = self._dates.waiting_channels(now, by_api=by_api)
        left: Mapping[str, int] = (
            {} if by_api else time_left_s(order, self._meter.seconds_per_video())
        )
        for channel_id in self._state.waiting(order, left):
            self._tell_channel(channel_id)

    def _state_channels(self) -> list[str]:
        return list(dict.fromkeys(self._dates.waiting_channels(self._now(), by_api=False)))

    def _now(self) -> int:
        return int(self._clock.now().timestamp())


def _cleaned(key: str) -> str:
    """Return a pasted key without the spaces around it, or refuse what is no key."""
    key = key.strip()
    if not key or any(character.isspace() for character in key) or len(key) > 200:
        raise AppError(ErrorCode.INVALID_REQUEST, {"message": "the key is empty or has spaces"})
    return key
