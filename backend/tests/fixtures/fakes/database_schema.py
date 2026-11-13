"""A database schema that exists only as a version number. Fake of the DatabaseSchema port."""


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

    def exists(self) -> bool:
        """Return whether the database has been created."""
        return self._exists

    def current_version(self) -> str | None:
        """Return the schema version of the database."""
        return self._current

    def latest_version(self) -> str:
        """Return the schema version the app expects."""
        return self._latest

    def upgrade(self) -> None:
        """Move to the latest version and count the call."""
        self.upgrades += 1
        self._exists = True
        self._current = self._latest

    def is_intact(self) -> bool:
        """Return the configured answer of the integrity check."""
        return self._intact
