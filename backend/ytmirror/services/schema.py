"""Brings the database schema up to date when the app starts (R-QA-07).

Before a pending migration runs on an existing database, a copy of it is
made in ``data/backups/`` and the newest five are kept. A migration that
fails changes nothing (D-081); should the database not be as it was all the
same, the copy is put back. Either way the app does not start, and says
which copy it made. The updater of milestone M9 builds its rollback on this.
This module must not know Alembic or SQLite: it works through the
DatabaseSchema port.

Tests: backend/tests/unit/services/test_schema.py
"""

from pathlib import Path

import structlog
from structlog.typing import FilteringBoundLogger

from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.ports.clock import Clock
from ytmirror.ports.database_schema import DatabaseSchema

_log: FilteringBoundLogger = structlog.get_logger(__name__)

KEEP_BACKUPS = 5
"""How many backups made before migrations are kept."""


class SchemaService:
    """Runs pending database migrations, after a backup."""

    def __init__(self, schema: DatabaseSchema, clock: Clock, backups: Path) -> None:
        """Create the service.

        Args:
            schema: The database schema port.
            clock: Used to name the backup and to measure how long the migration took.
            backups: The folder of the backups, ``data/backups``.
        """
        self._schema = schema
        self._clock = clock
        self._backups = backups

    def bring_up_to_date(self) -> str:
        """Run pending migrations and return the schema version afterwards.

        Does nothing when the database is already at the latest version.

        Returns:
            The schema version of the database after the call.

        Raises:
            AppError: ``DB_UPGRADE_FAILED`` when a migration failed. The database
                is as it was before, and ``details["backup"]`` names the copy
                made before (empty for a database that did not exist yet).
        """
        current = self._schema.current_version()
        latest = self._schema.latest_version()
        if current == latest:
            return latest
        backup = None
        if current is not None:
            backup = self._schema.back_up(self._backups, self._clock.now(), KEEP_BACKUPS)
            _log.info(
                "db.backup",
                msg="Database copied before its update",
                file=str(backup),
                version=current,
            )
        started = self._clock.monotonic()
        _log.info(
            "db.migration.started",
            msg="Database migration started",
            from_version=current,
            to_version=latest,
        )
        try:
            self._schema.upgrade()
        except Exception as error:
            restored = self._keep_the_old_database(current, backup)
            _log.error(
                "db.migration.failed",
                msg="The database could not be updated. It is as it was; the app does not start",
                error_code=ErrorCode.DB_UPGRADE_FAILED.value,
                from_version=current,
                to_version=latest,
                backup=str(backup) if backup else None,
                restored=restored,
                exc_info=True,
            )
            raise AppError(
                ErrorCode.DB_UPGRADE_FAILED,
                {
                    "backup": str(backup) if backup else "",
                    "from_version": current or "",
                    "to_version": latest,
                },
            ) from error
        _log.info(
            "db.migration.finished",
            msg="Database migration finished",
            from_version=current,
            to_version=latest,
            duration_ms=round((self._clock.monotonic() - started) * 1000),
        )
        return latest

    def _keep_the_old_database(self, version: str | None, backup: Path | None) -> bool:
        """Make sure the database is the one from before. Returns whether the copy was put back."""
        if backup is None:
            return False
        if self._schema.current_version() == version and self._schema.is_intact():
            return False
        self._schema.restore(backup)
        return True
