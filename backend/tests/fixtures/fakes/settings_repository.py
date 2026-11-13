"""Settings kept in memory. Fake of the SettingsRepository port."""

from ytmirror.core.models import Settings


class InMemorySettingsRepository:
    """Remembers the last saved settings."""

    def __init__(self) -> None:
        """Create a repository in which nothing was saved yet."""
        self._saved: Settings | None = None

    def load(self) -> Settings:
        """Return the saved settings, or the defaults."""
        return self._saved if self._saved is not None else Settings()

    def save(self, settings: Settings) -> None:
        """Remember the settings."""
        self._saved = settings
