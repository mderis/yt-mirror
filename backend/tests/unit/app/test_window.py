"""Tests of ``ytmirror.app.window``, with stand-ins for pywebview and for macOS."""

from collections.abc import Callable
from typing import Self

from tests.fixtures.fakes.native_app import FakeNativeApp
from ytmirror.app.menus import menu_bar
from ytmirror.app.window import DEFAULT_SIZE, MINIMUM_SIZE, open_window

URL = "http://127.0.0.1:5000/?token=t"


class FakeEvent:
    """An event of a pywebview window: handlers are added with ``+=``."""

    def __init__(self) -> None:
        """Start without handlers."""
        self.handlers: list[Callable[[], None]] = []

    def __iadd__(self, handler: Callable[[], None]) -> Self:
        """Add a handler, as pywebview does."""
        self.handlers.append(handler)
        return self


class FakeEvents:
    """The events of a window."""

    def __init__(self) -> None:
        """Start with the one event the app uses."""
        self.shown = FakeEvent()


class FakeWindow:
    """A pywebview window."""

    def __init__(self) -> None:
        """Start with fresh events."""
        self.events = FakeEvents()


class FakeWebview:
    """Records what the app asks of pywebview, and plays its window loop."""

    def __init__(self, native: FakeNativeApp, *, user: str = "closes the window") -> None:
        """Start with the setting pywebview has by default.

        Args:
            native: The stand-in for macOS, whose loop this window loop turns.
            user: What the user does: "closes the window" or "quits".
        """
        self.settings: dict[str, object] = {"OPEN_DEVTOOLS_IN_DEBUG": True}
        self.created: list[dict[str, object]] = []
        self.window = FakeWindow()
        self.started_with_debug: bool | None = None
        self._native = native
        self._user = user

    def create_window(
        self, title: str, url: str, *, width: int, height: int, min_size: tuple[int, int]
    ) -> FakeWindow:
        """Remember the window."""
        self.created.append(
            {"title": title, "url": url, "width": width, "height": height, "min_size": min_size}
        )
        return self.window

    def start(self, *, debug: bool) -> None:
        """Show the window, turn the loop once, then do what the user does."""
        self.started_with_debug = debug
        for handler in self.window.events.shown.handlers:
            handler()
        self._native.turn_loop()
        if self._user == "quits":
            self._native.request_quit()


class Run:
    """One call of ``open_window`` with stand-ins, and what happened in it."""

    def __init__(self, *, debug: bool = False, user: str = "closes the window") -> None:
        """Open the window and let the user act."""
        self.native = FakeNativeApp()
        self.webview = FakeWebview(self.native, user=user)
        self.shutdown_runs = 0
        self.shown_runs = 0
        self.signal_requests: list[Callable[[], None]] = []
        open_window(
            URL,
            title="yt-mirror",
            debug=debug,
            native=self.native,
            menus=menu_bar("yt-mirror"),
            before_quit=self._shutdown,
            when_shown=self._shown,
            webview=self.webview,
            route_stop_signals=self.signal_requests.append,
        )

    def _shutdown(self) -> None:
        self.shutdown_runs += 1

    def _shown(self) -> None:
        self.shown_runs += 1


def test_the_window_shows_the_app_address_under_the_app_name() -> None:
    """R-PL-02: the UI runs in a dedicated window."""
    run = Run()

    (window,) = run.webview.created
    assert window["title"] == "yt-mirror"
    assert window["url"] == URL
    assert run.webview.started_with_debug is False


def test_the_window_cannot_be_made_smaller_than_1100_by_700() -> None:
    """R-PL-03: minimum window size 1100 x 700 points."""
    run = Run()

    (window,) = run.webview.created
    assert window["min_size"] == (1100, 700) == MINIMUM_SIZE
    assert (window["width"], window["height"]) == DEFAULT_SIZE
    assert DEFAULT_SIZE[0] >= MINIMUM_SIZE[0]
    assert DEFAULT_SIZE[1] >= MINIMUM_SIZE[1]


def test_debug_makes_the_developer_tools_available_without_opening_them() -> None:
    """R-IN-06: ``./start --debug`` enables the developer tools in the window."""
    run = Run(debug=True)

    assert run.webview.started_with_debug is True
    assert run.webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] is False


def test_once_the_window_is_shown_the_menu_bar_is_the_apps_own() -> None:
    """R-NA-03: the app's menu bar is put in place when the window is up."""
    run = Run()

    assert [menu.title for menu in run.native.shown_menu_bar()] == ["yt-mirror", "Edit"]
    assert run.shown_runs == 1


class FakeWebviewWhoseLoopHasNotTurnedYet(FakeWebview):
    """A window that is shown, while the app's loop has not run anything yet."""

    def start(self, *, debug: bool) -> None:
        """Show the window and return at once."""
        self.started_with_debug = debug
        for handler in self.window.events.shown.handlers:
            handler()


def test_the_menu_bar_waits_for_the_main_thread() -> None:
    """R-NA-03: the menu bar is set from the app's loop, after the window library set its own."""
    native = FakeNativeApp()

    open_window(
        URL,
        title="yt-mirror",
        debug=False,
        native=native,
        menus=menu_bar("yt-mirror"),
        before_quit=lambda: None,
        webview=FakeWebviewWhoseLoopHasNotTurnedYet(native),
        route_stop_signals=lambda _request: None,
    )

    assert native.shown_menu_bar() == ()
    native.turn_loop()
    assert [menu.title for menu in native.shown_menu_bar()] == ["yt-mirror", "Edit"]


def test_quitting_runs_the_shutdown_work_before_the_app_ends() -> None:
    """R-PL-13: Quit ends the process inside macOS, and the shutdown work runs before that."""
    run = Run(user="quits")

    assert run.native.ended
    assert run.shutdown_runs == 1


def test_closing_the_window_leaves_the_shutdown_work_to_the_caller() -> None:
    """R-PL-13: closing the window returns, so that the caller can shut down."""
    run = Run(user="closes the window")

    assert not run.native.ended
    assert run.shutdown_runs == 0


def test_a_stop_signal_asks_the_app_to_quit_like_the_menu_does() -> None:
    """R-PL-13: Ctrl+C and a termination signal take the same way out as Quit."""
    run = Run()
    (on_signal,) = run.signal_requests

    on_signal()
    assert run.native.quit_requests == 0
    run.native.turn_loop()

    assert run.native.quit_requests == 1
    assert run.shutdown_runs == 1
