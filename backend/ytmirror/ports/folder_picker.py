"""The FolderPicker port: the native dialog of macOS for choosing a folder.

Used when the user chooses the folder of a channel (R-CH-05). The dialog
belongs to the app window, so without a window (``--browser``, automated
tests) there is none, and the interface does not offer "Choose...".

Tests: backend/tests/integration/test_folder_picker_contract.py
"""

from pathlib import Path
from typing import Protocol


class FolderPicker(Protocol):
    """Lets the user choose a folder in the dialog of macOS."""

    def available(self) -> bool:
        """Return whether the dialog can be shown right now: whether the app has a window."""
        ...

    def choose(self, start: Path | None) -> Path | None:
        """Show the dialog and wait for the user.

        Args:
            start: The folder the dialog opens in, or None for the place macOS suggests.

        Returns:
            The chosen folder, or None when the user cancelled or there is no window.
        """
        ...
