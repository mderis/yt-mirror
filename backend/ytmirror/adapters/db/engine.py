"""Creates the SQLAlchemy engine for the one SQLite database file.

The database runs in WAL mode with one writer at a time and short
transactions (docs/DECISIONS.md D-005). This module must not define tables
or run queries of its own.

Tests: backend/tests/integration/db/test_engine.py
"""

import sqlite3
from pathlib import Path

from sqlalchemy import Engine, NullPool, create_engine, event

_BUSY_TIMEOUT_MS = 5000


def create_db_engine(database_file: Path) -> Engine:
    """Return an engine for the database file.

    Nothing is opened or created until the first connection is made.

    Args:
        database_file: The SQLite file. Its folder is created on first use.

    Returns:
        The engine. Every connection it opens uses WAL mode and foreign keys, and is
        closed as soon as it is released.
    """
    # No pool: a connection is opened for each unit of work and closed after it. Opening
    # SQLite is cheap, and no connection is left open when the app stops or crashes.
    engine = create_engine(f"sqlite:///{database_file}", poolclass=NullPool)

    def configure(dbapi_connection: sqlite3.Connection, _record: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
        cursor.close()

    def ensure_folder(_dialect: object, _record: object, _args: object, _params: object) -> None:
        database_file.parent.mkdir(parents=True, exist_ok=True)

    event.listen(engine, "do_connect", ensure_folder)
    event.listen(engine, "connect", configure)
    return engine
