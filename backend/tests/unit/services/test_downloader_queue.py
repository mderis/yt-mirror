"""Tests of the queue of the downloader: parallel workers, abandoned lookups, held progress."""

import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.fixtures.world import World
from ytmirror.core.channels import VideoStatus
from ytmirror.core.jobs import DownloadProgress, JobProgressed, JobState, Stage
from ytmirror.core.models import Settings

FIRST = "sm000000005"
SECOND = "sm000000004"
THIRD = "sm000000003"


@pytest.fixture
def world(tmp_path: Path) -> World:
    """A world with the small channel added and listed."""
    world = World(tmp_path)
    world.add_and_list()
    return world


def parallel(world: World, count: int) -> None:
    """Set how many downloads may run at once."""
    world.settings_repository.save(Settings(parallel_downloads=count))


def status_of(world: World, video_id: str) -> VideoStatus:
    """Return the stored status of a video."""
    video = world.repository.video(video_id)
    assert video is not None
    return video.status


def eventually(condition: Callable[[], bool], what: str) -> None:
    """Wait up to 10 seconds for a condition that threads make true."""
    deadline = time.monotonic() + 10
    while not condition():
        assert time.monotonic() < deadline, what
        time.sleep(0.01)


def start_workers(world: World) -> list[threading.Thread]:
    """Start the downloader and run each worker it hands to the background in a thread."""
    world.downloader.start()
    return run_new_workers(world)


def run_new_workers(world: World) -> list[threading.Thread]:
    """Run the workers that the downloader handed to the background since the last call."""
    threads: list[threading.Thread] = []
    while world.background:
        thread = threading.Thread(target=world.background.pop(0), daemon=True)
        thread.start()
        threads.append(thread)
    return threads


def hold(world: World, *video_ids: str) -> dict[str, threading.Event]:
    """Hold the metadata lookup of these videos until their event is set."""
    for video_id in video_ids:
        world.download.held[video_id] = threading.Event()
        world.download.asked[video_id] = threading.Event()
    return world.download.held


def stop(world: World, threads: list[threading.Thread]) -> None:
    """Let every held lookup answer, stop the downloader and wait for its workers."""
    for event in world.download.held.values():
        event.set()
    world.downloader.stop(wait_s=10)
    for thread in threads:
        thread.join(10)


# --- parallel downloads (R-QU-01)


def test_as_many_downloads_run_at_once_as_the_setting_allows(world: World) -> None:
    """R-QU-01: with the default of two, two downloads run and the third waits for a place."""
    held = hold(world, FIRST, SECOND, THIRD)
    workers = start_workers(world)
    assert len(workers) == 2

    world.downloader.mirror([FIRST, SECOND, THIRD])

    assert world.download.asked[FIRST].wait(10)
    assert world.download.asked[SECOND].wait(10)
    time.sleep(0.2)
    assert not world.download.asked[THIRD].is_set()
    assert status_of(world, THIRD) is VideoStatus.QUEUED

    held[FIRST].set()
    assert world.download.asked[THIRD].wait(10)
    held[SECOND].set()
    held[THIRD].set()
    eventually(
        lambda: all(status_of(world, v) is VideoStatus.SYNCED for v in (FIRST, SECOND, THIRD)),
        "every video was downloaded",
    )
    stop(world, workers)


def test_with_one_parallel_download_they_run_one_after_another(world: World) -> None:
    """R-QU-01: the setting of one runs a single download at a time, in the order of the line."""
    parallel(world, 1)
    held = hold(world, FIRST, SECOND)
    workers = start_workers(world)
    assert len(workers) == 1

    world.downloader.mirror([FIRST, SECOND])

    assert world.download.asked[FIRST].wait(10)
    time.sleep(0.2)
    assert not world.download.asked[SECOND].is_set()
    held[FIRST].set()
    assert world.download.asked[SECOND].wait(10)
    stop(world, workers)


def test_a_higher_setting_adds_workers_without_a_restart(world: World) -> None:
    """R-QU-01: more places take effect at the next Mirror, with no restart."""
    workers = start_workers(world)
    parallel(world, 4)

    world.downloader.mirror([FIRST])

    workers += run_new_workers(world)
    assert len(workers) == 4
    stop(world, workers)


def test_a_lower_setting_ends_the_workers_that_are_too_many(world: World) -> None:
    """R-QU-01: fewer places take effect without a restart: idle workers that are too many end."""
    workers = start_workers(world)
    parallel(world, 1)

    world.downloader.mirror([FIRST])

    eventually(lambda: sum(thread.is_alive() for thread in workers) == 1, "one worker ended")
    eventually(lambda: status_of(world, FIRST) is VideoStatus.SYNCED, "the video was downloaded")
    stop(world, workers)


def test_no_job_is_taken_while_every_place_is_taken(world: World) -> None:
    """R-QU-01: a worker that wakes while every place is taken finds nothing to do."""
    parallel(world, 1)
    held = hold(world, FIRST)
    world.downloader.mirror([FIRST, SECOND])
    first = threading.Thread(target=world.downloader.work_once, daemon=True)
    first.start()
    assert world.download.asked[FIRST].wait(10)

    assert world.downloader.work_once() is False

    held[FIRST].set()
    first.join(10)
    assert world.downloader.work_once() is True


# --- an abandoned lookup takes no place (R-QU-02)


@pytest.mark.parametrize("places", [1, 2])
def test_a_download_cancelled_while_youtube_is_asked_frees_its_place_at_once(
    world: World, places: int
) -> None:
    """R-QU-01, R-QU-02: the next download starts before the abandoned lookup answers.

    The abandoned lookup waits for YouTube on its own; it holds neither a worker
    nor a place in the queue, also when only one download may run.
    """
    parallel(world, places)
    held = hold(world, FIRST, *([SECOND] if places == 2 else []))
    workers = start_workers(world)
    jobs = world.downloader.mirror([FIRST, SECOND, THIRD])
    assert world.download.asked[FIRST].wait(10)
    if places == 2:
        assert world.download.asked[SECOND].wait(10)
    waiting = SECOND if places == 1 else THIRD

    world.downloader.cancel(jobs[0].id)
    workers += run_new_workers(world)
    if places == 2:
        held[SECOND].set()

    eventually(lambda: status_of(world, waiting) is VideoStatus.SYNCED, "the next one ran")
    assert not held[FIRST].is_set(), "YouTube has not answered the abandoned lookup yet"
    assert status_of(world, FIRST) is VideoStatus.NOT_DOWNLOADED
    held[FIRST].set()
    stop(world, workers)
    assert status_of(world, FIRST) is VideoStatus.NOT_DOWNLOADED


def test_the_worker_of_an_abandoned_lookup_ends_when_youtube_answers(world: World) -> None:
    """R-QU-01, R-QU-02: the replaced worker ends, so the workers stay as many as allowed."""
    parallel(world, 1)
    held = hold(world, FIRST)
    workers = start_workers(world)
    [job] = world.downloader.mirror([FIRST])
    assert world.download.asked[FIRST].wait(10)
    world.downloader.cancel(job.id)
    workers += run_new_workers(world)

    held[FIRST].set()

    eventually(lambda: not workers[0].is_alive(), "the replaced worker ended")
    assert workers[1].is_alive()
    stop(world, workers)


# --- side files are written by one worker at a time


def test_side_files_that_waited_are_written_by_one_worker_at_a_time(world: World) -> None:
    """R-MD-02, R-QA-06: a second worker does not write the same waiting side files again."""
    inside = threading.Event()
    go = threading.Event()
    calls: list[int] = []

    def slow() -> None:
        calls.append(1)
        inside.set()
        go.wait(10)

    world.downloader._write_waiting_side_files = slow  # type: ignore[method-assign]
    first = threading.Thread(target=world.downloader.retry_side_files, daemon=True)
    first.start()
    assert inside.wait(10)

    world.downloader.retry_side_files()

    go.set()
    first.join(10)
    assert calls == [1]


# --- the last progress report is told after a stall (R-QU-04)


def told(world: World) -> list[float | None]:
    """Return the fractions of the video stage that were told to the window."""
    return [
        event.progress.fraction
        for event in world.events
        if isinstance(event, JobProgressed) and event.progress.stage is Stage.VIDEO
    ]


def report(fraction: float) -> DownloadProgress:
    """A progress report of the video stream."""
    return DownloadProgress(stage=Stage.VIDEO, fraction=fraction, speed_bps=1e6, left_s=5)


def test_a_report_that_came_too_soon_is_told_when_no_newer_one_follows(world: World) -> None:
    """R-QU-04: when a download stalls, the row shows its last report, not an older one.

    Reports come at most four times a second. One that comes sooner is kept back
    and told once the quarter second is over, if nothing newer was told by then.
    """
    world.later.clear()

    def stalls(tell: Callable[[DownloadProgress], None]) -> None:
        tell(report(0.1))
        world.clock.advance(0.1)
        tell(report(0.2))  # too soon: kept back
        assert told(world) == [0.1]
        [(delay, send)] = world.later
        assert delay == pytest.approx(0.15)
        world.later.clear()
        world.clock.advance(delay)
        send()  # the download stalls: nothing newer came
        assert told(world) == [0.1, 0.2]

    world.download.during_video = stalls
    world.downloader.mirror([FIRST])

    world.download_all()

    assert told(world)[:2] == [0.1, 0.2]


def test_a_kept_back_report_is_dropped_when_a_newer_one_was_told(world: World) -> None:
    """R-QU-04: the trailing send never tells an older report after a newer one."""
    world.later.clear()
    sends: list[Callable[[], None]] = []

    def steady(tell: Callable[[DownloadProgress], None]) -> None:
        tell(report(0.1))
        world.clock.advance(0.1)
        tell(report(0.2))  # kept back
        sends.extend(work for _delay, work in world.later)
        world.later.clear()
        world.clock.advance(0.2)
        tell(report(0.3))  # in time: told, and the kept one is dropped
        for send in sends:
            send()

    world.download.during_video = steady
    world.downloader.mirror([FIRST])

    world.download_all()

    assert told(world)[:2] == [0.1, 0.3]
    assert 0.2 not in told(world)


def test_a_kept_back_report_is_not_told_after_its_download_ended(world: World) -> None:
    """R-QU-04, R-QU-02: a report kept back from a download that ended is never told afterwards.

    Here the download is cancelled right after a report was kept back.
    """
    world.later.clear()
    [job] = world.downloader.mirror([FIRST])

    def cancelled(tell: Callable[[DownloadProgress], None]) -> None:
        tell(report(0.1))
        world.clock.advance(0.1)
        tell(report(0.2))
        world.downloader.cancel(job.id)

    world.download.during_video = cancelled
    world.download_all()
    assert world.jobs.jobs([JobState.WAITING, JobState.RUNNING]) == ()
    assert status_of(world, FIRST) is VideoStatus.NOT_DOWNLOADED
    before = told(world)

    for _delay, send in world.later:
        send()

    assert told(world) == before
