"""Tests of migration 0006, which adds the jobs and the status history of videos."""

from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from tests.migrations.helpers import new_database, table_names, upgrade_to

CHANNEL = (
    "INSERT INTO channels (id, url, title, folder, folder_is_custom, auto_mirror, paused,"
    " position, created_at, updated_at)"
    " VALUES ('UCa', 'u', 'A channel', 'A channel', 0, 0, 0, 0, 1, 1)"
)
VIDEO = (
    "INSERT INTO videos (id, channel_id, title, published_exact, channel_position, status,"
    " excluded, exclude_exception, missing_checks, gone, first_seen_at, last_seen_at,"
    " seen_in_first_listing, attempts, created_at, updated_at)"
    " VALUES ('v1', 'UCa', 'A video', 0, 0, 'not_downloaded', 0, 0, 0, 0, 1, 1, 1, 0, 1, 1)"
)
JOB = (
    "INSERT INTO jobs (id, video_id, kind, state, priority, quality, created_at, updated_at)"
    " VALUES ('01JOB', 'v1', 'download', 'waiting', 1, 'best', 2, 2)"
)
EVENT = (
    "INSERT INTO video_events (video_id, at, from_status, to_status, reason, job_id,"
    " created_at, updated_at) VALUES ('v1', 2, 'not_downloaded', 'queued', 'mirror', '01JOB', 2, 2)"
)


def test_the_upgrade_keeps_the_catalogue_and_starts_without_jobs(tmp_path: Path) -> None:
    """R-QA-04: a database of the version before keeps its videos, and has no jobs or history."""
    engine = new_database(tmp_path)
    upgrade_to(engine, "0005")
    with engine.begin() as connection:
        connection.execute(text(CHANNEL))
        connection.execute(text(VIDEO))

    upgrade_to(engine, "0006")

    assert {"jobs", "video_events"} <= table_names(engine)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT id, status FROM videos")).all() == [
            ("v1", "not_downloaded")
        ]
        assert connection.execute(text("SELECT count(*) FROM jobs")).scalar() == 0
        assert connection.execute(text("SELECT count(*) FROM video_events")).scalar() == 0


def test_a_status_change_is_stored_with_its_time_reason_and_job(tmp_path: Path) -> None:
    """R-LG-03, R-LG-02: the history has the time, both statuses, the reason and the job ID."""
    engine = new_database(tmp_path)
    upgrade_to(engine, "0006")

    columns = {column["name"] for column in inspect(engine).get_columns("video_events")}
    job_columns = {column["name"] for column in inspect(engine).get_columns("jobs")}

    assert {"video_id", "at", "from_status", "to_status", "reason", "job_id"} <= columns
    assert {"id", "video_id", "kind", "state", "priority", "quality", "stage"} <= job_columns


def test_removing_a_channel_removes_the_jobs_and_history_of_its_videos(tmp_path: Path) -> None:
    """R-CH-32: the catalogue of a removed channel goes, with its jobs and its history."""
    engine = new_database(tmp_path)
    upgrade_to(engine, "0006")
    with engine.begin() as connection:
        for statement in (CHANNEL, VIDEO, JOB, EVENT):
            connection.execute(text(statement))

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM channels WHERE id = 'UCa'"))

    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM jobs")).scalar() == 0
        assert connection.execute(text("SELECT count(*) FROM video_events")).scalar() == 0


def test_a_job_of_a_video_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    """R-QA-07: the foreign keys hold, so no job can point at nothing."""
    engine = new_database(tmp_path)
    upgrade_to(engine, "0006")

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text(JOB))
