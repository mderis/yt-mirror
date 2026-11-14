"""Tests of ``ytmirror.app.signals``."""

import signal
import threading

import pytest

from ytmirror.app.signals import STOP_SIGNALS, send_stop_signals_to


@pytest.mark.parametrize("stop_signal", [signal.SIGINT, signal.SIGTERM])
def test_a_stop_signal_becomes_a_request_to_quit(stop_signal: signal.Signals) -> None:
    """R-PL-13: Ctrl+C and a termination signal ask the app to quit instead of killing it."""
    asked = threading.Event()
    restore = send_stop_signals_to(asked.set)

    try:
        signal.raise_signal(stop_signal)

        assert asked.wait(timeout=5)
    finally:
        restore()


def test_every_signal_asks_once_more() -> None:
    """R-PL-13: a second Ctrl+C is not lost while the first one is being handled."""
    asked = threading.Semaphore(0)
    restore = send_stop_signals_to(asked.release)

    try:
        signal.raise_signal(signal.SIGINT)
        signal.raise_signal(signal.SIGTERM)

        assert asked.acquire(timeout=5)
        assert asked.acquire(timeout=5)
    finally:
        restore()


def test_other_signals_do_not_ask_to_quit() -> None:
    """R-PL-13: only Ctrl+C and the termination signal end the app."""
    asked = threading.Event()
    seen = threading.Event()
    earlier = signal.signal(signal.SIGUSR1, lambda _number, _frame: seen.set())
    restore = send_stop_signals_to(asked.set)

    try:
        signal.raise_signal(signal.SIGUSR1)

        assert seen.wait(timeout=5)
        assert not asked.wait(timeout=0.3)
    finally:
        restore()
        signal.signal(signal.SIGUSR1, earlier)


def test_the_earlier_signal_handling_comes_back() -> None:
    """infra: after a run nothing of the signal handling stays behind in the process."""
    before = {number: signal.getsignal(number) for number in STOP_SIGNALS}

    send_stop_signals_to(lambda: None)()

    assert {number: signal.getsignal(number) for number in STOP_SIGNALS} == before
    assert signal.set_wakeup_fd(-1) == -1
