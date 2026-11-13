"""Opens the app window with pywebview (docs/ARCHITECTURE.md section 7.8).

Implements R-PL-02 and R-PL-03. Closing the window ends the app
(docs/DECISIONS.md D-020). This module must be called on the main thread,
which macOS requires for windows.

Tests: backend/tests/unit/app/test_window.py
"""

import importlib
from typing import Protocol, cast

WINDOW_TITLE = "yt-mirror"
DEFAULT_SIZE = (1280, 800)
MINIMUM_SIZE = (1100, 700)


class WebviewModule(Protocol):
    """The part of the pywebview module that yt-mirror uses."""

    settings: dict[str, object]

    def create_window(
        self, title: str, url: str, *, width: int, height: int, min_size: tuple[int, int]
    ) -> object:
        """Create a window that shows a URL."""
        ...

    def start(self, *, debug: bool) -> None:
        """Show the windows and block until the last one is closed."""
        ...


def open_window(url: str, *, debug: bool, webview: WebviewModule | None = None) -> None:
    """Open the app window and return when the user has closed it.

    Args:
        url: The address to show.
        debug: True makes the WebKit developer tools available in the window.
        webview: A stand-in for the pywebview module. For tests.
    """
    module = webview if webview is not None else _load_webview()
    # The developer tools stay closed until asked for: "Inspect Element" in the context menu.
    module.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False
    module.create_window(
        WINDOW_TITLE,
        url,
        width=DEFAULT_SIZE[0],
        height=DEFAULT_SIZE[1],
        min_size=MINIMUM_SIZE,
    )
    module.start(debug=debug)


def _load_webview() -> WebviewModule:
    """Import pywebview late, so that tests and ``--doctor`` do not need a display."""
    return cast(WebviewModule, importlib.import_module("webview"))
