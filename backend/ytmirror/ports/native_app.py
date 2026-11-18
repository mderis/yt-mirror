"""The NativeApp port: the parts of a Mac app that macOS itself draws and decides.

The menu bar (R-NA-03), the name under which macOS knows the running app
(R-NA-01), and the end of the app (R-PL-13). The window itself is not part of
this port: it belongs to ``app/window.py``.

Tests: backend/tests/integration/test_native_app_contract.py
"""

from collections.abc import Callable, Sequence
from typing import Protocol

from ytmirror.core.models import AppIdentity, ItemState, Menu, MenuCommand, ShownMenu


class NativeApp(Protocol):
    """Talks to macOS about the running app."""

    def identity(self) -> AppIdentity:
        """Return the name and the bundle identifier under which macOS knows this process."""
        ...

    def show_menu_bar(
        self,
        menus: Sequence[Menu],
        state_of: Callable[[MenuCommand], ItemState] | None = None,
        on_command: Callable[[MenuCommand], None] | None = None,
    ) -> None:
        """Replace the whole menu bar of the app. Call it on the main thread.

        Args:
            menus: The menus, from left to right. The first one is the app menu.
            state_of: Says, each time macOS is about to show or trigger a command
                item, whether it is enabled, its title and its check mark (R-NA-04).
                Without it every command item is enabled.
            on_command: Runs the command of a chosen item (D-094). Main thread.
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

    def bring_to_front(self) -> None:
        """Bring the app and its window to the front, also from the Dock or minimized.

        Before the question of a held quit (R-QU-12, D-096). Main thread only.
        """
        ...

    def ending_session(self) -> bool:
        """Tell whether the quit macOS asks for now comes from a logout, a restart or a shutdown.

        Such a quit is never held for a question (R-NA-06, ARCHITECTURE 7.10).
        Main thread only, while macOS asks whether the app may quit.
        """
        ...

    def show_alert(self, title: str, text: str) -> None:
        """Show a message in a window of its own, and return when the user closed it.

        For a start that cannot go on, before the window of the app exists
        (R-QA-07). Main thread only.

        Args:
            title: What happened, in one sentence.
            text: What it means for the user's data, and what to do.
        """
        ...
