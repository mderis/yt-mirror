"""Tests of migration 0005, which adds the time of a failed check to the channels."""

from pathlib import Path

from sqlalchemy import inspect, text

from tests.migrations.helpers import new_database, upgrade_to

CHANNEL = (
    "INSERT INTO channels (id, url, title, folder, folder_is_custom, auto_mirror, paused,"
    " last_check_error, position, created_at, updated_at)"
    " VALUES ('UCa', 'u', 'A channel', 'A channel', 0, 0, 0, 'NETWORK_UNREACHABLE', 0, 1, 1)"
)


def test_the_upgrade_keeps_the_channels_and_gives_them_no_time(tmp_path: Path) -> None:
    """R-QA-04: a database of the version before keeps its channels, with their error codes."""
    engine = new_database(tmp_path)
    upgrade_to(engine, "0004")
    with engine.begin() as connection:
        connection.execute(text(CHANNEL))

    upgrade_to(engine, "0005")

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, last_check_error, last_check_error_at FROM channels")
        ).all()
    assert [tuple(row) for row in rows] == [("UCa", "NETWORK_UNREACHABLE", None)]


def test_a_channel_stores_when_its_last_check_failed(tmp_path: Path) -> None:
    """R-QA-04, R-CH-25: the time of a failed check has a column of its own, which may be empty."""
    engine = new_database(tmp_path)

    upgrade_to(engine, "0005")

    columns = {column["name"]: column for column in inspect(engine).get_columns("channels")}
    assert columns["last_check_error_at"]["nullable"] is True
    assert str(columns["last_check_error_at"]["type"]) == "INTEGER"
