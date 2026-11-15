"""Tests of the job repository on a real, migrated database."""

import dataclasses
from pathlib import Path

import pytest
from sqlalchemy import Engine

from tests.fixtures.catalogue import CHANNEL_ID, NOW, make_channel, make_video, video_id
from tests.fixtures.database import migrated_engine
from tests.fixtures.fakes.clock import FakeClock
from ytmirror.adapters.db.catalogue_repository import SqlCatalogueRepository
from ytmirror.adapters.db.job_repository import SqlJobRepository
from ytmirror.core.catalogue import CheckChanges
from ytmirror.core.channels import DatePrecision, Quality, VideoStatus
from ytmirror.core.errors import ErrorCode
from ytmirror.core.jobs import Job, JobKind, JobState, Stage, VideoEvent
from ytmirror.core.status import change_status


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    """A migrated database with one channel and three videos."""
    engine = migrated_engine(tmp_path)
    catalogue = SqlCatalogueRepository(engine, FakeClock())
    catalogue.add_channel(make_channel())
    catalogue.apply_check(
        make_channel(),
        CheckChanges(
            inserted=tuple(make_video(number) for number in (1, 2, 3)),
            updated=(),
            new=0,
            changed=0,
            removed=0,
            returned=0,
            read=0,
        ),
    )
    return engine


@pytest.fixture
def jobs(engine: Engine, clock: FakeClock) -> SqlJobRepository:
    """The repository under test."""
    return SqlJobRepository(engine, clock)


def a_job(number: int, priority: int, state: JobState = JobState.WAITING) -> Job:
    """Return a download job of video ``number``."""
    return Job(
        id=f"01JOB{number:05d}",
        video_id=video_id(number),
        kind=JobKind.DOWNLOAD,
        state=state,
        priority=priority,
        quality=Quality.P1080,
        created_at=NOW + number,
    )


def test_a_job_its_video_and_the_status_change_are_stored_together(
    engine: Engine, jobs: SqlJobRepository, clock: FakeClock
) -> None:
    """R-LG-03, R-LG-02: the status change is recorded with its time, reason and job ID."""
    video = make_video(1)
    queued = dataclasses.replace(video, status=VideoStatus.QUEUED)
    change = change_status(video.id, video.status, VideoStatus.QUEUED, "mirror")

    jobs.record(a_job(1, priority=1), queued, change)

    stored = SqlCatalogueRepository(engine, clock).video(video.id)
    assert stored is not None
    assert stored.status is VideoStatus.QUEUED
    assert jobs.job("01JOB00001") == a_job(1, priority=1)
    assert jobs.events(video.id) == (
        VideoEvent(
            video_id=video.id,
            at=int(clock.now().timestamp()),
            from_status="not_downloaded",
            to_status="queued",
            reason="mirror",
            job_id="01JOB00001",
        ),
    )


def test_a_job_is_updated_in_place(jobs: SqlJobRepository) -> None:
    """R-LG-02: one job keeps one row through its life."""
    jobs.record(a_job(1, priority=1))
    running = dataclasses.replace(
        a_job(1, priority=1), state=JobState.RUNNING, stage=Stage.VIDEO, started_at=NOW + 5
    )
    failed = dataclasses.replace(
        running, state=JobState.FAILED, error_code=ErrorCode.MEMBERS_ONLY, finished_at=NOW + 9
    )

    jobs.record(running)
    jobs.record(failed)

    assert jobs.job(running.id) == failed
    assert jobs.jobs([JobState.FAILED]) == (failed,)


def test_waiting_jobs_come_in_the_order_of_their_priority(jobs: SqlJobRepository) -> None:
    """R-MI-01: pressing Mirror on several videos puts them in line in that order."""
    for number, priority in ((1, 3), (2, 1), (3, 2)):
        jobs.record(a_job(number, priority))

    order = [job.video_id for job in jobs.jobs([JobState.WAITING])]

    assert order == [video_id(2), video_id(3), video_id(1)]
    assert jobs.next_priority() == 4


def test_a_video_has_at_most_one_active_job_and_finished_jobs_do_not_count(
    jobs: SqlJobRepository,
) -> None:
    """R-MI-01: the job of a video that waits or runs is found, and an ended one is not."""
    jobs.record(a_job(1, priority=1, state=JobState.CANCELLED))
    jobs.record(a_job(2, priority=2, state=JobState.RUNNING))

    assert jobs.active_job_of(video_id(1)) is None
    assert jobs.active_job_of(video_id(2)) == a_job(2, priority=2, state=JobState.RUNNING)
    assert jobs.next_priority() == 3


def test_a_check_that_ran_during_a_download_does_not_undo_it(
    engine: Engine, jobs: SqlJobRepository, clock: FakeClock
) -> None:
    """R-QA-06, R-DT-05: a check that read a video before its download ended keeps the download."""
    catalogue = SqlCatalogueRepository(engine, clock)
    read_by_the_check = catalogue.video(video_id(1))
    assert read_by_the_check is not None
    synced = dataclasses.replace(
        read_by_the_check,
        status=VideoStatus.SYNCED,
        file_name="Video 1.mkv",
        file_size=1234,
        height=1080,
        published_at=NOW - 3600,
        published_exact=True,
        published_precision=None,
    )
    jobs.record(a_job(1, priority=1, state=JobState.DONE), synced)
    retitled = dataclasses.replace(
        read_by_the_check,
        title="Video 1, now with a better title",
        published_at=NOW - 86_400 * 3,
        published_precision=DatePrecision.DAY,
    )

    catalogue.apply_check(make_channel(), CheckChanges((), (retitled,), 0, 1, 0, 0, 1))

    stored = catalogue.video(video_id(1))
    assert stored is not None
    assert stored.title == "Video 1, now with a better title"
    assert stored.status is VideoStatus.SYNCED
    assert (stored.file_name, stored.file_size, stored.height) == ("Video 1.mkv", 1234, 1080)
    assert (stored.published_at, stored.published_exact) == (NOW - 3600, True)


def test_a_check_still_gives_an_approximate_date_to_a_video_without_an_exact_one(
    engine: Engine, clock: FakeClock
) -> None:
    """R-DT-04: a listing's date is stored while no exact date is known."""
    catalogue = SqlCatalogueRepository(engine, clock)
    before = catalogue.video(video_id(2))
    assert before is not None
    later = dataclasses.replace(
        before, published_at=NOW - 86_400 * 30, published_precision=DatePrecision.MONTH
    )

    catalogue.apply_check(make_channel(), CheckChanges((), (later,), 0, 0, 0, 0, 1))

    stored = catalogue.video(video_id(2))
    assert stored is not None
    assert (stored.published_at, stored.published_precision) == (
        NOW - 86_400 * 30,
        DatePrecision.MONTH,
    )


def test_the_tracked_files_of_a_channel_are_its_file_names(
    jobs: SqlJobRepository, engine: Engine, clock: FakeClock
) -> None:
    """R-CH-32: the files the app tracks for a channel are known by name."""
    video = SqlCatalogueRepository(engine, clock).video(video_id(3))
    assert video is not None
    jobs.record(
        a_job(3, priority=1, state=JobState.DONE),
        dataclasses.replace(video, status=VideoStatus.SYNCED, file_name="Video 3.mkv"),
    )

    assert jobs.tracked_files(CHANNEL_ID) == ("Video 3.mkv",)
    assert jobs.tracked_files("UCother") == ()
