"""A migration that fails leaves the database as it was (R-QA-04, R-QA-06).

Every pending migration runs in one transaction, and SQLite rolls back table
changes too. A copy of the migrations with one more that fails half way shows
it: the version, the tables and the rows are those from before.
"""

from pathlib import Path

import pytest
from sqlalchemy import inspect, text

from tests.migrations.helpers import add_a_failing_migration, new_database, upgrade_to
from tests.migrations.test_no_data_lost import contents, fill, revisions
from ytmirror.adapters.db.schema import AlembicSchema


def test_a_migration_that_fails_half_way_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-QA-04: the version, the tables and every row are as before the failed upgrade."""
    add_a_failing_migration(tmp_path, monkeypatch)
    engine = new_database(tmp_path)
    upgrade_to(engine, revisions()[-1])
    fill(engine)
    before = contents(engine)
    schema = AlembicSchema(engine, tmp_path / "yt-mirror.db")

    with pytest.raises(RuntimeError, match="half way"):
        schema.upgrade()

    assert schema.current_version() == revisions()[-1]
    assert "half_done" not in {column["name"] for column in inspect(engine).get_columns("channels")}
    assert contents(engine) == before
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
