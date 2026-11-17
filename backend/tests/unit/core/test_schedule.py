"""Tests of ``ytmirror.core.schedule``: when the app checks channels by itself."""

import dataclasses

import pytest

from tests.fixtures.catalogue import NOW, make_channel
from ytmirror.core.errors import ErrorCode
from ytmirror.core.schedule import (
    DAY_S,
    checked_by_itself,
    full_check_due,
    is_stale,
    next_interval_check,
    retry_at,
)

MINUTE = 60


def test_a_paused_or_never_listed_channel_is_not_checked_by_itself() -> None:
    """R-CH-20, R-CH-22: automatic checks skip paused channels; first listings have own rules."""
    assert checked_by_itself(make_channel())
    assert not checked_by_itself(make_channel(paused=True))
    assert not checked_by_itself(make_channel(first_listed_at=None))


def test_a_channel_selected_after_more_than_five_minutes_is_stale() -> None:
    """R-CH-21: the last successful check older than 5 minutes."""
    channel = make_channel(last_check_at=NOW)

    assert not is_stale(channel, NOW + 5 * MINUTE)
    assert is_stale(channel, NOW + 5 * MINUTE + 1)
    assert not is_stale(make_channel(paused=True, last_check_at=NOW), NOW + DAY_S)


@pytest.mark.parametrize(("retries", "minutes"), [(0, 5), (1, 15), (2, 60), (3, 60), (8, 60)])
def test_a_failed_check_is_tried_again_after_5_15_and_60_minutes(
    retries: int, minutes: int
) -> None:
    """R-CH-25: automatic retries with backoff (5, 15, 60 minutes), then every hour."""
    channel = dataclasses.replace(
        make_channel(last_check_error=ErrorCode.NETWORK_UNREACHABLE, last_check_error_at=NOW),
        check_retries=retries,
    )

    assert retry_at(channel) == NOW + minutes * MINUTE


def test_only_a_failed_check_of_a_channel_that_is_not_paused_is_retried() -> None:
    """R-CH-25, R-CH-31: no retry without a failure, and none for a paused channel."""
    assert retry_at(make_channel()) is None
    assert (
        retry_at(
            make_channel(
                paused=True, last_check_error=ErrorCode.NETWORK_UNREACHABLE, last_check_error_at=NOW
            )
        )
        is None
    )


def test_a_full_check_is_due_after_the_set_number_of_days() -> None:
    """R-CH-26: "Full check at least every" (default 7 days)."""
    channel = make_channel(last_full_check_at=NOW)

    assert not full_check_due(channel, NOW + 7 * DAY_S - 1, 7)
    assert full_check_due(channel, NOW + 7 * DAY_S, 7)
    assert full_check_due(channel, NOW + 2 * DAY_S, 2)


def test_no_full_check_is_due_for_a_paused_failed_or_unlisted_channel() -> None:
    """R-CH-26, R-CH-25: a failed check is retried first; paused and unlisted ones wait."""
    late = NOW + 30 * DAY_S
    assert not full_check_due(make_channel(paused=True), late, 7)
    assert not full_check_due(make_channel(first_listed_at=None), late, 7)
    failed = make_channel(last_check_error=ErrorCode.NETWORK_UNREACHABLE, last_check_error_at=NOW)
    assert not full_check_due(failed, late, 7)


def test_the_first_listing_counts_as_the_last_full_check() -> None:
    """R-CH-26: adding a channel is a full check (R-CH-11)."""
    channel = make_channel(first_listed_at=NOW, last_full_check_at=None)

    assert full_check_due(channel, NOW + 7 * DAY_S, 7)


def test_the_interval_check_comes_after_its_minutes_and_never_when_off() -> None:
    """R-CH-22: 30 minutes, 1 hour, 3 hours, or never."""
    assert next_interval_check(NOW, 30) == NOW + 30 * MINUTE
    assert next_interval_check(NOW, 180) == NOW + 3 * 60 * MINUTE
    assert next_interval_check(NOW, 0) is None
