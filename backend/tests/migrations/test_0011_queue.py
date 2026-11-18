"""Tests of migration 0011, which adds what the queue of M5 keeps."""

from pathlib import Path

from sqlalchemy import text

from tests.migrations.helpers import new_database, upgrade_to

CHANNEL = (
    "INSERT INTO channels (id, url, title, folder, folder_is_custom, auto_mirror, paused,"
    " position, created_at, updated_at)"
    " VALUES (:id, 'u', 'A channel', :id, 0, :auto, 0, 0, 1, 1)"
)
VIDEO = (
    "INSERT INTO videos (id, channel_id, title, published_exact, channel_position, status,"
    " excluded, exclude_exception, missing_checks, gone, first_seen_at, last_seen_at,"
    " seen_in_first_listing, attempts, created_at, updated_at)"
    " VALUES ('v1', 'UCa', 'A video', 1, 0, 'queued', 0, 0, 0, 0, 1, 1, 1, 0, 1, 1)"
)
JOB = (
    "INSERT INTO jobs (id, video_id, kind, state, priority, quality, created_at, updated_at)"
    " VALUES ('01JOB', 'v1', 'download', 'waiting', 1, 'best', 1, 1)"
)


def test_a_stored_job_counts_as_started_by_hand(tmp_path: Path) -> None:
    """R-DT-06, R-QU-05, R-QA-04: a job of an earlier version was started by hand."""
    engine = new_database(tmp_path)
    upgrade_to(engine, "0010")
    with engine.begin() as connection:
        connection.execute(text(CHANNEL), {"id": "UCa", "auto": 0})
        connection.execute(text(VIDEO))
        connection.execute(text(JOB))

    upgrade_to(engine, "0011")

    with engine.connect() as connection:
        job = connection.execute(text("SELECT by_hand, not_before, formats FROM jobs")).one()
        video = connection.execute(text("SELECT replacing FROM videos")).one()
    assert tuple(job) == (1, None, None)
    assert tuple(video) == (None,)


def test_a_channel_with_auto_mirror_on_is_asked_first(tmp_path: Path) -> None:
    """R-MI-02, D-095, R-QA-04: auto-mirror of an earlier version starts nothing before a question.

    A channel with auto-mirror off needs no answer.
    """
    engine = new_database(tmp_path)
    upgrade_to(engine, "0010")
    with engine.begin() as connection:
        connection.execute(text(CHANNEL), {"id": "UCa", "auto": 1})
        connection.execute(text(CHANNEL), {"id": "UCb", "auto": 0})

    upgrade_to(engine, "0011")

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, auto_mirror_asked, missing_left FROM channels ORDER BY id")
        ).all()
    assert [tuple(row) for row in rows] == [("UCa", 0, None), ("UCb", 1, None)]
