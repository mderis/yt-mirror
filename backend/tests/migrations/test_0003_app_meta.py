"""Tests of migration 0003, which creates the app_meta table."""

from pathlib import Path

from sqlalchemy import inspect, text

from tests.migrations.helpers import new_database, table_names, upgrade_to


def test_the_upgrade_creates_the_app_meta_table_and_keeps_the_settings(tmp_path: Path) -> None:
    """R-QA-04, R-IN-03: the app gets a place to remember that its setup completed."""
    engine = new_database(tmp_path)
    upgrade_to(engine, "0002")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO settings (key, value, created_at, updated_at)"
                " VALUES ('log_detail', '\"verbose\"', 1, 1)"
            )
        )

    upgrade_to(engine, "0003")

    assert table_names(engine) == {"alembic_version", "settings", "app_meta"}
    columns = {column["name"]: column for column in inspect(engine).get_columns("app_meta")}
    assert list(columns) == ["key", "value", "created_at", "updated_at"]
    assert [str(column["type"]) for column in columns.values()] == [
        "TEXT",
        "TEXT",
        "INTEGER",
        "INTEGER",
    ]
    assert not any(columns[name]["nullable"] for name in ("value", "created_at", "updated_at"))
    assert inspect(engine).get_pk_constraint("app_meta")["constrained_columns"] == ["key"]
    with engine.connect() as connection:
        kept = connection.execute(text("SELECT value FROM settings")).scalars().all()
    assert kept == ['"verbose"']
