"""Tests of migration 0001, the empty baseline."""

from pathlib import Path

from sqlalchemy import text

from tests.migrations.helpers import new_database, table_names, upgrade_to


def test_the_baseline_gives_a_new_database_a_version_and_no_tables(tmp_path: Path) -> None:
    """R-QA-04: the first migration is empty and only records the schema version."""
    engine = new_database(tmp_path)

    upgrade_to(engine, "0001")

    assert table_names(engine) == {"alembic_version"}
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert version == "0001"
