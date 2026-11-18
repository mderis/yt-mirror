"""Actions of the user that queue many videos at once (review of M5: High 5 and 6).

One action starts at most 20 jobs by hand, new or promoted, in the order it
names them (D-090). A bulk action is stored in a few transactions and told to
the window with one summary per channel, not three events per video.
"""

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tests.fixtures.world import SMALL_ID, World, channel_file
from ytmirror.core.channels import VideoStatus
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.jobs import DownloadProgress, JobState, VideoUpdated
from ytmirror.core.pacing import LookupBudget
from ytmirror.core.queue import RETRY_DELAYS_S


def listed(tmp_path: Path, videos: int, **more: Any) -> World:
    """A world whose small channel has this many videos, listed."""
    world = World(tmp_path, channel_file(videos=videos), **more)
    world.add_and_list()
    return world


def by_hand(world: World) -> list[bool]:
    """Whether each waiting job is started by hand, in the order of the line."""
    return [job.by_hand for job in world.jobs.jobs([JobState.WAITING])]


def test_promoting_waiting_jobs_counts_against_the_20_of_the_action(tmp_path: Path) -> None:
    """R-DT-06, D-090: Mirror on 25 waiting automatic jobs makes only the first 20 by hand."""
    world = listed(tmp_path, 25)
    ids = world.ids(SMALL_ID)
    world.downloader.mirror(ids, automatic=True)
    assert by_hand(world) == [False] * 25

    world.downloader.mirror(ids)

    assert by_hand(world) == [True] * 20 + [False] * 5


def test_new_and_promoted_jobs_share_the_20_in_the_order_given(tmp_path: Path) -> None:
    """R-DT-06, D-090: 10 promoted and 15 new: the first 20 named are by hand."""
    world = listed(tmp_path, 25)
    ids = world.ids(SMALL_ID)
    world.downloader.mirror(ids[:10], automatic=True)

    world.downloader.mirror(ids)

    hand = {job.video_id: job.by_hand for job in world.jobs.jobs([JobState.WAITING])}
    assert [hand[video_id] for video_id in ids] == [True] * 20 + [False] * 5


def test_a_redownload_of_more_than_20_starts_only_20_by_hand(tmp_path: Path) -> None:
    """R-QL-06, D-090: a re-download the user starts is one action like Mirror."""
    world = listed(tmp_path, 25)
    ids = world.ids(SMALL_ID)
    world.downloader.mirror(ids)
    world.download_all()

    jobs = world.downloader.redownload(ids)

    assert [job.by_hand for job in jobs] == [True] * 20 + [False] * 5


def test_mirror_on_a_download_waiting_for_its_retry_starts_it_now(tmp_path: Path) -> None:
    """R-QU-07, D-090: the user's Mirror does not wait for the automatic retry."""
    world = listed(tmp_path, 1)
    [video_id] = world.ids(SMALL_ID)
    world.download.fail = AppError(ErrorCode.NETWORK_UNREACHABLE, {})
    world.downloader.mirror([video_id])
    world.download_all()
    [waiting] = world.jobs.jobs([JobState.WAITING])
    assert waiting.not_before is not None
    world.download.fail = None

    world.downloader.mirror([video_id])
    world.download_all()

    stored = world.repository.video(video_id)
    assert stored is not None
    assert stored.status is VideoStatus.SYNCED


def test_a_bulk_mirror_is_stored_in_few_writes_and_told_in_few_events(tmp_path: Path) -> None:
    """R-MI-01, R-MI-07, R-FB-03: 300 videos at once, not 900 events and 300 transactions."""
    world = listed(tmp_path, 300)
    ids = world.ids(SMALL_ID)
    writes: list[int] = []
    record, record_many = world.jobs.record, world.jobs.record_many

    def counted(*args: Any, **kwargs: Any) -> None:
        writes.append(1)
        record(*args, **kwargs)

    def counted_many(*args: Any, **kwargs: Any) -> None:
        writes.append(1)
        record_many(*args, **kwargs)

    world.jobs.record = counted  # type: ignore[method-assign]
    world.jobs.record_many = counted_many  # type: ignore[method-assign]
    before = len(world.events)

    jobs = world.downloader.mirror(ids)

    assert len(jobs) == 300
    assert len(writes) <= 2
    told = world.events[before:]
    assert len(told) <= 10, [type(event).__name__ for event in told]
    assert not [event for event in told if isinstance(event, VideoUpdated)]


def test_two_bulk_actions_at_once_never_give_a_video_two_jobs(tmp_path: Path) -> None:
    """R-MI-01, R-QU-02: the presses of two windows, or a double click, queue each video once."""
    world = listed(tmp_path, 120)
    ids = world.ids(SMALL_ID)
    start = threading.Barrier(2)
    errors: list[BaseException] = []

    def press() -> None:
        start.wait()
        try:
            world.downloader.mirror(ids)
        except BaseException as error:  # noqa: BLE001  (each press must succeed)
            errors.append(error)

    presses = [threading.Thread(target=press) for _ in range(2)]
    for thread in presses:
        thread.start()
    for thread in presses:
        thread.join(30)

    assert errors == []
    waiting = world.jobs.jobs([JobState.WAITING])
    assert sorted(job.video_id for job in waiting) == sorted(ids)


def test_paced_rows_are_told_in_a_summary_when_many_change(tmp_path: Path) -> None:
    """R-DT-06, R-FB-03, D-090: the paced times of many rows are one event per channel."""
    world = listed(tmp_path, 200, budget=LookupBudget(per_hour=1))
    ids = world.ids(SMALL_ID)
    before = len(world.events)

    world.downloader.mirror(ids, automatic=True)

    told = world.events[before:]
    assert len(told) <= 10, [type(event).__name__ for event in told]


def test_a_redownload_that_keeps_failing_in_a_way_that_passes_ends_failed(
    tmp_path: Path,
) -> None:
    """R-QU-07, R-QL-06: its tries are counted; after the last delay it fails, synced still."""
    world = listed(tmp_path, 1)
    [video_id] = world.ids(SMALL_ID)
    world.downloader.mirror([video_id])
    world.download_all()
    world.downloader.redownload([video_id])
    world.download.fail = AppError(ErrorCode.NETWORK_UNREACHABLE, {})

    for _ in range(len(RETRY_DELAYS_S) + 2):
        world.clock.advance(max(RETRY_DELAYS_S) + 1)
        world.download_all()

    assert world.jobs.active_job_of(video_id) is None
    assert [job.state for job in world.jobs.jobs([JobState.FAILED])] == [JobState.FAILED]
    assert world.repository.video(video_id).status is VideoStatus.SYNCED  # type: ignore[union-attr]


def test_two_workers_never_start_more_automatic_downloads_than_the_budget_has_room_for(
    tmp_path: Path,
) -> None:
    """R-DT-06, D-090: the worker reserves the lookup as it takes the job."""
    world = listed(tmp_path, 3, budget=LookupBudget(per_hour=1))
    world.settings_repository.save(world.settings.current().__class__(parallel_downloads=2))
    ids = world.ids(SMALL_ID)
    held = threading.Event()

    def hold(_tell: Callable[[DownloadProgress], None]) -> None:
        held.wait(10)

    world.download.during_video = hold
    world.downloader.mirror(ids, automatic=True)
    world.downloader.start()
    workers: list[threading.Thread] = []
    while world.background:
        worker = threading.Thread(target=world.background.pop(0), daemon=True)
        worker.start()
        workers.append(worker)
    deadline = threading.Event()
    deadline.wait(1)
    asked = [job.video_id for job in world.jobs.jobs([JobState.RUNNING])]
    held.set()
    world.downloader.stop(wait_s=10)
    for worker in workers:
        worker.join(10)

    assert len(asked) == 1
