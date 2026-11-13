"""Tests of migration 0002, which creates the settings table."""

from pathlib import Path

from sqlalchemy import inspect, text

from tests.migrations.helpers import new_database, table_names, upgrade_to


def test_the_upgrade_from_the_baseline_creates_the_settings_table(tmp_path: Path) -> None:
    """R-QA-04, R-SE-03: settings get their table through a migration from version 0001."""
    engine = new_database(tmp_path)
    upgrade_to(engine, "0001")

    upgrade_to(engine, "0002")

    assert table_names(engine) == {"alembic_version", "settings"}
    columns = {column["name"]: column for column in inspect(engine).get_columns("settings")}
    assert list(columns) == ["key", "value", "created_at", "updated_at"]
    assert str(columns["key"]["type"]) == "TEXT"
    assert str(columns["value"]["type"]) == "TEXT"
    assert str(columns["created_at"]["type"]) == "INTEGER"
    assert str(columns["updated_at"]["type"]) == "INTEGER"
    assert not any(columns[name]["nullable"] for name in ("value", "created_at", "updated_at"))
    assert inspect(engine).get_pk_constraint("settings")["constrained_columns"] == ["key"]


def test_a_setting_key_can_be_stored_only_once(tmp_path: Path) -> None:
    """R-SE-03: the key is the primary key, so a setting has exactly one value."""
    engine = new_database(tmp_path)
    upgrade_to(engine, "0002")
    insert = text(
        "INSERT OR IGNORE INTO settings (key, value, created_at, updated_at)"
        " VALUES ('theme', :value, 1, 1)"
    )

    with engine.begin() as connection:
        connection.execute(insert, {"value": '"dark"'})
        connection.execute(insert, {"value": '"light"'})

    with engine.connect() as connection:
        rows = connection.execute(text("SELECT value FROM settings")).scalars().all()
    assert rows == ['"dark"']
