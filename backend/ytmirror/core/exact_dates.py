"""Rules of the exact-date fetch: what a video's date shows, retries, the rate and the time left.

Implements the rules of R-DT-06, R-DT-13, R-DT-14 and R-DT-15 that need no
storage and no clock. A video without an exact date is waiting, updating or
unavailable (R-DT-13). A lookup that fails for one video is tried again
after an hour, then six hours, then once a day. The time left comes only
from the rate measured while the fetch runs (R-DT-14), and above 10 minutes
without a key the key is offered (R-DT-15).

This module must not read a clock: every time is passed in.

Tests: backend/tests/unit/core/test_exact_dates.py
"""

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from ytmirror.core.errors import ErrorCode

RETRY_AFTER_S = (60 * 60, 6 * 60 * 60, 24 * 60 * 60)
"""When a lookup that failed for one video is tried again: after its first, second and
every later failure."""

OFFER_KEY_ABOVE_S = 10 * 60
"""Above this time left, a channel without a key offers the key (R-DT-15)."""

SAMPLES = 20
"""How many finished lookups the rate is measured over."""

ENOUGH_SAMPLES = 5
"""How many finished lookups it takes before a time left is shown (R-DT-14)."""

VIDEO_FAILURES = frozenset(
    {
        ErrorCode.VIDEO_PRIVATE,
        ErrorCode.VIDEO_REMOVED,
        ErrorCode.MEMBERS_ONLY,
        ErrorCode.AGE_RESTRICTED,
        ErrorCode.GEO_BLOCKED,
        ErrorCode.NOT_YET_AVAILABLE,
        ErrorCode.NO_FORMATS,
    }
)
"""Failures that concern one video. Every other failure holds the whole fetch back."""


class DateState(StrEnum):
    """What the approximate date of a video shows (R-DT-13)."""

    WAITING = "waiting"
    UPDATING = "updating"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class FetchState:
    """What the fetch remembers of one video without an exact date.

    Attributes:
        attempts: How many lookups of it failed in a row.
        next_try_at: When it may be looked up again, or None.
        last_error: Why the last lookup failed, or None.
    """

    attempts: int = 0
    next_try_at: int | None = None
    last_error: ErrorCode | None = None


@dataclass(frozen=True, slots=True)
class PendingDate:
    """A video whose exact date the fetch may look up now.

    Attributes:
        video_id: The video.
        channel_id: Its channel.
        urgent: Whether a decision waits for its date (R-MI-03): then it is looked up
            while downloads run too, within the lookup budget (D-090).
    """

    video_id: str
    channel_id: str
    urgent: bool = False


@dataclass(frozen=True, slots=True)
class DateShown:
    """What the date of one video shows while it is not exact (R-DT-13).

    Attributes:
        state: Waiting, updating or unavailable.
        reason: Why it is unavailable, or None.
        retry_at: When it is tried again, for an unavailable date, or None.
    """

    state: DateState
    reason: ErrorCode | None = None
    retry_at: int | None = None


@dataclass(frozen=True, slots=True)
class FetchHold:
    """Why the whole fetch is held back, and until when (R-FB-01).

    Attributes:
        reason: ``BOT_CHECK`` for the pause of the whole app, or the code of the
            failure that started the fetch's own back-off.
        until: When it is tried again, or None when it is not known.
    """

    reason: ErrorCode
    until: int | None


class KeyStatus(StrEnum):
    """How the optional API key stands (R-DT-12)."""

    NONE = "none"
    SAVED = "saved"
    UNREADABLE = "unreadable"
    INVALID = "invalid"
    QUOTA_EXCEEDED = "quota_exceeded"


@dataclass(frozen=True, slots=True)
class KeyState:
    """How the optional API key stands, for the key setting and the notice (R-DT-12).

    Attributes:
        status: Whether a key is saved, and whether it fails.
        until: Until when the app does without a key that failed, or None when it is
            until the key is saved again.
    """

    status: KeyStatus
    until: int | None = None

    @property
    def failing(self) -> bool:
        """Whether a saved key is not working: unreadable, invalid or out of quota."""
        return self.status in (KeyStatus.UNREADABLE, KeyStatus.INVALID, KeyStatus.QUOTA_EXCEEDED)


NO_KEY = KeyState(KeyStatus.NONE)
"""No key is saved."""


@dataclass(frozen=True, slots=True)
class KeyStateChanged:
    """Event: how the API key stands changed (R-DT-12).

    Attributes:
        key: How it stands now.
    """

    key: KeyState


@dataclass(frozen=True, slots=True)
class ExactDatesProgress:
    """How far the exact dates of one channel are (R-FB-01, R-DT-14, R-DT-15).

    Attributes:
        done: How many dates were found since the channel last had none waiting.
        total: How many there are in all since then.
        left_s: The measured time left, or None while it is not known.
        offer_key: Whether the channel offers the key.
    """

    done: int
    total: int
    left_s: int | None = None
    offer_key: bool = False


def retry_after_s(attempts: int) -> int:
    """Return how long a video waits after its ``attempts``-th failed lookup in a row."""
    return RETRY_AFTER_S[min(max(attempts, 1), len(RETRY_AFTER_S)) - 1]


def date_shown(
    state: FetchState | None, *, updating: bool, hold: FetchHold | None, now: int
) -> DateShown:
    """Return what the date of a video without an exact date shows (R-DT-13).

    Args:
        state: What the fetch remembers of the video, or None.
        updating: Whether the video is being looked up now.
        hold: Why the whole fetch is held back, or None.
        now: The time now.
    """
    if updating:
        return DateShown(DateState.UPDATING)
    if (
        state is not None
        and state.last_error is not None
        and state.next_try_at is not None
        and state.next_try_at > now
    ):
        return DateShown(DateState.UNAVAILABLE, state.last_error, state.next_try_at)
    if hold is not None:
        return DateShown(DateState.UNAVAILABLE, hold.reason, hold.until)
    return DateShown(DateState.WAITING)


class RateMeter:
    """Measures how long the fetch takes per video, waits included (R-DT-14).

    Not safe for threads: the caller holds a lock.
    """

    def __init__(self) -> None:
        """Measure nothing yet."""
        self._finished: deque[float] = deque(maxlen=SAMPLES)

    def finished(self, at: float) -> None:
        """Note that the lookup of one video ended, at a monotonic time."""
        self._finished.append(at)

    def restart(self) -> None:
        """Forget what was measured, for example after a pause of the fetch."""
        self._finished.clear()

    def seconds_per_video(self) -> float | None:
        """Return the measured time per video, or None before enough lookups ended."""
        if len(self._finished) < ENOUGH_SAMPLES:
            return None
        return (self._finished[-1] - self._finished[0]) / (len(self._finished) - 1)


def time_left_s(order: Sequence[str], seconds_per_video: float | None) -> Mapping[str, int]:
    """Return how long it takes until the last waiting video of each channel has its date.

    Args:
        order: The channel of every video that waits, in the order of the fetch.
        seconds_per_video: The measured rate, or None.

    Returns:
        Seconds by channel, for the channels with waiting videos; empty without a rate.
    """
    if seconds_per_video is None:
        return {}
    last: dict[str, int] = {}
    for place, channel_id in enumerate(order):
        last[channel_id] = place
    return {channel: round((place + 1) * seconds_per_video) for channel, place in last.items()}


def offers_key(left_s: int | None, *, key_works: bool) -> bool:
    """Return whether a channel offers the key: over 10 minutes left and no working key."""
    return not key_works and left_s is not None and left_s > OFFER_KEY_ABOVE_S
