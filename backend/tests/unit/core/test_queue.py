"""Tests of the order of the queue: reorder and "Mirror first"."""

from hypothesis import given
from hypothesis import strategies as st

from ytmirror.core.queue import priorities_first, priorities_in_order

WAITING = [("a", 3), ("b", 4), ("c", 7)]


def order_after(waiting: list[tuple[str, int]], changes: dict[str, int]) -> list[str]:
    """Return the job IDs in the order their new priorities give."""
    priority = dict(waiting) | changes
    return sorted(priority, key=lambda job_id: priority[job_id])


def test_the_named_jobs_wait_in_the_given_order() -> None:
    """R-QU-02: reordering puts the waiting jobs in the order the user dragged them to."""
    changes = priorities_in_order(WAITING, ["c", "a", "b"])

    assert order_after(WAITING, changes) == ["c", "a", "b"]


def test_jobs_that_are_not_named_keep_their_order_behind_the_named_ones() -> None:
    """R-QU-02: a job put in line meanwhile is not lost by a reorder that does not name it."""
    changes = priorities_in_order(WAITING, ["b"])

    assert order_after(WAITING, changes) == ["b", "a", "c"]


def test_unknown_and_repeated_names_are_ignored() -> None:
    """R-QU-02: a job that ended meanwhile, or a name given twice, changes nothing else."""
    changes = priorities_in_order(WAITING, ["x", "c", "c", "a"])

    assert order_after(WAITING, changes) == ["c", "a", "b"]


def test_the_priorities_of_the_waiting_jobs_are_used_again() -> None:
    """R-QU-02: running jobs and jobs put in line later keep their places around these."""
    changes = priorities_in_order(WAITING, ["c", "b", "a"])

    assert sorted((dict(WAITING) | changes).values()) == [3, 4, 7]
    assert "b" not in changes


def test_mirror_first_puts_the_jobs_ahead_of_all_others_in_their_order() -> None:
    """R-QU-02: "Mirror first" puts the videos at the top, in the order given."""
    assert priorities_first(3, lowest=5) == [2, 3, 4]
    assert priorities_first(1, lowest=None) == [0]


@given(
    st.lists(st.integers(-1000, 1000), min_size=1, max_size=20, unique=True),
    st.permutations(range(20)),
)
def test_any_reorder_gives_the_exact_order_asked_for(
    priorities: list[int], shuffle: list[int]
) -> None:
    """R-QU-02: for any waiting jobs and any full order, the new order is exactly that order."""
    waiting = [(f"j{index}", priority) for index, priority in enumerate(sorted(priorities))]
    ids = [job_id for job_id, _priority in waiting]
    wanted = [ids[index] for index in shuffle if index < len(ids)]

    changes = priorities_in_order(waiting, wanted)

    assert order_after(waiting, changes) == wanted
