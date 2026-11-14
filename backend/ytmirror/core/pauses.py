"""How long the app pauses when YouTube refuses it.

Implements the pause of R-ER-05: after YouTube's "not a bot" check the app
waits 15 minutes before it asks again by itself, then twice as long each
time, up to 6 hours. Any answer of YouTube starts the row from the beginning.

This module must not read a clock.

Tests: backend/tests/unit/core/test_pauses.py
"""

FIRST_PAUSE_S = 15 * 60
LONGEST_PAUSE_S = 6 * 60 * 60


def next_pause_s(previous_s: int | None) -> int:
    """Return how long the next pause is.

    Args:
        previous_s: The length of the pause before, or None when YouTube answered
            since then.

    Returns:
        The length in seconds.
    """
    if previous_s is None:
        return FIRST_PAUSE_S
    return min(previous_s * 2, LONGEST_PAUSE_S)
