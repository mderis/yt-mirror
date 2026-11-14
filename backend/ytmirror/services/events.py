"""The in-process event bus that feeds the live updates of the interface.

Services publish typed events (docs/ARCHITECTURE.md section 7.6). The HTTP
layer subscribes and passes them on to the window as Server-Sent Events.
Milestone M1 has one event, ``ToolUpdated``. Later milestones add theirs.

This module must not know HTTP. A listener is called in the thread that
publishes, so it has to be quick and must not block.

Tests: backend/tests/unit/services/test_events.py
"""

import threading
from collections.abc import Callable

from ytmirror.core.models import AppEvent

type Listener = Callable[[AppEvent | None], None]
"""Receives every event. Receives None once, when the app stops: nothing follows."""


class EventBus:
    """Hands every published event to every listener."""

    def __init__(self) -> None:
        """Create a bus without listeners."""
        self._lock = threading.Lock()
        self._listeners: list[Listener] = []
        self._closed = False

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        """Start handing events to a listener.

        Args:
            listener: Called with every event from now on, and with None when
                the app stops. On a bus that was closed it gets None at once.

        Returns:
            A function that stops the listening.
        """
        with self._lock:
            closed = self._closed
            if not closed:
                self._listeners.append(listener)
        if closed:
            listener(None)

        def unsubscribe() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return unsubscribe

    def publish(self, event: AppEvent) -> None:
        """Hand an event to every listener. Does nothing after the bus was closed.

        Args:
            event: The event.
        """
        with self._lock:
            listeners = [] if self._closed else list(self._listeners)
        for listener in listeners:
            listener(event)

    def close(self) -> None:
        """Tell every listener that the app stops, and take no more events."""
        with self._lock:
            listeners = [] if self._closed else list(self._listeners)
            self._closed = True
            self._listeners.clear()
        for listener in listeners:
            listener(None)
