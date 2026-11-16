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
            AppError: ``DB_UPGRADE_FAILED`` when the update failed and the database
                file is as it was before: ``details["backup"]`` names the copy made
                before (empty when there was none or none could be made).
                ``DB_UNREADABLE`` when the database file cannot be read, or the
                copy could not be put back: the file itself may be damaged.
        """
        try:
            current = self._schema.current_version()
        except Exception as error:
            _log.error(
                "db.unreadable",
                msg="The database file cannot be read. The app does not start",
                error_code=ErrorCode.DB_UNREADABLE.value,
                exc_info=True,
            )
            raise AppError(ErrorCode.DB_UNREADABLE, {"backup": ""}) from error
        latest = self._schema.latest_version()
        if current == latest:
            return latest
        backup = None
        if current is not None:
            try:
                backup = self._schema.back_up(self._backups, self._clock.now(), KEEP_BACKUPS)
            except Exception as error:
                self._log_failure(current, latest, None, restored=False, step="backup")
                raise self._failure(ErrorCode.DB_UPGRADE_FAILED, current, latest, None) from error
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
            try:
                restored = self._keep_the_old_database(current, backup)
            except Exception:  # noqa: BLE001  (the restore itself failed: the file may be damaged)
                self._log_failure(current, latest, backup, restored=False, step="restore")
                raise self._failure(ErrorCode.DB_UNREADABLE, current, latest, backup) from error
            self._log_failure(current, latest, backup, restored=restored, step="migration")
            raise self._failure(ErrorCode.DB_UPGRADE_FAILED, current, latest, backup) from error
        _log.info(
            "db.migration.finished",
            msg="Database migration finished",
            from_version=current,
            to_version=latest,
            duration_ms=round((self._clock.monotonic() - started) * 1000),
        )
        return latest

    def _log_failure(
        self,
        current: str | None,
        latest: str,
        backup: Path | None,
        *,
        restored: bool,
        step: str,
    ) -> None:
        _log.error(
            "db.migration.failed",
            msg="The database could not be updated. The app does not start",
            error_code=ErrorCode.DB_UPGRADE_FAILED.value,
            from_version=current,
            to_version=latest,
            backup=str(backup) if backup else None,
            restored=restored,
            step=step,
            exc_info=True,
        )

    @staticmethod
    def _failure(
        code: ErrorCode, current: str | None, latest: str, backup: Path | None
    ) -> AppError:
        return AppError(
            code,
            {
                "backup": str(backup) if backup else "",
                "from_version": current or "",
                "to_version": latest,
            },
        )

    def _keep_the_old_database(self, version: str | None, backup: Path | None) -> bool:
        """Make sure the database is the one from before. Returns whether the copy was put back."""
        if backup is None:
            return False
        try:
            unchanged = self._schema.current_version() == version and self._schema.is_intact()
        except Exception:  # noqa: BLE001  (a file that cannot be read is not the one from before)
            unchanged = False
        if unchanged:
            return False
        self._schema.restore(backup)
        return True
