"""Brings the database schema up to date when the app starts.

The updater (milestone M9) will add backup and rollback around the same
step. This module must not know Alembic or SQLite: it works through the
DatabaseSchema port.

Tests: backend/tests/unit/services/test_schema.py
"""

import structlog
from structlog.typing import FilteringBoundLogger

from ytmirror.ports.clock import Clock
from ytmirror.ports.database_schema import DatabaseSchema

_log: FilteringBoundLogger = structlog.get_logger(__name__)


class SchemaService:
    """Runs pending database migrations."""

    def __init__(self, schema: DatabaseSchema, clock: Clock) -> None:
        """Create the service.

        Args:
            schema: The database schema port.
            clock: Used to measure how long the migration took.
        """
        self._schema = schema
        self._clock = clock

    def bring_up_to_date(self) -> str:
        """Run pending migrations and return the schema version afterwards.

        Does nothing when the database is already at the latest version.

        Returns:
            The schema version of the database after the call.
        """
        current = self._schema.current_version()
        latest = self._schema.latest_version()
        if current == latest:
            return latest
        started = self._clock.monotonic()
        _log.info(
            "db.migration.started",
            msg="Database migration started",
            from_version=current,
            to_version=latest,
        )
        self._schema.upgrade()
        _log.info(
            "db.migration.finished",
            msg="Database migration finished",
            from_version=current,
            to_version=latest,
            duration_ms=round((self._clock.monotonic() - started) * 1000),
        )
        return latest
