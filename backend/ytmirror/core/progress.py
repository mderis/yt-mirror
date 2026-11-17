"""One progress for the whole Mirror: every part of a download, weighted by its bytes.

Implements R-QU-04 (docs/DECISIONS.md D-088). yt-dlp downloads the parts of
a video one after another (the thumbnail, the subtitles, the video stream,
the audio stream) and reports each from 0 to 100%. This module adds them up
into one percent that goes from 0 to 100% once: the sizes known before the
download, estimates for the others, each corrected as soon as its real size
is told, and the percent shown never goes down. The time left comes from the
speed measured over the last seconds, and only once that speed is stable.

The gateway of yt-dlp and the fake YouTube both feed it, one report per
part, as yt-dlp sends them.

This module must not read a clock: every time is passed in, in seconds of a
clock that never goes back.

Tests: backend/tests/unit/core/test_progress.py
"""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

SUBTITLES_ESTIMATE = 100_000
"""The bytes a subtitle file is taken to have until its size is known."""

THUMBNAIL_ESTIMATE = 150_000
"""The bytes a thumbnail is taken to have. yt-dlp does not report its download."""

SPEED_WINDOW_S = 10.0
"""The speed is measured over this many of the last seconds."""

STABLE_AFTER_S = 5.0
"""The time left is told only once the speed was measured over this long."""

_ALMOST_DONE = 0.99
"""The percent stays below 100% until every part is finished, whatever the estimates."""


class PartKind(StrEnum):
    """What a part of a download is."""

    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLES = "subtitles"
    THUMBNAIL = "thumbnail"


@dataclass(frozen=True, slots=True)
class PlannedPart:
    """A part a download is going to fetch, as known before it starts.

    Attributes:
        key: What tells its reports apart: the format ID of a stream, or the kind.
        kind: What it is.
        size: Its size in bytes, or None when it is not known.
    """

    key: str
    kind: PartKind
    size: int | None


@dataclass(frozen=True, slots=True)
class PartProgress:
    """How far one part of a download is, for the details panel (R-QU-04).

    Attributes:
        kind: What it is.
        size: Its size in bytes, real or estimated.
        done: How many of its bytes arrived.
        estimated: Whether the size is an estimate.
        finished: Whether it is complete.
    """

    kind: PartKind
    size: int
    done: int
    estimated: bool
    finished: bool


@dataclass(frozen=True, slots=True)
class Totals:
    """How far a whole download is.

    Attributes:
        fraction: From 0 to 1, never less than told before.
        done_bytes: The bytes that arrived, of all parts.
        total_bytes: The bytes of all parts, real or estimated.
        speed_bps: The measured speed, or None.
        left_s: The time left, or None until the speed is stable.
        parts: Each part.
    """

    fraction: float
    done_bytes: int
    total_bytes: int
    speed_bps: float | None
    left_s: int | None
    parts: tuple[PartProgress, ...]


@dataclass
class _Part:
    kind: PartKind
    size: int
    estimated: bool
    done: int = 0
    finished: bool = False


class ProgressTracker:
    """Adds the parts of one download up. Not safe for threads: one download uses it."""

    def __init__(self, planned: Sequence[PlannedPart]) -> None:
        """Start with the parts known before the download.

        Args:
            planned: The parts, in the order they are fetched.
        """
        self._parts: dict[str, _Part] = {}
        for part in planned:
            self._add(part.key, part.kind, part.size)
        self._shown = 0.0
        self._samples: deque[tuple[float, int]] = deque()

    def arrived(self, key: str, kind: PartKind, done: int, size: int | None, now: float) -> Totals:
        """Note how many bytes of a part arrived.

        Args:
            key: The part, as planned. A part that was not planned is added.
            kind: What it is.
            done: Its bytes that arrived.
            size: Its real size, when the report tells it.
            now: The time, in seconds of a clock that never goes back.
        """
        part = self._parts.get(key) or self._add(key, kind, size)
        if size is not None and size > 0:
            part.size, part.estimated = size, False
        part.done = max(part.done, done)
        if part.estimated and part.done > part.size:
            part.size = part.done
        return self._totals(now)

    def finished(self, key: str, kind: PartKind, size: int | None, now: float) -> Totals:
        """Note that a part is complete.

        Args:
            key: The part.
            kind: What it is.
            size: Its final size, when it is told.
            now: The time.
        """
        part = self._parts.get(key) or self._add(key, kind, size)
        final = size if size is not None and size > 0 else max(part.done, part.size)
        part.size, part.done, part.estimated, part.finished = final, final, False, True
        return self._totals(now)

    def finish_kind(self, kind: PartKind, now: float) -> Totals:
        """Note that every part of a kind is complete, for one yt-dlp does not report."""
        for part in self._parts.values():
            if part.kind is kind and not part.finished:
                part.done, part.estimated, part.finished = part.size, False, True
        return self._totals(now)

    def _add(self, key: str, kind: PartKind, size: int | None) -> _Part:
        known = size is not None and size > 0
        part = _Part(
            kind=kind, size=size if known and size else _estimate(kind), estimated=not known
        )
        self._parts[key] = part
        return part

    def _totals(self, now: float) -> Totals:
        parts = list(self._parts.values())
        total = sum(part.size for part in parts)
        done = sum(min(part.done, part.size) for part in parts)
        complete = all(part.finished for part in parts)
        measured = 1.0 if complete else min(_ALMOST_DONE, done / total if total else 0.0)
        self._shown = max(self._shown, measured)
        speed = self._speed(done, now)
        stable = speed is not None and now - self._samples[0][0] >= STABLE_AFTER_S
        left = round((total - done) / speed) if stable and speed else None
        return Totals(
            fraction=self._shown,
            done_bytes=done,
            total_bytes=total,
            speed_bps=speed,
            left_s=max(left, 0) if left is not None else None,
            parts=tuple(
                PartProgress(
                    kind=part.kind,
                    size=part.size,
                    done=min(part.done, part.size),
                    estimated=part.estimated,
                    finished=part.finished,
                )
                for part in parts
            ),
        )

    def _speed(self, done: int, now: float) -> float | None:
        self._samples.append((now, done))
        while len(self._samples) > 1 and now - self._samples[0][0] > SPEED_WINDOW_S:
            self._samples.popleft()
        first_at, first_done = self._samples[0]
        if now <= first_at:
            return None
        return (done - first_done) / (now - first_at)


def _estimate(kind: PartKind) -> int:
    """Return the size a part is taken to have while its own is not known."""
    if kind is PartKind.THUMBNAIL:
        return THUMBNAIL_ESTIMATE
    return SUBTITLES_ESTIMATE


def stream_size(
    filesize: int | None, approx: int | None, tbr_kbps: float | None, duration_s: float | None
) -> int | None:
    """Return the size of a stream as yt-dlp knows it before the download, or an estimate.

    Args:
        filesize: The exact size, when YouTube gives it.
        approx: yt-dlp's estimate, when it has one.
        tbr_kbps: The bitrate in kilobits per second, when known.
        duration_s: The length of the video, when known.

    Returns:
        Bytes, or None when nothing tells the size.
    """
    if filesize:
        return filesize
    if approx:
        return approx
    if tbr_kbps and duration_s:
        return round(tbr_kbps * 1000 / 8 * duration_s)
    return None
