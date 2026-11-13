"""The real clock: implements the Clock port with the system clock.

Tests: backend/tests/integration/test_clock_contract.py
"""

import time
from datetime import UTC, datetime


class SystemClock:
    """Reads the time from the operating system."""

    def now(self) -> datetime:
        """Return the current time as a timezone-aware datetime in UTC."""
        return datetime.now(tz=UTC)

    def monotonic(self) -> float:
        """Return seconds from a clock that never goes backwards."""
        return time.monotonic()
