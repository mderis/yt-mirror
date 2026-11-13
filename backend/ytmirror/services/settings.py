"""Reads the general settings.

Changing settings through the UI arrives in milestone M7. This module must
not know how settings are stored.

Tests: backend/tests/unit/services/test_settings.py
"""

from ytmirror.core.models import Settings
from ytmirror.ports.settings_repository import SettingsRepository


class SettingsService:
    """Gives the rest of the app the current general settings."""

    def __init__(self, repository: SettingsRepository) -> None:
        """Create the service.

        Args:
            repository: Where the settings are stored.
        """
        self._repository = repository

    def current(self) -> Settings:
        """Return the current general settings."""
        return self._repository.load()
