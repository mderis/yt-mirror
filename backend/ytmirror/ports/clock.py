"""The Clock port: the only source of time for core rules and services.

Code in ``core`` and ``services`` must never read the system clock itself
(docs/CODING-STANDARDS.md section 3), so that tests control time.

Tests: backend/tests/integration/test_clock_contract.py
"""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Tells the time."""

    def now(self) -> datetime:
        """Return the current time as a timezone-aware datetime in UTC."""
        ...

    def monotonic(self) -> float:
        """Return seconds from a clock that never goes backwards, for measuring durations."""
        ...
