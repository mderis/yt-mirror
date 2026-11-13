"""The DatabaseSchema port: the version of the database schema and its upgrades.

Tests: backend/tests/integration/test_database_schema_contract.py
"""

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
