"""What is known in memory about the exact-date fetch, for the views.

Shared by the date service, which changes it, and the views, which read it:
the videos being looked up now (R-DT-13), whether the whole fetch is held
back and why (R-FB-01), how far each channel is with its time left and the
key offer (R-DT-14, R-DT-15), and how the API key stands (R-DT-12). Nothing
here is stored: the database is the truth after a restart.

Tests: backend/tests/unit/services/test_dates.py
"""

import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from ytmirror.core.exact_dates import (
    ExactDatesProgress,
    FetchHold,
    KeyState,
    KeyStatus,
    offers_key,
)


@dataclass
class _Run:
    done: int = 0
    total: int = 0
    left_s: int | None = None


@dataclass
class _Known:
    updating: set[str] = field(default_factory=set[str])
    hold: FetchHold | None = None
    active: bool = False
    runs: dict[str, _Run] = field(default_factory=dict[str, _Run])
    key: KeyState = field(default_factory=lambda: KeyState(KeyStatus.NONE))


class DateFetchState:
    """How the exact-date fetch stands, by channel and by video."""

    def __init__(self) -> None:
        """Know of nothing yet."""
        self._lock = threading.Lock()
        self._known = _Known()

    def updating(self, video_id: str) -> bool:
        """Return whether a video is being looked up now."""
        with self._lock:
            return video_id in self._known.updating

    def hold(self) -> FetchHold | None:
        """Return why the whole fetch is held back, or None."""
        with self._lock:
            return self._known.hold

    def key(self) -> KeyState:
        """Return how the API key stands."""
        with self._lock:
            return self._known.key

    def progress(self, channel_id: str) -> ExactDatesProgress | None:
        """Return how far the exact dates of a channel are, or None when none of its dates waits.

        Args:
            channel_id: The channel.
        """
        with self._lock:
            run = self._known.runs.get(channel_id)
            if run is None:
                return None
            key = self._known.key
            return ExactDatesProgress(
                done=run.done,
                total=run.total,
                left_s=run.left_s,
                offer_key=key.status is KeyStatus.NONE and offers_key(run.left_s, key_works=False),
            )

    def running(self, channel_id: str) -> bool:
        """Return whether exact dates of a channel are being fetched now, not held back."""
        with self._lock:
            return (
                self._known.active and self._known.hold is None and channel_id in self._known.runs
            )

    def waits_for_youtube(self, channel_id: str) -> bool:
        """Return whether exact dates of a channel wait for YouTube (R-FB-01)."""
        with self._lock:
            return self._known.hold is not None and channel_id in self._known.runs

    def set_updating(self, video_ids: Sequence[str], updating: bool) -> None:
        """Note that videos are being looked up now, or no longer."""
        with self._lock:
            if updating:
                self._known.updating.update(video_ids)
            else:
                self._known.updating.difference_update(video_ids)

    def set_hold(self, hold: FetchHold | None) -> bool:
        """Note why the whole fetch is held back. Returns whether that changed."""
        with self._lock:
            changed = self._known.hold != hold
            self._known.hold = hold
            return changed

    def set_active(self, active: bool) -> bool:
        """Note whether the fetch runs at all: with a working key, or with lookups switched on."""
        with self._lock:
            changed = self._known.active != active
            self._known.active = active
            return changed

    def set_key(self, key: KeyState) -> bool:
        """Note how the API key stands. Returns whether that changed."""
        with self._lock:
            changed = self._known.key != key
            self._known.key = key
            return changed

    def found(self, channel_id: str) -> None:
        """Count one exact date found for a channel."""
        with self._lock:
            run = self._known.runs.get(channel_id)
            if run is not None:
                run.done += 1

    def waiting(self, order: Sequence[str], left_s: Mapping[str, int]) -> set[str]:
        """Note which videos wait, by their channel in fetch order, and the time left.

        A channel with no video waiting ends its run.

        Args:
            order: The channel of every video that waits, in the order of the fetch.
            left_s: The measured time left by channel, where known.

        Returns:
            The channels whose numbers changed.
        """
        counts: dict[str, int] = {}
        for channel_id in order:
            counts[channel_id] = counts.get(channel_id, 0) + 1
        changed: set[str] = set()
        with self._lock:
            runs = self._known.runs
            for channel_id in list(runs):
                if channel_id not in counts:
                    del runs[channel_id]
                    changed.add(channel_id)
            for channel_id, count in counts.items():
                run = runs.setdefault(channel_id, _Run())
                before = (run.total, run.left_s)
                run.total = run.done + count
                run.left_s = left_s.get(channel_id)
                if (run.total, run.left_s) != before:
                    changed.add(channel_id)
        return changed

    def forget(self, channel_id: str) -> None:
        """Drop what is known of a channel that was removed."""
        with self._lock:
            self._known.runs.pop(channel_id, None)
