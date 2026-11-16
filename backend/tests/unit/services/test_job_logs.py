"""Tests of the clean-up of the logs of jobs (R-LG-01, docs/LOGGING.md section 3)."""

import dataclasses
from pathlib import Path

import pytest

from tests.fixtures.world import World
from ytmirror.core.channels import Quality, VideoStatus
from ytmirror.core.errors import ErrorCode
from ytmirror.core.jobs import JOB_LOGS_KEPT, Job, JobKind, JobState
from ytmirror.core.status import change_status
from ytmirror.services.job_logs import JobLogsService

DAY = 24 * 60 * 60
VIDEO = "sm000000005"


@pytest.fixture
def world(tmp_path: Path) -> World:
    """The services with the small channel listed."""
    world = World(tmp_path)
    world.add_and_list()
    return world


def ulid(number: int) -> str:
    """Return a ULID-shaped job ID."""
    return f"01JD{number:022d}"


def folder(world: World) -> Path:
    """The folder of the logs of jobs."""
    return world.library.parent / "data" / "logs" / "jobs"


def service(world: World) -> JobLogsService:
    """The clean-up over the world."""
    return JobLogsService(folder(world), world.repository, world.jobs, world.files, world.clock)


def ended_job(world: World, number: int, state: JobState, ended: int, video: str = VIDEO) -> str:
    """Store an ended job of a video and its log. Returns the job ID."""
    job = Job(
        id=ulid(number),
        video_id=video,
        kind=JobKind.DOWNLOAD,
        state=state,
        priority=number,
        quality=Quality.BEST,
        created_at=ended,
        error_code=ErrorCode.NETWORK_UNREACHABLE if state is JobState.FAILED else None,
        finished_at=ended,
    )
    world.jobs.record(job)
    world.files.add_files(folder(world), [f"{job.id}.log"])
    return job.id


def set_status(world: World, status: VideoStatus) -> None:
    """Give the video a status, through the status machine."""
    video = world.repository.video(VIDEO)
    assert video is not None
    path = {
        VideoStatus.FAILED: [VideoStatus.QUEUED, VideoStatus.DOWNLOADING, VideoStatus.FAILED],
        VideoStatus.SYNCED: [
            VideoStatus.QUEUED,
            VideoStatus.DOWNLOADING,
            VideoStatus.PROCESSING,
            VideoStatus.SYNCED,
        ],
    }[status]
    for step in path:
        current = world.repository.video(VIDEO)
        assert current is not None
        world.jobs.record(
            world.jobs.jobs([JobState.FAILED, JobState.DONE])[0],
            dataclasses.replace(current, status=step),
            change_status(VIDEO, current.status, step, "test"),
        )


def logs(world: World) -> list[str]:
    """Return the names in the folder of the logs of jobs."""
    return world.files.file_names(folder(world))


def test_an_old_log_of_a_video_that_is_still_failed_is_kept(world: World) -> None:
    """R-LG-01: the latest failed attempt's log stays while the video is failed, however old."""
    job_id = ended_job(world, 1, JobState.FAILED, world.now() - 400 * DAY)
    set_status(world, VideoStatus.FAILED)

    deleted = service(world).clean()

    assert deleted == 0
    assert logs(world) == [f"{job_id}.log"]


def test_a_failed_log_goes_fourteen_days_after_its_video_stopped_failing(world: World) -> None:
    """R-LG-01: the 14 days count from when the video stopped being failed."""
    ended_job(world, 1, JobState.FAILED, world.now() - 400 * DAY)
    set_status(world, VideoStatus.FAILED)
    world.clock.advance(-15 * DAY)
    set_status(world, VideoStatus.SYNCED)
    world.clock.advance(15 * DAY)

    deleted = service(world).clean()

    assert deleted == 1
    assert logs(world) == []


def test_a_failed_log_stays_within_fourteen_days_after_its_video_stopped_failing(
    world: World,
) -> None:
    """R-LG-01: a video that synced 13 days ago keeps the log of its failure."""
    job_id = ended_job(world, 1, JobState.FAILED, world.now() - 400 * DAY)
    set_status(world, VideoStatus.FAILED)
    world.clock.advance(-13 * DAY)
    set_status(world, VideoStatus.SYNCED)
    world.clock.advance(13 * DAY)

    service(world).clean()

    assert logs(world) == [f"{job_id}.log"]


def test_only_the_fifty_newest_logs_of_other_jobs_are_kept(world: World) -> None:
    """R-LG-01: of the jobs that did not fail, the oldest log beyond fifty goes."""
    ids = [
        ended_job(world, number, JobState.DONE, world.now() - number)
        for number in range(1, JOB_LOGS_KEPT + 2)
    ]

    deleted = service(world).clean()

    assert deleted == 1
    assert f"{ids[-1]}.log" not in logs(world)
    assert len(logs(world)) == JOB_LOGS_KEPT


def test_a_file_with_another_name_in_the_log_folder_is_never_touched(world: World) -> None:
    """R-LG-01: only files named like a job log are ever deleted."""
    world.files.add_files(folder(world), ["notes.txt", "01JD-not-a-ulid.log", ".DS_Store"])

    service(world).clean()

    assert world.files.file_names(folder(world), hidden=True) == [
        ".DS_Store",
        "01JD-not-a-ulid.log",
        "notes.txt",
    ]


def test_a_log_without_its_job_is_the_oldest_and_goes_first(world: World) -> None:
    """R-LG-01: the log of a job of a removed channel is no longer needed."""
    for number in range(1, JOB_LOGS_KEPT + 1):
        ended_job(world, number, JobState.DONE, world.now() - number)
    world.files.add_files(folder(world), [f"{ulid(999)}.log"])

    service(world).clean()

    assert f"{ulid(999)}.log" not in logs(world)


def test_the_folder_refuses_to_delete_anything_but_a_job_log(world: World) -> None:
    """R-LG-01: the delete itself refuses every other file."""
    world.files.add_files(folder(world), ["notes.txt"])

    with pytest.raises(ValueError, match="not the log of a job"):
        world.files.remove_job_log(folder(world) / "notes.txt")
