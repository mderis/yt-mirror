"""Tests of ``ytmirror.core.pauses``."""

from ytmirror.core.pauses import FIRST_PAUSE_S, LONGEST_PAUSE_S, next_pause_s


def test_the_first_pause_is_a_quarter_of_an_hour() -> None:
    """R-ER-05: after the "not a bot" check the app waits 15 minutes."""
    assert next_pause_s(None) == FIRST_PAUSE_S == 15 * 60


def test_every_further_pause_is_twice_as_long_up_to_six_hours() -> None:
    """R-ER-05: the pause doubles each time and never exceeds 6 hours."""
    pauses = [next_pause_s(None)]
    for _ in range(7):
        pauses.append(next_pause_s(pauses[-1]))

    minutes = [pause // 60 for pause in pauses]
    assert minutes == [15, 30, 60, 120, 240, 360, 360, 360]
    assert LONGEST_PAUSE_S == 6 * 60 * 60
