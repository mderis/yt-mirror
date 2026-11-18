"""The queue of downloads: how it stands, and the order of the jobs that wait.

Implements the pure part of R-QU-02 (order, "Mirror first", reorder) and the
summary the queue bar and the downloads panel show (R-QU-01, R-QU-02). The
order of the jobs that wait is their priority, lower first; reordering gives
them new priorities and leaves the running jobs alone.

This module must not read a clock or store anything.

Tests: backend/tests/unit/core/test_queue.py
"""

from collections.abc import Sequence
from dataclasses import dataclass

from ytmirror.core.channels import Video
from ytmirror.core.jobs import Job, JobProgress

HAND_JOBS_PER_ACTION = 20
"""How many jobs of one action of the user count as started by hand (R-DT-06, D-090).

The jobs beyond them wait for room in the lookup budget like automatic ones."""


@dataclass(frozen=True, slots=True)
class QueueSummary:
    """How the queue stands, for the queue bar and the downloads panel.

    Attributes:
        downloading: How many downloads run now.
        waiting: How many wait in line.
        failed: How many videos failed and wait for the user (R-QU-08).
        paused: Whether the user paused all downloads (R-QU-02).
        places: How many downloads may run at once (R-QU-01).
    """

    downloading: int
    waiting: int
    failed: int
    paused: bool
    places: int


NO_QUEUE = QueueSummary(downloading=0, waiting=0, failed=0, paused=False, places=2)
"""The summary of a queue that has nothing in it, with the default settings."""


@dataclass(frozen=True, slots=True)
class QueueEntry:
    """One download that waits or runs, as the downloads panel shows it.

    Attributes:
        job: The job.
        video: Its video.
        channel_title: The name of the video's channel.
        progress: How far it is, when it runs and reported already, else None.
    """

    job: Job
    video: Video
    channel_title: str
    progress: JobProgress | None = None


@dataclass(frozen=True, slots=True)
class FailedEntry:
    """One failed video, as the downloads panel shows it (R-QU-08).

    Attributes:
        video: The video, with its last failure.
        channel_title: The name of its channel.
    """

    video: Video
    channel_title: str


@dataclass(frozen=True, slots=True)
class QueueView:
    """The whole queue, as the downloads panel shows it.

    Attributes:
        summary: How it stands.
        running: The downloads that run, in the order they were taken.
        waiting: The downloads that wait, in their order.
        failed: The failed videos, newest failure first.
    """

    summary: QueueSummary
    running: tuple[QueueEntry, ...]
    waiting: tuple[QueueEntry, ...]
    failed: tuple[FailedEntry, ...]


@dataclass(frozen=True, slots=True)
class QueueChanged:
    """Event: the queue changed (R-FB-03).

    Attributes:
        summary: How it stands now.
    """

    summary: QueueSummary


def priorities_in_order(waiting: Sequence[tuple[str, int]], order: Sequence[str]) -> dict[str, int]:
    """Return the new priority of each waiting job, so that they wait in the given order.

    The jobs named in ``order`` come first, in that order. A waiting job that is
    not named keeps its place behind them. A name that is not a waiting job, or
    that comes twice, is ignored. The priorities the waiting jobs had are used
    again, lowest first, so the jobs that run and the ones put in line later keep
    their places around them (R-QU-02).

    Args:
        waiting: Every waiting job as (job ID, priority), in their order now.
        order: Job IDs in the order the user wants.

    Returns:
        The new priority of each waiting job whose priority changes.
    """
    known = {job_id for job_id, _priority in waiting}
    named: list[str] = []
    for job_id in order:
        if job_id in known and job_id not in named:
            named.append(job_id)
    rest = [job_id for job_id, _priority in waiting if job_id not in named]
    slots = sorted(priority for _job_id, priority in waiting)
    old = dict(waiting)
    return {
        job_id: priority
        for job_id, priority in zip(named + rest, slots, strict=True)
        if old[job_id] != priority
    }


def priorities_first(count: int, lowest: int | None) -> list[int]:
    """Return priorities for jobs that go to the top of the line, in their order ("Mirror first").

    Args:
        count: How many jobs go to the top.
        lowest: The lowest priority of a job that waits or runs, or None when there is none.

    Returns:
        One priority per job, all lower than every other, in increasing order.
    """
    start = (1 if lowest is None else lowest) - count
    return list(range(start, start + count))
