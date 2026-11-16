"""Helpers for the migration tests: run the real migrations up to a chosen revision."""

import shutil
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect

import ytmirror.migrations
from ytmirror.adapters.db.engine import create_db_engine
from ytmirror.adapters.db.schema import alembic_config


def new_database(folder: Path) -> Engine:
    """Return an engine for a database file that does not exist yet."""
    return create_db_engine(folder / "yt-mirror.db")


def upgrade_to(engine: Engine, revision: str) -> None:
    """Run the migrations up to and including a revision."""
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)


def table_names(engine: Engine) -> set[str]:
    """Return the names of all tables in the database."""
    return set(inspect(engine).get_table_names())


FAILING = '''"""A migration that changes a table and then fails. For tests only."""

import sqlalchemy as sa
from alembic import op

revision = "9999"
down_revision = "{head}"


def upgrade() -> None:
    op.add_column("channels", sa.Column("half_done", sa.Text(), nullable=True))
    op.execute("DELETE FROM videos")
    raise RuntimeError("the migration failed half way")
'''


def add_a_failing_migration(folder: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the app see a copy of its migrations with one more that fails half way.

    It adds a column, deletes every video, then raises.
    """
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    copy = folder / "migrations"
    shutil.copytree(
        Path(ytmirror.migrations.__file__).parent,
        copy,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (copy / "versions" / "9999_fails.py").write_text(FAILING.format(head=head))
    config = Config()
    config.set_main_option("script_location", str(copy))
    monkeypatch.setattr("ytmirror.adapters.db.schema.alembic_config", lambda: config)
