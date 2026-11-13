"""Contract of the Clock port, run against the fake and the real adapter."""

from collections.abc import Callable
from datetime import timedelta

import pytest

from tests.fixtures.fakes.clock import FakeClock
from ytmirror.adapters.system_clock import SystemClock
from ytmirror.ports.clock import Clock

CLOCKS: list[Callable[[], Clock]] = [FakeClock, SystemClock]


@pytest.mark.parametrize("make_clock", CLOCKS)
def test_now_is_timezone_aware_and_in_utc(make_clock: Callable[[], Clock]) -> None:
    """infra: all timestamps are UTC, whatever the time zone of the Mac."""
    now = make_clock().now()

    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


@pytest.mark.parametrize("make_clock", CLOCKS)
def test_monotonic_never_goes_backwards(make_clock: Callable[[], Clock]) -> None:
    """infra: durations are measured with a clock that cannot jump back."""
    clock = make_clock()

    first = clock.monotonic()
    second = clock.monotonic()

    assert second >= first


def test_the_fake_clock_moves_only_when_told() -> None:
    """infra: tests control time (docs/TESTING.md rule 4)."""
    clock = FakeClock()
    before = clock.now()

    clock.advance(90)

    assert clock.now() - before == timedelta(seconds=90)
    assert clock.monotonic() == 1090.0
