"""A Mac app that exists only in memory. Fake of the NativeApp port."""

from collections.abc import Callable, Sequence

from ytmirror.core.models import AppIdentity, Menu, ShownMenu, ShownMenuItem


class FakeNativeApp:
    """Remembers what it is asked, and lets a test play macOS."""

    def __init__(self, identity: AppIdentity | None = None) -> None:
        """Start as an app without a menu bar.

        Args:
            identity: What macOS calls the app. Default: an installed yt-mirror.
        """
        self._identity = identity or AppIdentity("yt-mirror", "io.github.mderis.yt-mirror")
        self._menus: tuple[Menu, ...] = ()
        self._waiting: list[Callable[[], None]] = []
        self._before_end: list[Callable[[], None]] = []
        self.quit_requests = 0
        self.ended = False

    def identity(self) -> AppIdentity:
        """Return the configured identity."""
        return self._identity

    def show_menu_bar(self, menus: Sequence[Menu]) -> None:
        """Remember the menu bar."""
        self._menus = tuple(menus)

    def shown_menu_bar(self) -> tuple[ShownMenu, ...]:
        """Return the remembered menu bar, every item enabled."""
        return tuple(
            ShownMenu(
                title=menu.title,
                items=tuple(
                    ShownMenuItem(item.title, item.action, item.shortcut, enabled=True)
                    for group in menu.groups
                    for item in group
                ),
            )
            for menu in self._menus
        )

    def run_on_main_thread(self, action: Callable[[], None]) -> None:
        """Keep the action until the loop turns."""
        self._waiting.append(action)

    def on_will_terminate(self, action: Callable[[], None]) -> None:
        """Remember what to run before the app ends."""
        self._before_end.append(action)

    def request_quit(self) -> None:
        """Count the request and end the app, as "Quit" does."""
        self.quit_requests += 1
        self.end()

    def turn_loop(self) -> None:
        """Play the app's loop: run what was handed to the main thread."""
        waiting, self._waiting = self._waiting, []
        for action in waiting:
            action()

    def end(self) -> None:
        """Play macOS ending the app: run what was registered for that moment."""
        for action in self._before_end:
            action()
        self.ended = True
