"""Reads the general settings, and changes the ones the interface already offers.

The settings screen arrives in milestone M7. Before it, the downloads panel
changes two settings of the queue: "Pause all downloads" and the speed limit
(R-QU-02, R-QU-03). This module must not know how settings are stored.

Tests: backend/tests/unit/services/test_settings.py
"""

from dataclasses import replace
from pathlib import Path
from typing import Any

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

    def change(self, **values: Any) -> Settings:
        """Store new values of some settings and keep the others (R-SE-01: saved at once).

        Args:
            values: The new values, by the name of the setting.

        Returns:
            The settings as they are now.
        """
        changed = replace(self.current(), **values)
        self._repository.save(changed)
        return changed

    def library_folder(self) -> Path:
        """Return the library folder as a real path (R-FI-01).

        Returns:
            The folder the user chose, or the default library of this Mac.
        """
        chosen = self.current().library_folder
        if chosen == DEFAULT_LIBRARY_FOLDER:
            return self._default_library
        return Path(chosen)
