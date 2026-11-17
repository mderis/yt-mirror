"""Tests of migration 0010, which adds the marker of a rename."""

from pathlib import Path

from sqlalchemy import text

from tests.migrations.helpers import new_database, upgrade_to

CHANNEL = (
    "INSERT INTO channels (id, url, title, folder, folder_is_custom, auto_mirror, paused,"
    " position, created_at, updated_at)"
    " VALUES ('UCa', 'u', 'A channel', 'A channel', 0, 0, 0, 0, 1, 1)"
)
VIDEO = (
    "INSERT INTO videos (id, channel_id, title, published_exact, channel_position, status,"
    " excluded, exclude_exception, missing_checks, gone, first_seen_at, last_seen_at,"
    " seen_in_first_listing, attempts, created_at, updated_at, file_name)"
    " VALUES ('v1', 'UCa', 'A video', 1, 0, 'synced', 0, 0, 0, 0, 1, 1, 1, 0, 1, 1, 'A video.mkv')"
)


def test_a_stored_video_has_no_rename_marked(tmp_path: Path) -> None:
    """R-FN-06, R-QA-04: a video stored before the upgrade keeps its file and has no marker."""
    engine = new_database(tmp_path)
    upgrade_to(engine, "0009")
    with engine.begin() as connection:
        connection.execute(text(CHANNEL))
        connection.execute(text(VIDEO))

    upgrade_to(engine, "0010")

    with engine.connect() as connection:
        row = connection.execute(text("SELECT file_name, rename_from, rename_to FROM videos")).one()
    assert tuple(row) == ("A video.mkv", None, None)
