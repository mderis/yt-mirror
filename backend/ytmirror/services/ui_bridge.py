"""What the app window and the interface tell each other (docs/ARCHITECTURE.md section 7.10).

Implements the service side of D-094 and of the decision part of the quit
path (R-NA-04, R-NA-06, R-QU-12, D-052):

- The interface reports its state (``PUT /api/ui/state``); the menu bar is
  enabled and titled from the last report.
- A chosen command item of the menu bar is passed on to the interface as an
  event, which runs what its own control runs.
- A quit is held while downloads run and someone can be asked: the interface
  is connected. The interface asks; "Quit" confirms and the app quits. A
  logout, a restart, a shutdown, Ctrl+C and a termination signal are never
  held: there is nobody to wait for.

Everything here is called from the main thread of the window as well, while
macOS waits for an answer, so nothing here touches the database.

Tests: backend/tests/unit/services/test_ui_bridge.py
"""

import threading
from collections.abc import Callable

import structlog

from ytmirror.core.models import MenuCommand, MenuCommanded, QuitAsked, UiState
from ytmirror.services.events import EventBus

_log = structlog.get_logger(__name__)


class UiBridge:
    """The state the interface reported, the menu commands, and the quit question."""

    def __init__(self, events: EventBus, downloading_now: Callable[[], int]) -> None:
        """Create the bridge. Nothing is reported yet: the Channel menu waits for a report.

        Args:
            events: The bus the interface listens to.
            downloading_now: How many downloads run now, from memory.
        """
        self._events = events
        self._downloading_now = downloading_now
        self._lock = threading.Lock()
        self._state = UiState()
        self._windows = 0
        self._confirmed = False
        self._quit: Callable[[], None] | None = None
        self._watchers: list[Callable[[UiState], None]] = []

    def report(self, state: UiState) -> None:
        """Keep what the interface reports about itself (R-NA-04).

        Args:
            state: The state, as the interface sees it now.
        """
        with self._lock:
            self._state = state
            watchers = list(self._watchers)
        for watcher in watchers:
            watcher(state)

    def state(self) -> UiState:
        """Return the state the interface last reported."""
        with self._lock:
            return self._state

    def watch(self, watcher: Callable[[UiState], None]) -> None:
        """Call a function with every new report. For the window report of the tests.

        Args:
            watcher: Called in the thread that reports.
        """
        with self._lock:
            self._watchers.append(watcher)

    def command(self, command: MenuCommand) -> None:
        """Pass a command chosen in the menu bar on to the interface (D-094).

        Args:
            command: The command of the item.
        """
        _log.info("menu.command", msg="A command was chosen in the menu bar", command=command.value)
        self._events.publish(MenuCommanded(command))

    def window_connected(self) -> Callable[[], None]:
        """Count an interface that listens to the events, until the returned function is called."""
        with self._lock:
            self._windows += 1
        done = threading.Event()

        def disconnected() -> None:
            if done.is_set():
                return
            done.set()
            with self._lock:
                self._windows -= 1

        return disconnected

    def on_quit(self, quit_now: Callable[[], None]) -> None:
        """Set how a confirmed quit ends the app. The window sets it.

        Args:
            quit_now: Asks the app to quit. It may be called from any thread.
        """
        with self._lock:
            self._quit = quit_now

    def let_quit(self, reason: str) -> None:
        """Let the next quit through without a question.

        Args:
            reason: Why, for the log: ``signal``.
        """
        with self._lock:
            self._confirmed = True
        _log.info("app.quit_passed", msg="The quit is not held", reason=reason)

    def may_quit(self, *, ending_session: bool) -> bool:
        """Decide whether the app may quit now, or holds the quit to ask (R-NA-06, R-QU-12).

        Called by every way of quitting, on the main thread, while macOS waits.

        Args:
            ending_session: Whether macOS asks because of a logout, a restart or a shutdown.

        Returns:
            True to quit, False to hold the quit while the interface asks.
        """
        with self._lock:
            confirmed = self._confirmed
            windows = self._windows
        if confirmed:
            return True
        if ending_session:
            _log.info("app.quit_passed", msg="The quit is not held", reason="session_end")
            return True
        downloading = self._downloading_now()
        if downloading == 0 or windows == 0:
            return True
        _log.info(
            "app.quit_held",
            msg="The quit waits for an answer, as downloads run",
            downloading=downloading,
        )
        self._events.publish(QuitAsked())
        return False

    def confirm_quit(self) -> None:
        """Quit after all: the user chose "Quit" in the question (R-QU-12)."""
        with self._lock:
            self._confirmed = True
            quit_now = self._quit
        _log.info("app.quit_confirmed", msg="The user confirmed the quit")
        if quit_now is not None:
            quit_now()
