"""Runs the database migrations with Alembic: implements the DatabaseSchema port.

Migrations are forward only and are run by the app at start, never with the
``alembic`` command (docs/RELEASE-AND-UPDATE.md section 7). This module must
not decide when to migrate. That is the job of ``services/schema.py``.

Tests: backend/tests/integration/test_database_schema_contract.py
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text
from sqlalchemy.exc import DatabaseError

import ytmirror.migrations


class AlembicSchema:
    """Knows the schema version of the database and can bring it up to date."""

    def __init__(self, engine: Engine, database_file: Path) -> None:
        """Create the migrator.

        Args:
            engine: The database engine.
            database_file: The SQLite file behind the engine.
        """
        self._engine = engine
        self._database_file = database_file

    def exists(self) -> bool:
        """Return whether the database file has been created."""
        return self._database_file.is_file()

    def current_version(self) -> str | None:
        """Return the schema version of the database, or None before the first migration."""
        if not self.exists():
            return None
        with self._engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()

    def latest_version(self) -> str:
        """Return the schema version this copy of the app expects."""
        head = ScriptDirectory.from_config(alembic_config()).get_current_head()
        if head is None:
            raise RuntimeError("No migration found in ytmirror.migrations.versions")
        return head

    def upgrade(self) -> None:
        """Run every pending migration. Creates the database when it does not exist."""
        config = alembic_config()
        with self._engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")

    def is_intact(self) -> bool:
        """Return whether the database passes SQLite's integrity check."""
        if not self.exists():
            return True
        try:
            with self._engine.connect() as connection:
                result = connection.execute(text("PRAGMA integrity_check")).scalar()
        except DatabaseError:
            # A badly damaged file cannot even be opened.
            return False
        return result == "ok"


def alembic_config() -> Config:
    """Return an Alembic configuration that points at the bundled migrations.

    The migration tests use it to stop at a chosen revision.
    """
    config = Config()
    config.set_main_option("script_location", str(Path(ytmirror.migrations.__file__).parent))
    return config
