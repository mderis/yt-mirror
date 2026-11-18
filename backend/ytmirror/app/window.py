"""Opens the app window with pywebview (docs/ARCHITECTURE.md sections 7.8 and 7.10).

Implements R-PL-02 and R-PL-03, puts the app's own menu bar in place of the
window library's menus (R-NA-03, docs/DECISIONS.md D-049), and makes every
way of quitting run the app's shutdown work (R-PL-13, D-052). Every way of
quitting first reaches the decision whether the quit is held for a question
(R-NA-06, R-QU-12), through the ``closing`` event of the window; Ctrl+C and
a termination signal are let through. Closing the window ends the app (D-020).
This module must be called on the main thread, which macOS requires for windows.
Only public calls of pywebview are used.

Tests: backend/tests/unit/app/test_window.py and, with a real window,
backend/tests/integration/app/test_window_app.py
"""

import importlib
from collections.abc import Callable, Sequence
from typing import Protocol, Self, cast

from ytmirror.app.signals import send_stop_signals_to
from ytmirror.core.models import ItemState, Menu, MenuCommand
from ytmirror.ports.native_app import NativeApp

DEFAULT_SIZE = (1280, 800)
MINIMUM_SIZE = (1100, 700)


class WebviewEvent(Protocol):
    """One event of a pywebview window. Handlers are added with ``+=``."""

    def __iadd__(self, handler: Callable[[], None]) -> Self:
        """Add a handler."""
        ...


class WebviewClosingEvent(Protocol):
    """The ``closing`` event of a pywebview window. A handler returning False holds the close."""

    def __iadd__(self, handler: Callable[[], bool]) -> Self:
        """Add a handler."""
        ...


class WebviewEvents(Protocol):
    """The events of a pywebview window that yt-mirror uses."""

    @property
    def shown(self) -> WebviewEvent:
        """Set once the window is on the screen."""
        ...

    @property
    def closing(self) -> WebviewClosingEvent:
        """Asked before the window closes and before the app quits, on the main thread."""
        ...


class WebviewWindow(Protocol):
    """The part of a pywebview window that yt-mirror uses."""

    @property
    def events(self) -> WebviewEvents:
        """The events of this window."""
        ...


class WebviewModule(Protocol):
    """The part of the pywebview module that yt-mirror uses."""

    settings: dict[str, object]

    def create_window(
        self, title: str, url: str, *, width: int, height: int, min_size: tuple[int, int]
    ) -> WebviewWindow:
        """Create a window that shows a URL."""
        ...

    def start(self, *, debug: bool) -> None:
        """Show the windows and block until the last one is closed."""
        ...


def open_window(
    url: str,
    *,
    title: str,
    debug: bool,
    native: NativeApp,
    menus: Sequence[Menu],
    before_quit: Callable[[], None],
    when_shown: Callable[[], None] | None = None,
    item_state: Callable[[MenuCommand], ItemState] | None = None,
    on_command: Callable[[MenuCommand], None] | None = None,
    may_quit: Callable[[], bool] | None = None,
    signal_quit: Callable[[], None] | None = None,
    webview: WebviewModule | None = None,
    route_stop_signals: Callable[[Callable[[], None]], object] = send_stop_signals_to,
) -> None:
    """Open the app window and return when the user has closed it.

    When the user quits instead (Cmd+Q, the Dock, a logout, Ctrl+C), macOS ends
    the process and this function never returns. ``before_quit`` has run by then.

    Args:
        url: The address to show.
        title: The title of the window.
        debug: True makes the WebKit developer tools available in the window.
        native: The app as macOS sees it.
        menus: The menu bar of the app.
        before_quit: The app's shutdown work. It runs before macOS ends the process.
        when_shown: Runs on the main thread once the window and the menu bar are up.
        item_state: Whether a command item of the menu bar is enabled, its title and mark.
        on_command: Runs the command of a chosen menu item.
        may_quit: Decides whether a close or a quit goes on (True) or is held (False).
        signal_quit: Runs before Ctrl+C or a termination signal asks to quit, so that
            the quit is not held: there is nobody to ask.
        webview: A stand-in for the pywebview module. For tests.
        route_stop_signals: A stand-in for the signal handling of this process. For tests.
    """
    module = webview if webview is not None else _load_webview()
    # The developer tools stay closed until asked for: "Inspect Element" in the context menu.
    module.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False
    window = module.create_window(
        title,
        url,
        width=DEFAULT_SIZE[0],
        height=DEFAULT_SIZE[1],
        min_size=MINIMUM_SIZE,
    )
    native.on_will_terminate(before_quit)

    def quit_after_signal() -> None:
        if signal_quit is not None:
            signal_quit()
        native.request_quit()

    def set_up_on_the_main_thread() -> None:
        # pywebview sets menus of its own once, just before its loop starts. This runs
        # in that loop, so it comes after them and replaces them (D-049).
        native.show_menu_bar(menus, item_state, on_command)
        # From here on Ctrl+C and a termination signal quit like "Quit" in the menu does.
        route_stop_signals(lambda: native.run_on_main_thread(quit_after_signal))
        if when_shown is not None:
            when_shown()

    def on_shown() -> None:
        native.run_on_main_thread(set_up_on_the_main_thread)

    def on_closing() -> bool:
        # The window library asks this for a close of the window and for every quit
        # request of macOS. It holds only on exactly False; an error lets it through.
        return may_quit() if may_quit is not None else True

    shown = window.events.shown
    shown += on_shown
    closing = window.events.closing
    closing += on_closing
    module.start(debug=debug)


def _load_webview() -> WebviewModule:
    """Import pywebview late, so that tests and ``--doctor`` do not need a display."""
    return cast(WebviewModule, importlib.import_module("webview"))
