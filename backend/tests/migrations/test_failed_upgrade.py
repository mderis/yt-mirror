"""A migration that fails leaves the database as it was (R-QA-04, R-QA-06).

Every pending migration runs in one transaction, and SQLite rolls back table
changes too. A copy of the migrations with one more that fails half way shows
it: the version, the tables and the rows are those from before.
"""

import shutil
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text

import ytmirror.migrations
from tests.migrations.helpers import new_database, upgrade_to
from tests.migrations.test_no_data_lost import contents, fill, revisions
from ytmirror.adapters.db.schema import AlembicSchema

FAILING = '''"""A migration that changes a table and then fails. For the test only."""

import sqlalchemy as sa
from alembic import op

revision = "9999"
down_revision = "{head}"


def upgrade() -> None:
    """Add a column, delete rows, then fail."""
    op.add_column("channels", sa.Column("half_done", sa.Text(), nullable=True))
    op.execute("DELETE FROM videos")
    raise RuntimeError("the migration failed half way")
'''


def test_a_migration_that_fails_half_way_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-QA-04: the version, the tables and every row are as before the failed upgrade."""
    copy = tmp_path / "migrations"
    shutil.copytree(
        Path(ytmirror.migrations.__file__).parent,
        copy,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (copy / "versions" / "9999_fails.py").write_text(FAILING.format(head=revisions()[-1]))
    config = Config()
    config.set_main_option("script_location", str(copy))
    monkeypatch.setattr("ytmirror.adapters.db.schema.alembic_config", lambda: config)
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
