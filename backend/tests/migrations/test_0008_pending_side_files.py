"""Tests of migration 0008, which keeps the side files still to be written."""

from pathlib import Path

from sqlalchemy import text

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
    " VALUES ('v1', 'UCa', 'A video', 0, 0, 'synced', 0, 0, 0, 0, 1, 1, 1, 0, 1, 1)"
)


def test_a_side_file_waits_with_its_content_and_goes_with_its_video(tmp_path: Path) -> None:
    """R-QA-04, R-MD-02: the upgrade adds the table; removing the channel removes what waits."""
    engine = new_database(tmp_path)
    upgrade_to(engine, "0007")
    with engine.begin() as connection:
        connection.execute(text(CHANNEL))
        connection.execute(text(VIDEO))

    upgrade_to(engine, "0008")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO pending_side_files (video_id, path, data, created_at, updated_at)"
                " VALUES ('v1', '.yt-mirror/v1.info.json', x'7b7d', 1, 1)"
            )
        )
        connection.execute(text("DELETE FROM channels"))

    assert "pending_side_files" in table_names(engine)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM pending_side_files")).scalar() == 0
