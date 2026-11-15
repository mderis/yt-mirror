"""A database schema that exists only as a version number. Fake of the DatabaseSchema port."""

import datetime
from pathlib import Path


class FakeDatabaseSchema:
    """Tracks a schema version without a database."""

    def __init__(
        self, *, latest: str = "0002", current: str | None = None, intact: bool = True
    ) -> None:
        """Create the fake.

        Args:
            latest: The version the app expects.
            current: The version of the database. None means the database does not exist yet.
            intact: The answer of the integrity check.
        """
        self._latest = latest
        self._current = current
        self._exists = current is not None
        self._intact = intact
        self.upgrades = 0
        self.fail: Exception | None = None
        """An error the next upgrade raises, after it changed the version when ``half_done``."""
        self.half_done = False
        self.backups: list[tuple[Path, str | None]] = []
        self.restored: list[Path] = []
        self.unreadable = False
        """Whether reading the version fails, as on a file that is not a database."""
        self.backup_fails = False
        self.restore_fails = False

    def exists(self) -> bool:
        """Return whether the database has been created."""
        return self._exists

    def current_version(self) -> str | None:
        """Return the schema version of the database, or fail on a damaged file."""
        if self.unreadable:
            raise RuntimeError("file is not a database")
        return self._current

    def latest_version(self) -> str:
        """Return the schema version the app expects."""
        return self._latest

    def upgrade(self) -> None:
        """Move to the latest version and count the call, or fail as configured."""
        self.upgrades += 1
        if self.fail is not None:
            if self.half_done:
                self._current = "half"
            raise self.fail
        self._exists = True
        self._current = self._latest

    def back_up(self, folder: Path, moment: datetime.datetime, keep: int) -> Path:
        """Remember a copy of the version as it is, or fail as configured."""
        if self.backup_fails:
            raise OSError(28, "No space left on device")
        copy = folder / f"yt-mirror-{moment:%Y-%m-%d-%H%M%S}-schema-{self._current}.db"
        self.backups.append((copy, self._current))
        return copy

    def restore(self, backup: Path) -> None:
        """Go back to the version the copy was made at, or fail as configured."""
        if self.restore_fails:
            raise RuntimeError("file is not a database")
        self.restored.append(backup)
        self._current = next(version for copy, version in self.backups if copy == backup)

    def is_intact(self) -> bool:
        """Return the configured answer of the integrity check."""
        return self._intact
