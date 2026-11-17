"""When the app checks channels by itself.

Implements the rules of R-CH-20 to R-CH-22, R-CH-25 and R-CH-26 that need
no storage and no clock: a channel selected after more than 5 minutes is
checked (R-CH-21); a failed check is tried again after 5, 15 and 60 minutes
and then every hour (R-CH-25); a full check is due when the last one is
older than the setting (R-CH-26). A paused channel is never checked by
itself, and neither is one that was never listed: its first listing is
started by its own rules (R-CH-11).

This module must not read a clock: every time is passed in, in seconds
since the Unix epoch.

Tests: backend/tests/unit/core/test_schedule.py
"""

from ytmirror.core.channels import Channel

STALE_AFTER_S = 5 * 60
"""A channel selected after this long since its last successful check is checked (R-CH-21)."""

RETRY_AFTER_S = (5 * 60, 15 * 60, 60 * 60)
"""When a failed check is tried again: after the first, second and every later retry."""

DAY_S = 24 * 60 * 60


def checked_by_itself(channel: Channel) -> bool:
    """Return whether the app may check a channel by itself: listed and not paused."""
    return not channel.paused and channel.first_listed_at is not None


def is_stale(channel: Channel, now: int) -> bool:
    """Return whether a selected channel is checked (R-CH-21).

    Args:
        channel: The channel.
        now: The time now.
    """
    if not checked_by_itself(channel):
        return False
    last = channel.last_check_at
    return last is None or now - last > STALE_AFTER_S


def retry_at(channel: Channel) -> int | None:
    """Return when a failed check of a channel is tried again by itself, or None (R-CH-25).

    The first retry comes 5 minutes after the failure, the second 15, every
    later one 60. ``check_retries`` counts the retries made since the last
    successful check.

    Args:
        channel: The channel.
    """
    if channel.paused or channel.last_check_error is None or channel.last_check_error_at is None:
        return None
    step = min(channel.check_retries, len(RETRY_AFTER_S) - 1)
    return channel.last_check_error_at + RETRY_AFTER_S[step]


def full_check_due(channel: Channel, now: int, days: int) -> bool:
    """Return whether a full check of a channel is due by itself (R-CH-26).

    Args:
        channel: The channel.
        now: The time now.
        days: The setting "Full check at least every".
    """
    if not checked_by_itself(channel) or channel.last_check_error is not None:
        return False
    last = channel.last_full_check_at or channel.first_listed_at
    return last is not None and now - last >= days * DAY_S


def next_interval_check(last_started: int, interval_min: int) -> int | None:
    """Return when all channels are checked again on the interval, or None for never (R-CH-22).

    Args:
        last_started: When the last check of all channels by itself was started.
        interval_min: The setting "Re-check interval" in minutes; 0 means never.
    """
    if interval_min <= 0:
        return None
    return last_started + interval_min * 60
