"""Tests of migration 0007: the marker of a file being placed, and who created a folder."""

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
    " seen_in_first_listing, attempts, file_name, created_at, updated_at)"
    " VALUES ('v1', 'UCa', 'A video', 0, 0, 'synced', 0, 0, 0, 0, 1, 1, 1, 0, 'A video.mkv', 1, 1)"
)


def test_existing_rows_place_nothing_and_their_folders_count_as_the_users(tmp_path: Path) -> None:
    """R-QA-04, R-CH-32, R-QA-06: no marker on old videos; no old folder may go to the Trash."""
    engine = new_database(tmp_path)
    upgrade_to(engine, "0006")
    with engine.begin() as connection:
        connection.execute(text(CHANNEL))
        connection.execute(text(VIDEO))

    upgrade_to(engine, "0007")

    with engine.connect() as connection:
        assert connection.execute(text("SELECT folder_created FROM channels")).all() == [(0,)]
        assert connection.execute(text("SELECT file_name, placing_file FROM videos")).all() == [
            ("A video.mkv", None)
        ]
