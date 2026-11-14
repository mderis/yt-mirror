"""A real, migrated database in a temp folder, for tests that store something."""

from pathlib import Path

from sqlalchemy import Engine

from ytmirror.adapters.db.engine import create_db_engine
from ytmirror.adapters.db.schema import AlembicSchema


def migrated_engine(folder: Path) -> Engine:
    """Return an engine for a new database that has the current schema.

    Args:
        folder: A temp folder of the test.
    """
    database_file = folder / "yt-mirror.db"
    engine = create_db_engine(database_file)
    AlembicSchema(engine, database_file).upgrade()
    return engine
