"""A Mac app that exists only in memory. Fake of the NativeApp port."""

from collections.abc import Callable, Sequence

from ytmirror.core.models import (
    AppIdentity,
    ItemState,
    Menu,
    MenuCommand,
    ShownMenu,
    ShownMenuItem,
)


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
        self.alerts: list[tuple[str, str]] = []
        self._state_of: Callable[[MenuCommand], ItemState] | None = None
        self._on_command: Callable[[MenuCommand], None] | None = None
        self.session_ending = False
        """Whether the quit macOS asks for now is a logout, a restart or a shutdown."""

    def identity(self) -> AppIdentity:
        """Return the configured identity."""
        return self._identity

    def show_menu_bar(
        self,
        menus: Sequence[Menu],
        state_of: Callable[[MenuCommand], ItemState] | None = None,
        on_command: Callable[[MenuCommand], None] | None = None,
    ) -> None:
        """Remember the menu bar and how its command items are validated and run."""
        self._menus = tuple(menus)
        self._state_of = state_of
        self._on_command = on_command

    def shown_menu_bar(self) -> tuple[ShownMenu, ...]:
        """Return the remembered menu bar, validated as macOS validates it before showing it."""
        items: list[ShownMenu] = []
        for menu in self._menus:
            shown: list[ShownMenuItem] = []
            for group in menu.groups:
                for item in group:
                    state = ItemState(enabled=True)
                    if item.command is not None and self._state_of is not None:
                        state = self._state_of(item.command)
                    shown.append(
                        ShownMenuItem(
                            state.title or item.title,
                            item.action,
                            item.shortcut,
                            enabled=state.enabled,
                            command=item.command,
                            checked=state.checked,
                        )
                    )
            items.append(ShownMenu(title=menu.title, items=tuple(shown)))
        return tuple(items)

    def choose(self, command: MenuCommand) -> None:
        """Play the user choosing a command item of the menu bar."""
        assert self._on_command is not None, "No menu bar with commands is shown"
        self._on_command(command)

    def ending_session(self) -> bool:
        """Return whether the test plays a logout, a restart or a shutdown."""
        return self.session_ending

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

    def show_alert(self, title: str, text: str) -> None:
        """Remember the message, as if the user read it and closed it."""
        self.alerts.append((title, text))

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
