"""Turns Ctrl+C and a termination signal into a request to quit.

Implements the signal part of R-PL-13 for a run with a window. While the
window loop of macOS waits, Python runs no signal handler, so a handler
alone would never be called. Python can still write the number of a signal
into a pipe at once. A helper thread reads that pipe and passes the request
on (docs/DECISIONS.md D-052).

This module must not decide what quitting means: it calls what it is given.

Tests: backend/tests/unit/app/test_signals.py
"""

import os
import signal
import threading
from collections.abc import Callable
from types import FrameType

STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM)
"""Ctrl+C in a terminal, and the signal ``kill`` and macOS send to end a process."""


def _nothing(_signal_number: int, _frame: FrameType | None) -> None:
    """Do nothing. The signal is handled by the thread that reads the pipe."""


def send_stop_signals_to(request_quit: Callable[[], None]) -> Callable[[], None]:
    """Call ``request_quit`` whenever a stop signal arrives. Main thread only.

    Args:
        request_quit: Called from a helper thread, once per signal.

    Returns:
        A function that puts the earlier signal handling back. Main thread only.
    """
    read_end, write_end = os.pipe()
    os.set_blocking(write_end, False)
    earlier_pipe = signal.set_wakeup_fd(write_end, warn_on_full_buffer=False)
    earlier = {number: signal.signal(number, _nothing) for number in STOP_SIGNALS}

    def watch() -> None:
        while data := os.read(read_end, 1):
            if data[0] in STOP_SIGNALS:
                request_quit()
        os.close(read_end)

    threading.Thread(target=watch, name="stop-signals", daemon=True).start()

    def restore() -> None:
        for number, handler in earlier.items():
            signal.signal(number, handler)
        signal.set_wakeup_fd(earlier_pipe)
        os.close(write_end)

    return restore
