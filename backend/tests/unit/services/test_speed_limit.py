"""Tests of the speed limit of all downloads together."""

from tests.fixtures.fakes.clock import FakeClock
from ytmirror.services.speed_limit import BYTES_PER_MB, SpeedLimit


def limited(clock: FakeClock, mbps: list[int]) -> SpeedLimit:
    """A limit read from a list, on a fake clock whose sleep moves it on."""
    return SpeedLimit(lambda: mbps[0], clock.monotonic, clock.advance)


def test_unlimited_never_waits() -> None:
    """R-QU-03: the default is unlimited."""
    clock = FakeClock()
    start = clock.monotonic()

    limited(clock, [0]).took(50 * BYTES_PER_MB)

    assert clock.monotonic() == start


def test_bytes_beyond_the_limit_wait_for_their_share_of_time() -> None:
    """R-QU-03: at 2 MB/s, 10 MB take 5 seconds, apart from a short burst."""
    clock = FakeClock()
    limit = limited(clock, [2])
    start = clock.monotonic()

    for _block in range(10):
        limit.took(BYTES_PER_MB)

    assert 4.4 <= clock.monotonic() - start <= 5.0


def test_two_downloads_share_one_limit() -> None:
    """R-QU-03: the limit applies to the sum of all downloads."""
    clock = FakeClock()
    limit = limited(clock, [1])
    start = clock.monotonic()

    for _block in range(4):
        limit.took(BYTES_PER_MB // 2)  # one download
        limit.took(BYTES_PER_MB // 2)  # the other

    assert 3.4 <= clock.monotonic() - start <= 4.0


def test_a_change_of_the_limit_takes_effect_at_once() -> None:
    """R-QU-03: the limit is read at every block."""
    clock = FakeClock()
    mbps = [1]
    limit = limited(clock, mbps)
    limit.took(BYTES_PER_MB)
    mbps[0] = 0
    before = clock.monotonic()

    limit.took(100 * BYTES_PER_MB)

    assert clock.monotonic() == before


def test_a_cancel_ends_the_wait() -> None:
    """R-QU-02, R-QU-03: a wait for the limit never holds up a cancel."""
    clock = FakeClock()
    limit = limited(clock, [1])
    start = clock.monotonic()

    limit.took(100 * BYTES_PER_MB, stop=lambda: clock.monotonic() - start > 0.3)

    assert clock.monotonic() - start < 0.5
