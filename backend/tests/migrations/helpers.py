"""Helpers for the migration tests: run the real migrations up to a chosen revision."""

from pathlib import Path

from alembic import command
from sqlalchemy import Engine, inspect

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
