"""The SettingsRepository port: where the general settings are stored.

Tests: backend/tests/integration/test_settings_repository_contract.py
"""

from typing import Protocol

from ytmirror.core.models import Settings


class SettingsRepository(Protocol):
    """Stores and loads the general settings (R-SE-03)."""

    def load(self) -> Settings:
        """Return the stored settings. A setting that was never stored has its default."""
        ...

    def save(self, settings: Settings) -> None:
        """Store every setting.

        Args:
            settings: The settings to store.
        """
        ...
