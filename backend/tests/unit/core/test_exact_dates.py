"""Tests of ``ytmirror.core.exact_dates``: date states, retries, the rate and the time left."""

import pytest

from ytmirror.core.errors import ErrorCode
from ytmirror.core.exact_dates import (
    OFFER_KEY_ABOVE_S,
    DateShown,
    DateState,
    FetchHold,
    FetchState,
    RateMeter,
    date_shown,
    offers_key,
    retry_after_s,
    time_left_s,
)

NOW = 1_794_000_000
HOUR = 3600


def test_a_date_nobody_looks_up_yet_is_waiting() -> None:
    """R-DT-13: "Exact date pending" while it is not being fetched yet."""
    assert date_shown(None, updating=False, hold=None, now=NOW) == DateShown(DateState.WAITING)


def test_a_date_being_looked_up_is_updating() -> None:
    """R-DT-13: "Getting the exact date..." while it is fetched now."""
    state = FetchState(attempts=1, next_try_at=NOW + HOUR, last_error=ErrorCode.VIDEO_PRIVATE)

    assert date_shown(state, updating=True, hold=None, now=NOW).state is DateState.UPDATING


def test_a_failed_lookup_is_unavailable_with_its_reason_until_it_is_tried_again() -> None:
    """R-DT-13: the tooltip says why and that it will be tried again."""
    state = FetchState(attempts=1, next_try_at=NOW + HOUR, last_error=ErrorCode.VIDEO_PRIVATE)

    shown = date_shown(state, updating=False, hold=None, now=NOW)

    assert shown == DateShown(DateState.UNAVAILABLE, ErrorCode.VIDEO_PRIVATE, NOW + HOUR)
    assert date_shown(state, updating=False, hold=None, now=NOW + HOUR).state is DateState.WAITING


def test_a_held_fetch_makes_every_waiting_date_unavailable_with_the_hold() -> None:
    """R-DT-13: unavailable also when fetching is paused, with when it goes on."""
    hold = FetchHold(ErrorCode.BOT_CHECK, NOW + 900)

    shown = date_shown(None, updating=False, hold=hold, now=NOW)

    assert shown == DateShown(DateState.UNAVAILABLE, ErrorCode.BOT_CHECK, NOW + 900)


@pytest.mark.parametrize(("attempts", "hours"), [(1, 1), (2, 6), (3, 24), (9, 24)])
def test_a_video_whose_lookup_failed_waits_longer_each_time(attempts: int, hours: int) -> None:
    """R-DT-13: one hour, six hours, then once a day."""
    assert retry_after_s(attempts) == hours * HOUR


def test_no_rate_is_known_before_five_lookups_ended() -> None:
    """R-DT-14: no time is shown until enough lookups were measured."""
    meter = RateMeter()
    for second in range(4):
        meter.finished(second * 12.0)

    assert meter.seconds_per_video() is None


def test_the_rate_is_the_time_per_video_waits_included() -> None:
    """R-DT-14: the rate comes from what the app measures while it runs."""
    meter = RateMeter()
    for second in (0.0, 12.0, 24.0, 36.0, 60.0):
        meter.finished(second)

    assert meter.seconds_per_video() == 15.0


def test_the_rate_follows_the_last_twenty_lookups() -> None:
    """R-DT-14: an old pace is forgotten."""
    meter = RateMeter()
    for second in range(30):
        meter.finished(second * 100.0)
    for second in range(20):
        meter.finished(3000.0 + second * 12.0)

    assert meter.seconds_per_video() == 12.0


def test_a_restarted_meter_has_no_rate() -> None:
    """R-DT-14: after a pause the time left is measured again."""
    meter = RateMeter()
    for second in range(6):
        meter.finished(float(second))
    meter.restart()

    assert meter.seconds_per_video() is None


def test_the_time_left_of_a_channel_ends_with_its_last_waiting_video() -> None:
    """R-DT-14: newest first across channels; a channel is done after its last video."""
    order = ["UCa", "UCb", "UCa", "UCb", "UCb"]

    assert time_left_s(order, 12.0) == {"UCa": 36, "UCb": 60}
    assert time_left_s(order, None) == {}


def test_the_key_is_offered_over_ten_minutes_without_a_working_key() -> None:
    """R-DT-15: over 10 minutes left and no key that works."""
    assert OFFER_KEY_ABOVE_S == 600
    assert offers_key(601, key_works=False)
    assert not offers_key(600, key_works=False)
    assert not offers_key(None, key_works=False)
    assert not offers_key(5000, key_works=True)
