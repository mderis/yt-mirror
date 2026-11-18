"""Tests of the queue of the downloader: parallel workers, abandoned lookups, held progress."""

import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from sqlalchemy import text
from structlog.testing import capture_logs

from tests.fixtures.world import SMALL_ID, World, channel_file
from ytmirror.core.channels import VideoStatus
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.jobs import DownloadProgress, JobProgressed, JobState, Stage
from ytmirror.core.models import Settings
from ytmirror.core.pacing import LookupBudget
from ytmirror.core.queue import QueueChanged, QueueSummary

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


# --- the order of the line, pause all, clear waiting (R-QU-02)


def waiting_order(world: World) -> list[str]:
    """Return the videos of the waiting jobs, in the order they will run."""
    return [job.video_id for job in world.jobs.jobs([JobState.WAITING])]


def test_mirror_first_puts_videos_at_the_top_of_the_line_in_their_order(world: World) -> None:
    """R-QU-02: "Mirror first" puts the videos ahead of every waiting one, in the order given."""
    world.downloader.mirror([FIRST, SECOND])

    world.downloader.mirror([THIRD, "sm000000002"], first=True)

    assert waiting_order(world) == [THIRD, "sm000000002", FIRST, SECOND]


def test_mirror_first_on_a_waiting_video_moves_it_to_the_top(world: World) -> None:
    """R-QU-02: "Mirror first" on a video that waits already moves it, without a second job."""
    world.downloader.mirror([FIRST, SECOND, THIRD])

    queued = world.downloader.mirror([THIRD], first=True)

    assert queued == []
    assert waiting_order(world) == [THIRD, FIRST, SECOND]
    world.download_all()
    assert [request.video_id for request in world.download.calls] == [THIRD, FIRST, SECOND]


def test_reorder_runs_the_waiting_downloads_in_the_new_order(world: World) -> None:
    """R-QU-02: after a drag and drop the downloads run in the order the user chose."""
    jobs = world.downloader.mirror([FIRST, SECOND, THIRD])

    world.downloader.reorder([jobs[2].id, jobs[0].id, jobs[1].id])

    assert waiting_order(world) == [THIRD, FIRST, SECOND]
    world.download_all()
    assert [request.video_id for request in world.download.calls] == [THIRD, FIRST, SECOND]


def test_a_job_put_in_line_later_stays_behind_a_reordered_line(world: World) -> None:
    """R-QU-02: a reorder that does not name a newer job keeps it at the end."""
    jobs = world.downloader.mirror([FIRST, SECOND])
    world.downloader.mirror([THIRD])

    world.downloader.reorder([jobs[1].id, jobs[0].id])

    assert waiting_order(world) == [SECOND, FIRST, THIRD]


def test_pause_all_holds_every_download_until_resume(world: World) -> None:
    """R-QU-02: nothing starts while all downloads are paused; resume all starts them again."""
    world.downloader.mirror([FIRST])

    world.downloader.pause_all()

    assert world.downloader.work_once() is False
    assert status_of(world, FIRST) is VideoStatus.QUEUED
    world.downloader.resume_all()
    assert world.downloader.work_once() is True
    assert status_of(world, FIRST) is VideoStatus.SYNCED


def test_pause_all_is_kept_across_a_restart(world: World) -> None:
    """R-QU-02, spec section 10: "Pause all downloads" is a stored setting."""
    world.downloader.pause_all()

    assert world.settings.current().downloads_paused is True
    world.downloader.resume_all()
    assert world.settings.current().downloads_paused is False


def test_clear_waiting_removes_every_waiting_download(world: World) -> None:
    """R-QU-02: "Clear waiting" removes the waiting items; their videos are not downloaded."""
    world.downloader.mirror([FIRST, SECOND])

    assert world.downloader.clear_waiting() == 2

    assert world.jobs.jobs([JobState.WAITING, JobState.RUNNING]) == ()
    assert status_of(world, FIRST) is VideoStatus.NOT_DOWNLOADED
    assert status_of(world, SECOND) is VideoStatus.NOT_DOWNLOADED


def test_clear_waiting_leaves_a_running_download_alone(world: World) -> None:
    """R-QU-02: only waiting items are cleared; the running one goes on."""
    held = hold(world, FIRST)
    world.downloader.mirror([FIRST, SECOND])
    worker = threading.Thread(target=world.downloader.work_once, daemon=True)
    worker.start()
    assert world.download.asked[FIRST].wait(10)

    assert world.downloader.clear_waiting() == 1

    held[FIRST].set()
    worker.join(10)
    assert status_of(world, FIRST) is VideoStatus.SYNCED
    assert status_of(world, SECOND) is VideoStatus.NOT_DOWNLOADED


# --- the summary of the queue


def summaries(world: World) -> list[QueueSummary]:
    """Return every summary of the queue that was told, in order."""
    return [event.summary for event in world.events if isinstance(event, QueueChanged)]


def test_the_queue_is_told_when_it_changes(world: World) -> None:
    """R-FB-03, R-QU-02: the queue bar hears of every job put in line, started and ended."""
    world.events.clear()

    world.downloader.mirror([FIRST, SECOND])
    world.download_all()

    told = [(summary.downloading, summary.waiting) for summary in summaries(world)]
    assert told[:2] == [(0, 1), (0, 2)]
    assert (1, 1) in told
    assert told[-1] == (0, 0)


def test_the_summary_counts_failed_videos_and_says_when_paused(world: World) -> None:
    """R-QU-08, R-QU-02: the summary has the failed videos and the pause of all downloads."""
    world.download.fail = AppError(ErrorCode.VIDEO_PRIVATE, {})
    world.downloader.mirror([FIRST])
    world.download_all()

    world.downloader.pause_all()

    assert world.downloader.queue_summary() == QueueSummary(
        downloading=0, waiting=0, failed=1, paused=True, places=2
    )


# --- jobs started by hand (R-DT-06, D-090) and excluded videos (R-MI-05)


def test_the_first_20_jobs_of_one_action_are_started_by_hand(tmp_path: Path) -> None:
    """R-DT-06, D-090: one action's first 20 jobs pass the budget, the rest are automatic."""
    world = World(tmp_path, channel_file(videos=25))
    world.add_and_list()

    jobs = world.downloader.mirror(world.ids(SMALL_ID))

    assert [job.by_hand for job in jobs] == [True] * 20 + [False] * 5
    assert [job.by_hand for job in world.jobs.jobs([JobState.WAITING])] == [True] * 20 + [False] * 5


def test_mirror_on_a_waiting_automatic_job_makes_it_one_started_by_hand(tmp_path: Path) -> None:
    """R-DT-06, D-090: pressing Mirror on a paced job lets it pass the budget."""
    world = World(tmp_path, channel_file(videos=25))
    world.add_and_list()
    ids = world.ids(SMALL_ID)
    jobs = world.downloader.mirror(ids)
    last = jobs[-1]
    assert last.by_hand is False

    assert world.downloader.mirror([ids[-1]]) == []

    assert world.jobs.job(last.id).by_hand is True  # type: ignore[union-attr]


def test_an_excluded_video_is_never_put_in_line(world: World) -> None:
    """R-MI-05: Mirror and Retry refuse an excluded video."""
    with world.engine.begin() as connection:
        connection.execute(text("UPDATE videos SET excluded = 1 WHERE id = :id"), {"id": FIRST})

    assert world.downloader.mirror([FIRST]) == []
    assert status_of(world, FIRST) is VideoStatus.NOT_DOWNLOADED


# --- automatic downloads wait for room in the lookup budget (R-DT-06, D-090)


def paced_world(tmp_path: Path) -> tuple[World, list[str]]:
    """A world whose budget allows one lookup an hour, with a channel of 25 videos listed."""
    world = World(tmp_path, channel_file(videos=25), budget=LookupBudget(per_hour=1))
    world.add_and_list()
    return world, world.ids(SMALL_ID)


def test_downloads_started_by_hand_never_wait_for_the_budget(tmp_path: Path) -> None:
    """R-DT-06, D-090: the 20 jobs of one action that are started by hand run at once."""
    world, ids = paced_world(tmp_path)
    world.downloader.mirror(ids[:20])

    world.download_all()

    assert all(status_of(world, video_id) is VideoStatus.SYNCED for video_id in ids[:20])


def test_an_automatic_download_waits_for_room_and_says_until_when(tmp_path: Path) -> None:
    """R-DT-06, D-090: beyond the budget an automatic download waits, and its row says when."""
    world, ids = paced_world(tmp_path)
    world.downloader.mirror(ids[:21])  # the 21st is automatic

    world.download_all()

    assert status_of(world, ids[20]) is VideoStatus.QUEUED
    view = world.views.video(ids[20])
    assert view is not None
    assert view.paced_until is not None
    assert view.paced_until > world.now()
    [paced] = world.queue.view().waiting
    assert paced.paced_until == view.paced_until


def test_an_automatic_download_starts_when_the_budget_has_room_again(tmp_path: Path) -> None:
    """R-DT-06, D-090: an hour after the lookups that filled it, the paced download runs."""
    world, ids = paced_world(tmp_path)
    world.downloader.mirror(ids[:21])
    world.download_all()
    view = world.views.video(ids[20])
    assert view is not None
    assert view.paced_until is not None

    world.clock.advance(view.paced_until - world.now() + 1)

    assert world.downloader.work_once() is True
    assert status_of(world, ids[20]) is VideoStatus.SYNCED


def test_a_later_download_started_by_hand_goes_ahead_of_a_paced_one(tmp_path: Path) -> None:
    """R-DT-06, D-090: a paced download never holds back one started by hand behind it."""
    world, ids = paced_world(tmp_path)
    world.downloader.mirror(ids[:21])
    world.download_all()

    world.downloader.mirror([ids[21]])
    world.download_all()

    assert status_of(world, ids[21]) is VideoStatus.SYNCED
    assert status_of(world, ids[20]) is VideoStatus.QUEUED


def test_mirror_on_a_paced_download_starts_it_without_waiting(tmp_path: Path) -> None:
    """R-DT-06, D-090: Mirror on a waiting automatic download makes it one started by hand."""
    world, ids = paced_world(tmp_path)
    world.downloader.mirror(ids[:21])
    world.download_all()

    world.downloader.mirror([ids[20]])
    world.download_all()

    assert status_of(world, ids[20]) is VideoStatus.SYNCED
    view = world.views.video(ids[20])
    assert view is not None
    assert view.paced_until is None


# --- a stopped download continues from its partial files (R-QU-05, D-091)


def temp_of(world: World, job_id: str) -> Path:
    """The temp folder of a job in the folder of the small channel."""
    channel = world.repository.channel(SMALL_ID)
    assert channel is not None
    return world.views.folder_of(channel) / ".yt-mirror" / "tmp" / job_id


def test_pause_all_stops_a_running_download_and_keeps_its_partial_file(world: World) -> None:
    """R-QU-02, R-QU-05, D-091: a paused download goes back in line and continues on resume."""
    [job] = world.downloader.mirror([FIRST])
    world.download.cancel_at = Stage.AUDIO
    world.download.on_cancel = world.downloader.pause_all

    world.download_all()

    assert status_of(world, FIRST) is VideoStatus.QUEUED
    assert world.jobs.job(job.id).state is JobState.WAITING  # type: ignore[union-attr]
    assert world.files.exists(temp_of(world, job.id) / f"{FIRST}.f399.mp4.part")
    world.download.cancel_at = None
    world.downloader.resume_all()
    world.download_all()
    assert status_of(world, FIRST) is VideoStatus.SYNCED
    assert world.download.calls[-1].formats == "399+251"
    assert world.files.exists(temp_of(world, job.id)) is False


def test_the_not_a_bot_check_keeps_the_partial_file_of_a_download(world: World) -> None:
    """R-ER-05, R-QU-05, D-091: a download held back by YouTube's check continues later."""
    [job] = world.downloader.mirror([FIRST])

    def refused(_tell: Callable[[DownloadProgress], None]) -> None:
        raise AppError(ErrorCode.BOT_CHECK, {})

    world.download.during_video = refused

    world.download_all()

    assert status_of(world, FIRST) is VideoStatus.QUEUED
    assert world.jobs.job(job.id).state is JobState.WAITING  # type: ignore[union-attr]
    assert world.files.exists(temp_of(world, job.id) / f"{FIRST}.f399.mp4.part")


def test_a_user_cancel_still_deletes_what_was_downloaded(world: World) -> None:
    """R-QU-02, D-091: only a quit, a pause or YouTube's check keep files; Cancel never does."""
    [job] = world.downloader.mirror([FIRST])
    world.download.cancel_at = Stage.AUDIO
    world.download.on_cancel = lambda: world.downloader.cancel(job.id)

    world.download_all()

    assert status_of(world, FIRST) is VideoStatus.NOT_DOWNLOADED
    assert world.files.exists(temp_of(world, job.id)) is False


def test_a_download_stopped_while_its_file_was_processed_starts_over(world: World) -> None:
    """R-QU-05, D-091: a finished file in the temp folder means processing was cut off."""
    [job] = world.downloader.mirror([FIRST])
    work = temp_of(world, job.id)
    world.files.add_files(work, [f"{FIRST}.mkv", f"{FIRST}.f399.mp4"])

    with capture_logs() as logs:
        world.download_all()

    assert status_of(world, FIRST) is VideoStatus.SYNCED
    [line] = [line for line in logs if line["event"] == "download.resumed"]
    assert "starts over" in str(line["msg"])


def test_a_drive_that_comes_back_is_cleaned_up_without_a_restart(world: World) -> None:
    """R-QA-06, R-FI-03: left-overs of an ended job go; the temp folder of a waiting one stays."""
    [waiting] = world.downloader.mirror([FIRST])
    ended = "01JD0000000000000000000099"
    world.files.add_files(temp_of(world, ended), ["old.part"])
    world.files.add_files(temp_of(world, waiting.id), [f"{FIRST}.f399.mp4.part"])

    world.check(SMALL_ID)

    assert world.files.exists(temp_of(world, ended)) is False
    assert world.files.exists(temp_of(world, waiting.id) / f"{FIRST}.f399.mp4.part")
