"""Checks that the migrations and the table classes describe the same schema."""

from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from tests.migrations.helpers import new_database, upgrade_to
from ytmirror.adapters.db.tables import Base


def test_a_fully_migrated_database_matches_the_table_classes(tmp_path: Path) -> None:
    """R-QA-04: a table change without its migration (or the reverse) fails this test."""
    engine = new_database(tmp_path)
    upgrade_to(engine, "head")

    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)

    assert differences == []
