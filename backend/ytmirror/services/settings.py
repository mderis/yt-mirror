"""Reads the general settings.

Changing settings through the UI arrives in milestone M7. This module must
not know how settings are stored.

Tests: backend/tests/unit/services/test_settings.py
"""

from pathlib import Path

from ytmirror.core.models import DEFAULT_LIBRARY_FOLDER, Settings
from ytmirror.ports.settings_repository import SettingsRepository


class SettingsService:
    """Gives the rest of the app the current general settings."""

    def __init__(self, repository: SettingsRepository, default_library: Path) -> None:
        """Create the service.

        Args:
            repository: Where the settings are stored.
            default_library: The folder that the default of the library setting,
                ``~/Movies/YouTube``, means on this Mac.
        """
        self._repository = repository
        self._default_library = default_library

    def current(self) -> Settings:
        """Return the current general settings."""
        return self._repository.load()

    def library_folder(self) -> Path:
        """Return the library folder as a real path (R-FI-01).

        Returns:
            The folder the user chose, or the default library of this Mac.
        """
        chosen = self.current().library_folder
        if chosen == DEFAULT_LIBRARY_FOLDER:
            return self._default_library
        return Path(chosen)
