"""Tests of ``ytmirror.services.ui_bridge``: the menu state, the commands and the quit question."""

from ytmirror.core.models import MenuCommand, MenuCommanded, QuitAsked, UiState, ViewKind
from ytmirror.services.events import EventBus
from ytmirror.services.ui_bridge import UiBridge


class Bridge:
    """A bridge with a number of running downloads the test sets, and what it published."""

    def __init__(self, downloading: int = 1) -> None:
        """Start with an interface that listens, and downloads that run."""
        self.downloading = downloading
        self.bus = EventBus()
        self.events: list[object] = []
        self.bus.subscribe(self.events.append)
        self.bridge = UiBridge(self.bus, lambda: self.downloading)
        self.quits = 0
        self.bridge.on_quit(self._quit)
        self.gone = self.bridge.window_connected()

    def _quit(self) -> None:
        self.quits += 1


def test_the_menu_state_is_the_last_one_the_interface_reported() -> None:
    """R-NA-04: the menu bar is enabled from the last report; before one, nothing is open."""
    bridge = Bridge().bridge
    seen: list[UiState] = []
    bridge.watch(seen.append)
    assert bridge.state() == UiState()

    reported = UiState(channel_open=True, paused=True, view=ViewKind.GRID)
    bridge.report(reported)

    assert bridge.state() == reported
    assert seen == [reported]


def test_a_menu_command_is_passed_on_to_the_interface() -> None:
    """R-NA-03, D-094: the menu bar holds no logic; the interface runs the command."""
    made = Bridge()

    made.bridge.command(MenuCommand.CHECK_NOW)

    assert made.events == [MenuCommanded(MenuCommand.CHECK_NOW)]


def test_a_quit_while_downloads_run_is_held_and_the_interface_asks() -> None:
    """R-QU-12, R-NA-06: the quit waits, and the interface is told to ask."""
    made = Bridge(downloading=2)

    assert made.bridge.may_quit(ending_session=False) is False
    assert made.events == [QuitAsked()]
    # Asked again while the question is open: it is asked again, and still held.
    assert made.bridge.may_quit(ending_session=False) is False
    assert made.events == [QuitAsked(), QuitAsked()]


def test_a_quit_without_running_downloads_goes_on() -> None:
    """R-QU-12: only running downloads make the app ask."""
    made = Bridge(downloading=0)

    assert made.bridge.may_quit(ending_session=False) is True
    assert made.events == []


def test_a_logout_a_restart_or_a_shutdown_is_never_held() -> None:
    """R-NA-06, ARCHITECTURE 7.10: the end of a session goes straight to the shutdown work."""
    made = Bridge(downloading=3)

    assert made.bridge.may_quit(ending_session=True) is True
    assert made.events == []


def test_without_an_interface_to_ask_nothing_is_held() -> None:
    """R-QU-12: a quit is held only when someone can answer, so the app never gets stuck."""
    made = Bridge(downloading=1)
    made.gone()
    made.gone()  # A second call changes nothing.

    assert made.bridge.may_quit(ending_session=False) is True


def test_confirming_quits_and_the_quit_is_then_let_through() -> None:
    """R-QU-12: "Quit" in the question ends the app, although downloads run."""
    made = Bridge(downloading=1)
    assert made.bridge.may_quit(ending_session=False) is False

    made.bridge.confirm_quit()

    assert made.quits == 1
    assert made.bridge.may_quit(ending_session=False) is True


def test_a_stop_signal_lets_the_quit_through() -> None:
    """R-NA-06: Ctrl+C and a termination signal are never held."""
    made = Bridge(downloading=1)

    made.bridge.let_quit("signal")

    assert made.bridge.may_quit(ending_session=False) is True
    assert made.events == []
