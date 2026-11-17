"""Tests of migration 0009, which keeps the state of the exact-date fetch and of check retries."""

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
    " VALUES ('v1', 'UCa', 'A video', 0, 0, 'not_downloaded', 0, 0, 0, 0, 1, 1, 1, 0, 1, 1)"
)


def test_a_channel_starts_with_no_retry_of_a_failed_check(tmp_path: Path) -> None:
    """R-CH-25: a channel stored before the upgrade has had no automatic retry yet."""
    engine = new_database(tmp_path)
    upgrade_to(engine, "0008")
    with engine.begin() as connection:
        connection.execute(text(CHANNEL))

    upgrade_to(engine, "0009")

    with engine.connect() as connection:
        assert connection.execute(text("SELECT check_retries FROM channels")).scalar() == 0


def test_the_fetch_state_of_a_video_goes_with_its_video(tmp_path: Path) -> None:
    """R-DT-06, R-QA-04: the upgrade adds the table; removing the channel removes its rows."""
    engine = new_database(tmp_path)
    upgrade_to(engine, "0008")
    with engine.begin() as connection:
        connection.execute(text(CHANNEL))
        connection.execute(text(VIDEO))

    upgrade_to(engine, "0009")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO date_fetch_queue (video_id, attempts, created_at, updated_at)"
                " VALUES ('v1', 1, 1, 1)"
            )
        )
        priority = connection.execute(text("SELECT priority FROM date_fetch_queue")).scalar()
        connection.execute(text("DELETE FROM channels"))

    assert "date_fetch_queue" in table_names(engine)
    assert priority == 0
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM date_fetch_queue")).scalar() == 0
