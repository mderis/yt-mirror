"""The speed limit of all downloads together (R-QU-03).

The downloads tell their progress block by block, from yt-dlp's progress
hook. Each block takes its share of one rate that every running download
shares; when the blocks come faster than the rate, the hook waits, and
yt-dlp reads the next block only after it. The limit is read from the
settings at every block, so a change takes effect at once.

Tests: backend/tests/unit/services/test_speed_limit.py
"""

import threading
from collections.abc import Callable

BYTES_PER_MB = 1_000_000
"""A megabyte, as macOS counts it."""

BURST_S = 0.5
"""How much time unused by a download may be made up at once: a short burst, no more."""

STEP_S = 0.1
"""The longest single wait, so that a cancel or a quit is never held up longer."""


class SpeedLimit:
    """One rate shared by every running download."""

    def __init__(
        self,
        limit_mbps: Callable[[], int],
        monotonic: Callable[[], float],
        sleep: Callable[[float], None],
    ) -> None:
        """Create the limit.

        Args:
            limit_mbps: Says the limit now, in MB/s; 0 means unlimited.
            monotonic: The clock the waits are measured on.
            sleep: Waits a number of seconds.
        """
        self._limit_mbps = limit_mbps
        self._monotonic = monotonic
        self._sleep = sleep
        self._lock = threading.Lock()
        self._free_at = 0.0

    def took(self, amount: int, stop: Callable[[], bool] = lambda: False) -> None:
        """Count bytes that arrived, and wait as long as the limit asks (R-QU-03).

        Args:
            amount: How many bytes arrived since the download last told.
            stop: Asked between the steps of a wait: when it says yes, the wait ends,
                so that a cancel or a quit is never held up.
        """
        limit = self._limit_mbps()
        if limit <= 0 or amount <= 0:
            return
        with self._lock:
            now = self._monotonic()
            start = max(self._free_at, now - BURST_S)
            self._free_at = start + amount / (limit * BYTES_PER_MB)
            until = self._free_at
        while not stop():
            left = until - self._monotonic()
            if left <= 0:
                return
            self._sleep(min(left, STEP_S))
