"""What auto-mirror waits for the user about, by channel (D-092, D-095).

Shared by the auto-mirror service, which changes it, and the views, which
show it with the channel. Kept in memory: auto-mirror finds it again from the
stored channel after a restart.

Tests: backend/tests/unit/services/test_auto_mirror.py
"""

import threading

from ytmirror.core.auto_mirror import AutoMirrorQuestion


class AutoMirrorState:
    """What auto-mirror waits for the user about, by channel. Shared with the views."""

    def __init__(self) -> None:
        """Know of no question."""
        self._lock = threading.Lock()
        self._questions: dict[str, AutoMirrorQuestion] = {}
        self._missing: dict[str, int] = {}

    def question(self, channel_id: str) -> AutoMirrorQuestion | None:
        """Return the question before a large start of a channel, or None (D-095)."""
        with self._lock:
            return self._questions.get(channel_id)

    def missing_held(self, channel_id: str) -> int | None:
        """Return how many missing files of a channel wait for the user, or None (D-092)."""
        with self._lock:
            return self._missing.get(channel_id)

    def set(
        self, channel_id: str, question: AutoMirrorQuestion | None, missing: int | None
    ) -> bool:
        """Note what a channel waits for. Returns whether it changed."""
        with self._lock:
            before = (self._questions.get(channel_id), self._missing.get(channel_id))
            if question is None:
                self._questions.pop(channel_id, None)
            else:
                self._questions[channel_id] = question
            if missing is None:
                self._missing.pop(channel_id, None)
            else:
                self._missing[channel_id] = missing
            return before != (question, missing)
