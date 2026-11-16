"""Runs the database migrations with Alembic: implements the DatabaseSchema port.

Migrations are forward only and are run by the app at start, never with the
``alembic`` command (docs/RELEASE-AND-UPDATE.md section 7). This module must
not decide when to migrate. That is the job of ``services/schema.py``.

Tests: backend/tests/integration/test_database_schema_contract.py
"""

import datetime
import hashlib
import re
import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text
from sqlalchemy.exc import DatabaseError

import ytmirror.migrations
from ytmirror.adapters.db.engine import for_reading

BACKUP_NAME = re.compile(r"^yt-mirror-\d{4}-\d{2}-\d{2}-\d{6}-schema-[0-9A-Za-z_]+(-\d+)?\.db$")
"""The name of a backup made before migrations: only such files are ever deleted."""


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
        with for_reading(self._engine).connect() as connection:
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
            with for_reading(self._engine).connect() as connection:
                result = connection.execute(text("PRAGMA integrity_check")).scalar()
        except DatabaseError:
            # A badly damaged file cannot even be opened.
            return False
        return result == "ok"

    def back_up(self, folder: Path, moment: datetime.datetime, keep: int) -> Path:
        """Copy the database with SQLite's backup API, and keep the newest ``keep`` copies.

        When the newest copy of the same schema version has the same content,
        no new copy is kept: that one is returned.

        Args:
            folder: The folder of the backups. It is created when missing.
            moment: When the copy is made, for its name.
            keep: How many copies to keep.

        Returns:
            The copy.
        """
        folder.mkdir(parents=True, exist_ok=True)
        stem = f"yt-mirror-{moment:%Y-%m-%d-%H%M%S}-schema-{self.current_version() or 'none'}"
        target = folder / f"{stem}.db"
        number = 2
        while target.exists():
            target = folder / f"{stem}-{number}.db"
            number += 1
        _copy(self._database_file, target)
        same = _newest_of_version(folder, stem.rsplit("-schema-", 1)[1], target)
        if same is not None and _checksum(same) == _checksum(target):
            # Nothing changed since that copy: a failed start that is tried again
            # must not push the older, different copies out (R-QA-07).
            target.unlink()
            return same
        kept = sorted(
            (path for path in folder.iterdir() if BACKUP_NAME.fullmatch(path.name)),
            key=lambda path: path.stat().st_mtime_ns,
        )
        for old in kept[: max(0, len(kept) - keep)]:
            old.unlink()
        return target

    def restore(self, backup: Path) -> None:
        """Put a backup in the place of the database, page by page with SQLite's backup API.

        Args:
            backup: The copy.
        """
        self._engine.dispose()
        _copy(backup, self._database_file)


def _newest_of_version(folder: Path, version: str, besides: Path) -> Path | None:
    """Return the newest backup of a schema version in the folder, other than ``besides``."""
    found = [
        path
        for path in folder.iterdir()
        if path != besides
        and BACKUP_NAME.fullmatch(path.name)
        and path.name.split("-schema-", 1)[1].split(".")[0].split("-")[0] == version
    ]
    return max(found, key=lambda path: path.stat().st_mtime_ns, default=None)


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _copy(source: Path, target: Path) -> None:
    """Copy one SQLite database onto another with the backup API of SQLite."""
    with sqlite3.connect(source) as reading, sqlite3.connect(target) as writing:
        reading.backup(writing)
    reading.close()
    writing.close()


def alembic_config() -> Config:
    """Return an Alembic configuration that points at the bundled migrations.

    The migration tests use it to stop at a chosen revision.
    """
    config = Config()
    config.set_main_option("script_location", str(Path(ytmirror.migrations.__file__).parent))
    return config
