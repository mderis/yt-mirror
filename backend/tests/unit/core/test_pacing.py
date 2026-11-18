"""Tests of ``ytmirror.core.pacing``: the budget of lookups in an hour."""

from ytmirror.core.pacing import HOUR_S, LOOKUPS_PER_HOUR, HourCounts, LookupBudget, LookupKind

START = 1_794_000_000 - 1_794_000_000 % HOUR_S
"""The start of a clock hour."""
MIDNIGHT = START + 10 * HOUR_S


def test_the_budget_is_300_lookups_an_hour_in_one_value() -> None:
    """R-DT-06: 300 lookups an hour, one value of the code that a later release can change."""
    budget = LookupBudget()

    assert LOOKUPS_PER_HOUR == 300
    assert budget.limit(START) == 300


def test_an_empty_budget_lets_the_fetch_ask_at_once() -> None:
    """R-DT-06: with nothing counted, the exact-date fetch may ask now."""
    assert LookupBudget().wait_s(START) == 0


def test_the_fetch_spreads_its_lookups_over_the_hour() -> None:
    """R-DT-06: the fetch's lookups are an equal share of the hour apart, 12 seconds at 300."""
    budget = LookupBudget()
    budget.count(LookupKind.EXACT_DATE, START)

    assert budget.wait_s(START + 2) == 10
    assert budget.wait_s(START + 12) == 0


def test_downloads_are_counted_but_do_not_space_the_fetch() -> None:
    """R-DT-06: a download's lookup uses the budget, and only a full budget holds the fetch."""
    budget = LookupBudget(per_hour=3)
    budget.count(LookupKind.DOWNLOAD, START)
    budget.count(LookupKind.DOWNLOAD, START + 1)

    assert budget.used(START + 2) == 2
    assert budget.wait_s(START + 2) == 0


def test_downloads_that_use_the_whole_budget_hold_the_fetch_until_the_oldest_is_an_hour_old() -> (
    None
):
    """R-DT-06: downloads go first; the fetch uses only what is left."""
    budget = LookupBudget(per_hour=3)
    for second in (0, 10, 20):
        budget.count(LookupKind.DOWNLOAD, START + second)

    assert budget.wait_s(START + 30) == HOUR_S - 30
    assert budget.wait_s(START + HOUR_S) == 0


def test_a_check_halves_the_budget_until_midnight() -> None:
    """R-DT-06: after a "not a bot" check the budget is halved until midnight."""
    budget = LookupBudget()

    budget.halve(START, MIDNIGHT)

    assert budget.limit(START + 1) == 150
    assert budget.limit(MIDNIGHT - 1) == 150
    assert budget.limit(MIDNIGHT) == 300


def test_a_halved_budget_spaces_the_fetch_twice_as_far() -> None:
    """R-DT-06: at 150 an hour the fetch's lookups are 24 seconds apart."""
    budget = LookupBudget()
    budget.halve(START, MIDNIGHT)
    budget.count(LookupKind.EXACT_DATE, START)

    assert budget.wait_s(START) == 24


def test_a_second_check_the_same_day_does_not_halve_again() -> None:
    """R-DT-06: the budget is halved once until midnight; the growing pause does the rest."""
    budget = LookupBudget()
    budget.halve(START, MIDNIGHT)

    budget.halve(START + HOUR_S, MIDNIGHT)

    assert budget.limit(START + HOUR_S) == 150


def test_a_check_after_midnight_halves_until_the_next_midnight() -> None:
    """R-DT-06: a check of a new day halves the budget of that day."""
    budget = LookupBudget()
    budget.halve(START, MIDNIGHT)

    budget.halve(MIDNIGHT + 5, MIDNIGHT + 24 * HOUR_S)

    assert budget.limit(MIDNIGHT + 6) == 150


def test_the_counts_of_an_hour_come_back_with_the_first_lookup_of_the_next() -> None:
    """R-DT-06: the lookups of each hour are kept for the log, by kind, with the checks."""
    budget = LookupBudget()
    budget.count(LookupKind.EXACT_DATE, START + 5)
    budget.count(LookupKind.DOWNLOAD, START + 6)
    budget.count(LookupKind.EXACT_DATE, START + 7)
    assert budget.halve(START + 8, MIDNIGHT) is None

    finished = budget.count(LookupKind.DOWNLOAD, START + HOUR_S + 1)

    assert finished == HourCounts(
        hour_start=START, exact_date=2, download=1, bot_checks=1, limit=150
    )


def test_an_hour_that_ended_is_finished_without_a_new_lookup() -> None:
    """R-DT-06: a finished hour is logged even when no lookup follows it."""
    budget = LookupBudget()
    budget.count(LookupKind.DOWNLOAD, START)

    assert budget.finish_hour(START + HOUR_S - 1) is None
    finished = budget.finish_hour(START + HOUR_S)

    assert finished is not None
    assert (finished.hour_start, finished.download) == (START, 1)
    assert budget.finish_hour(START + 2 * HOUR_S) is None


def test_the_open_hour_can_be_closed_at_the_end_of_the_app() -> None:
    """R-DT-06: at the app's end the hour that is open is logged too."""
    budget = LookupBudget()
    assert budget.close(START) is None
    budget.count(LookupKind.EXACT_DATE, START + 1)

    closed = budget.close(START + 2)

    assert closed is not None
    assert closed.exact_date == 1
    assert budget.close(START + 3) is None


def test_a_second_check_never_moves_the_end_of_the_halving_later() -> None:
    """R-DT-06: the halving ends at the midnight of the first check, whatever comes after."""
    budget = LookupBudget()
    budget.halve(START, MIDNIGHT)

    budget.halve(START + HOUR_S, MIDNIGHT + 24 * HOUR_S)

    assert budget.limit(MIDNIGHT) == 300


def test_the_budget_is_kept_across_a_restart() -> None:
    """R-DT-06: the lookups of the last hour and the halving survive a restart (review of M4)."""
    before = LookupBudget(per_hour=3)
    before.halve(START, MIDNIGHT)
    for second in (0, 10, 20):
        before.count(LookupKind.DOWNLOAD, START + second)

    after = LookupBudget(per_hour=3)
    after.restore(before.saved(), START + 30)

    assert after.limit(START + 30) == 1
    assert after.used(START + 30) == 3
    assert after.wait_s(START + 30) > 0


def test_what_cannot_be_read_is_not_restored() -> None:
    """R-DT-06: values that are no times, or no budget at all, are left out."""
    budget = LookupBudget()

    budget.restore({"recent": ["x", START], "halved_until": "soon"}, START)
    budget.restore("not a budget", START)

    assert budget.used(START) == 1
    assert budget.limit(START) == 300


def test_lookups_after_now_are_not_restored_when_the_clock_was_set_back() -> None:
    """R-DT-06: a lookup time in the future would hold the budget until the clock caught up."""
    budget = LookupBudget(per_hour=1)

    budget.restore({"recent": [START + 600], "halved_until": None}, START)

    assert budget.used(START) == 0
    assert budget.wait_s(START) == 0


def test_the_room_is_what_the_last_hour_left_of_the_budget() -> None:
    """R-DT-06, D-090: an automatic download may start while the budget has room."""
    budget = LookupBudget(per_hour=3)
    budget.count(LookupKind.DOWNLOAD, START)
    budget.count(LookupKind.EXACT_DATE, START + 1)

    assert budget.room(START + 2) == 1
    budget.count(LookupKind.DOWNLOAD, START + 2)
    assert budget.room(START + 3) == 0
    assert budget.room(START + HOUR_S) == 1


def test_room_comes_back_as_the_lookups_of_the_last_hour_grow_old() -> None:
    """R-DT-06, D-090: a paced download may start when the oldest lookup is an hour old."""
    budget = LookupBudget(per_hour=3)
    for second in (0, 10, 20):
        budget.count(LookupKind.DOWNLOAD, START + second)

    assert budget.free_times(START + 30, 3) == [
        START + HOUR_S,
        START + 10 + HOUR_S,
        START + 20 + HOUR_S,
    ]


def test_room_now_needs_no_wait() -> None:
    """R-DT-06, D-090: with room left, the next downloads may start now."""
    budget = LookupBudget(per_hour=3)
    budget.count(LookupKind.DOWNLOAD, START)

    assert budget.free_times(START + 1, 3) == [START + 1, START + 1, START + HOUR_S]


def test_the_paced_downloads_use_the_room_they_get() -> None:
    """R-DT-06, D-090: a long line of automatic downloads takes one more hour per full budget."""
    budget = LookupBudget(per_hour=2)
    budget.count(LookupKind.DOWNLOAD, START)
    budget.count(LookupKind.DOWNLOAD, START + 5)

    times = budget.free_times(START + 10, 6)

    assert times == [
        START + HOUR_S,
        START + 5 + HOUR_S,
        START + 2 * HOUR_S,
        START + 5 + 2 * HOUR_S,
        START + 3 * HOUR_S,
        START + 5 + 3 * HOUR_S,
    ]


def test_a_halved_budget_has_half_the_room() -> None:
    """R-DT-06, D-090: after a "not a bot" check automatic downloads get half the room."""
    budget = LookupBudget(per_hour=4)
    budget.halve(START, MIDNIGHT)

    assert budget.room(START) == 2
