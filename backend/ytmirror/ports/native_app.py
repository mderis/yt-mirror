"""The NativeApp port: the parts of a Mac app that macOS itself draws and decides.

The menu bar (R-NA-03), the name under which macOS knows the running app
(R-NA-01), and the end of the app (R-PL-13). The window itself is not part of
this port: it belongs to ``app/window.py``.

Tests: backend/tests/integration/test_native_app_contract.py
"""

from collections.abc import Callable, Sequence
from typing import Protocol

from ytmirror.core.models import AppIdentity, Menu, ShownMenu


class NativeApp(Protocol):
    """Talks to macOS about the running app."""

    def identity(self) -> AppIdentity:
        """Return the name and the bundle identifier under which macOS knows this process."""
        ...

    def show_menu_bar(self, menus: Sequence[Menu]) -> None:
        """Replace the whole menu bar of the app. Call it on the main thread.

        Args:
            menus: The menus, from left to right. The first one is the app menu.
        """
        ...

    def shown_menu_bar(self) -> tuple[ShownMenu, ...]:
        """Return the menu bar as it really is right now. Call it on the main thread.

        Returns:
            Every menu with its items. Items that are not ours have no action.
        """
        ...

    def run_on_main_thread(self, action: Callable[[], None]) -> None:
        """Run an action on the main thread, once the app's loop gets to it.

        Args:
            action: What to run.
        """
        ...

    def on_will_terminate(self, action: Callable[[], None]) -> None:
        """Run an action when macOS is about to end the app, before the process ends.

        Quit ends the process inside macOS: nothing after the window loop runs.
        This is the hook for work that must happen before that.

        Args:
            action: What to run. It may be registered more than once.
        """
        ...

    def request_quit(self) -> None:
        """Ask the app to quit, exactly as "Quit" in its menu does. Main thread only."""
        ...
