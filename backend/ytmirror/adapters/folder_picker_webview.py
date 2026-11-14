"""The FolderPicker port through the app window of pywebview.

Only public calls of pywebview are used (docs/ARCHITECTURE.md section 7.8):
the list of windows and the file dialog of a window. pywebview is imported
late, so a run without a window never loads it.

Tests: backend/tests/integration/test_folder_picker_contract.py
"""

import importlib
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

type LoadedWebview = Callable[[], Any | None]
"""Returns the pywebview module when this process has loaded it, otherwise None."""


def _loaded_webview() -> Any | None:
    """Return pywebview only when the app already uses it: a picker never loads a window library."""
    return importlib.import_module("webview") if "webview" in sys.modules else None


class WebviewFolderPicker:
    """Shows the folder dialog of the first app window."""

    def __init__(self, loaded_webview: LoadedWebview = _loaded_webview) -> None:
        """Create the picker.

        Args:
            loaded_webview: A stand-in for finding the loaded pywebview module. For tests.
        """
        self._loaded_webview = loaded_webview

    def available(self) -> bool:
        """Return whether the app has a window to show the dialog in."""
        return self._window() is not None

    def choose(self, start: Path | None) -> Path | None:
        """Show the dialog and wait for the user.

        Args:
            start: The folder the dialog opens in, or None.

        Returns:
            The chosen folder, or None when the user cancelled or there is no window.
        """
        window = self._window()
        webview = self._loaded_webview()
        if window is None or webview is None:
            return None
        chosen = window.create_file_dialog(
            webview.FileDialog.FOLDER, directory="" if start is None else str(start)
        )
        return _first_folder(chosen)

    def _window(self) -> Any | None:
        webview = self._loaded_webview()
        windows: Sequence[Any] = () if webview is None else webview.windows
        return windows[0] if windows else None


def _first_folder(chosen: object) -> Path | None:
    """Read what the dialog returned: a list with the folder, or nothing after Cancel."""
    if isinstance(chosen, str):
        return Path(chosen) if chosen else None
    if isinstance(chosen, (list, tuple)) and chosen and isinstance(chosen[0], str) and chosen[0]:
        return Path(chosen[0])
    return None
