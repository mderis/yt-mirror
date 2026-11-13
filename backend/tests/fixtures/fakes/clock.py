"""A clock that tests control. Fake of the Clock port."""

from datetime import UTC, datetime, timedelta

DEFAULT_START = datetime(2026, 11, 13, 9, 28, 4, 512000, tzinfo=UTC)


class FakeClock:
    """Stands still until a test moves it."""

    def __init__(self, start: datetime = DEFAULT_START) -> None:
        """Create a clock that shows ``start``."""
        self._now = start
        self._monotonic = 1000.0

    def now(self) -> datetime:
        """Return the time the clock shows, in UTC."""
        return self._now

    def monotonic(self) -> float:
        """Return the monotonic reading."""
        return self._monotonic

    def advance(self, seconds: float) -> None:
        """Move both readings forward."""
        self._now += timedelta(seconds=seconds)
        self._monotonic += seconds

    def set(self, moment: datetime) -> None:
        """Jump to a moment."""
        self._now = moment
