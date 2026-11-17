"""The budget of lookups the app asks of YouTube in an hour.

Implements the pace of R-DT-06 (docs/DECISIONS.md D-084). YouTube showed
its "not a bot" check after about 1,000 lookups in 25 minutes, with no
warning before it (OPEN-QUESTIONS Q-08). So every request that can bring
the check counts against one budget: the lookups of the exact-date fetch
and the metadata lookup of each download. Downloads are counted and never
held back; the exact-date fetch asks only when the budget has room, and its
lookups are spread over the hour instead of coming all at once. After a
"not a bot" check the budget is halved until the midnight the caller names.

The counts of each hour are kept apart, so the app can log them and real
use can show whether the number is right.

This module must not read a clock: every time is passed in, in seconds
since the Unix epoch.

Tests: backend/tests/unit/core/test_pacing.py
"""

from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import cast

LOOKUPS_PER_HOUR = 300
"""The budget of one hour. One value, so that a later release can change it (D-084)."""

HOUR_S = 3600


class LookupKind(StrEnum):
    """What a counted lookup was for."""

    EXACT_DATE = "exact_date"
    DOWNLOAD = "download"


@dataclass(frozen=True)
class HourCounts:
    """The lookups of one clock hour, for the log.

    Attributes:
        hour_start: The start of the hour, in seconds since the Unix epoch.
        exact_date: The lookups of the exact-date fetch.
        download: The metadata lookups of downloads.
        bot_checks: How many times YouTube showed its "not a bot" check.
        limit: The budget at the end of the hour.
    """

    hour_start: int
    exact_date: int
    download: int
    bot_checks: int
    limit: int


@dataclass
class _Hour:
    start: int
    counts: dict[LookupKind, int] = field(default_factory=lambda: dict.fromkeys(LookupKind, 0))
    bot_checks: int = 0


class LookupBudget:
    """Counts the lookups of the last hour and says when the next may be asked.

    Not safe for threads: the caller holds a lock.
    """

    def __init__(self, per_hour: int = LOOKUPS_PER_HOUR) -> None:
        """Create a budget.

        Args:
            per_hour: How many lookups an hour may have.
        """
        self._per_hour = per_hour
        self._recent: deque[float] = deque()
        self._last_fetch: float | None = None
        self._halved_until: float | None = None
        self._hour: _Hour | None = None

    def saved(self) -> dict[str, object]:
        """Return what must survive a restart: the lookups of the last hour and the halving."""
        return {"recent": list(self._recent), "halved_until": self._halved_until}

    def restore(self, saved: object, now: float) -> None:
        """Take back what ``saved`` gave, leaving out what cannot be read.

        What is over is left as it is: the count forgets lookups older than an
        hour, and a halving that ended no longer counts. A lookup that seems to
        come after ``now``, because the Mac's clock was set back, is left out:
        it would hold the budget until the clock caught up with it.

        Args:
            saved: The value ``saved`` returned before the restart.
            now: The time now.
        """
        if not isinstance(saved, dict):
            return
        values = cast(dict[str, object], saved)
        recent = values.get("recent")
        if isinstance(recent, list):
            times = [at for at in cast(list[object], recent) if isinstance(at, int | float)]
            self._recent = deque(sorted(float(at) for at in times if at <= now))
        halved = values.get("halved_until")
        if isinstance(halved, int | float):
            self._halved_until = float(halved)

    def limit(self, now: float) -> int:
        """Return the budget of an hour as it is now: halved after a check until its end."""
        if self._halved_until is not None and now < self._halved_until:
            return max(1, self._per_hour // 2)
        return self._per_hour

    def used(self, now: float) -> int:
        """Return how many lookups were counted in the hour before ``now``."""
        self._forget_before(now - HOUR_S)
        return len(self._recent)

    def wait_s(self, now: float) -> float:
        """Return how long the exact-date fetch waits before its next lookup.

        It waits while the last hour used the whole budget, and it keeps its
        own lookups apart by an equal share of the hour.

        Args:
            now: The time now.

        Returns:
            Seconds, 0 when it may ask now.
        """
        limit = self.limit(now)
        waits = [0.0]
        if self.used(now) >= limit:
            waits.append(self._recent[len(self._recent) - limit] + HOUR_S - now)
        if self._last_fetch is not None:
            waits.append(self._last_fetch + HOUR_S / limit - now)
        return max(waits)

    def count(self, kind: LookupKind, now: float) -> HourCounts | None:
        """Count one lookup.

        Args:
            kind: What the lookup was for.
            now: When it was asked.

        Returns:
            The counts of the hour before, when this lookup is the first of a new hour.
        """
        finished = self._enter_hour(now)
        self._recent.append(now)
        if kind is LookupKind.EXACT_DATE:
            self._last_fetch = now
        assert self._hour is not None
        self._hour.counts[kind] += 1
        return finished

    def halve(self, now: float, until: float) -> HourCounts | None:
        """Halve the budget after a "not a bot" check, until ``until``.

        A second check before then does not halve it again: the pause of the
        whole app (R-ER-05) already grows with every check.

        Args:
            now: When YouTube showed the check.
            until: The midnight in the Mac's time zone after ``now``.

        Returns:
            The counts of the hour before, when the check is the first event of a new hour.
        """
        finished = self._enter_hour(now)
        assert self._hour is not None
        self._hour.bot_checks += 1
        if self._halved_until is None or now >= self._halved_until:
            self._halved_until = until
        return finished

    def finish_hour(self, now: float) -> HourCounts | None:
        """Return the counts of the hour that ended before ``now``, if one is still open.

        Also used at the end of the app, with any time after the hour, to log the last one.
        """
        if self._hour is None or now < self._hour.start + HOUR_S:
            return None
        return self._close(now)

    def close(self, now: float) -> HourCounts | None:
        """Return the counts of the hour that is open, even before it ended. For the app's end."""
        if self._hour is None:
            return None
        return self._close(now)

    def _close(self, now: float) -> HourCounts:
        assert self._hour is not None
        hour = self._hour
        self._hour = None
        return HourCounts(
            hour_start=hour.start,
            exact_date=hour.counts[LookupKind.EXACT_DATE],
            download=hour.counts[LookupKind.DOWNLOAD],
            bot_checks=hour.bot_checks,
            limit=self.limit(now),
        )

    def _enter_hour(self, now: float) -> HourCounts | None:
        start = int(now) - int(now) % HOUR_S
        if self._hour is not None and self._hour.start == start:
            return None
        finished = self._close(now) if self._hour is not None else None
        self._hour = _Hour(start)
        return finished

    def _forget_before(self, moment: float) -> None:
        while self._recent and self._recent[0] <= moment:
            self._recent.popleft()
