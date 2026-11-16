"""The DatabaseSchema port: the version of the database schema and its upgrades.

Tests: backend/tests/integration/test_database_schema_contract.py
"""

import datetime
from pathlib import Path
from typing import Protocol


class DatabaseSchema(Protocol):
    """Knows the schema version of the database and can bring it up to date."""

    def exists(self) -> bool:
        """Return whether the database has been created."""
        ...

    def current_version(self) -> str | None:
        """Return the schema version of the database, or None before the first migration."""
        ...

    def latest_version(self) -> str:
        """Return the schema version this copy of the app expects."""
        ...

    def upgrade(self) -> None:
        """Run every pending migration. Creates the database when it does not exist."""
        ...

    def is_intact(self) -> bool:
        """Return whether the database passes its integrity check."""
        ...

    def back_up(self, folder: Path, moment: datetime.datetime, keep: int) -> Path:
        """Copy the database into a folder, safely while it is in use (WAL).

        The copy is named with the moment and the schema version. Only the
        newest ``keep`` copies of this kind are kept in the folder; no other
        file there is touched.

        Args:
            folder: The folder of the backups. It is created when missing.
            moment: When the copy is made, for its name.
            keep: How many copies to keep.

        Returns:
            The copy.
        """
        ...

    def restore(self, backup: Path) -> None:
        """Put a copy made by ``back_up`` in the place of the database.

        Args:
            backup: The copy.
        """
        ...
