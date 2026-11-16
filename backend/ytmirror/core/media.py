"""What a finished video file contains, and whether it passes verification.

Implements step 5 of the download (docs/ARCHITECTURE.md section 7.2): the
file opens, has a video and an audio stream, and its duration is within two
seconds of what YouTube said. A file that fails is never put in its place
(R-QA-06).

This module must not read files: the facts are passed in.

Tests: backend/tests/unit/core/test_media.py
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

DURATION_TOLERANCE_S = 2.0
"""How far the duration of a file may be from the duration YouTube gave."""


@dataclass(frozen=True, slots=True)
class SubtitleTrack:
    """One subtitle track of a file.

    Attributes:
        language: The language code, for example ``eng``, or None.
        title: The title of the track, or None.
    """

    language: str | None
    title: str | None


@dataclass(frozen=True, slots=True)
class MediaFacts:
    """What ffprobe found in a file.

    Attributes:
        container: The container format, for example ``matroska,webm``.
        duration_s: The length in seconds, or None.
        width: The width of the video stream, or None without one.
        height: The height of the video stream, or None without one.
        fps: Frames per second, or None.
        vcodec: The codec of the video stream, or None without one.
        acodec: The codec of the audio stream, or None without one.
        audio_channels: The number of audio channels, or None.
        subtitles: The subtitle tracks.
        attachments: The file names of the attachments, for example the cover.
        tags: The tags of the file, with lower-case names.
        chapters: How many chapters the file has.
    """

    container: str
    duration_s: float | None
    width: int | None
    height: int | None
    fps: float | None
    vcodec: str | None
    acodec: str | None
    audio_channels: int | None
    subtitles: tuple[SubtitleTrack, ...] = ()
    attachments: tuple[str, ...] = ()
    tags: Mapping[str, str] = field(default_factory=dict[str, str])
    chapters: int = 0


def verification_problem(facts: MediaFacts, expected_duration_s: int | None) -> str | None:
    """Return why a finished file fails verification, or None when it passes.

    Args:
        facts: What ffprobe found in the file.
        expected_duration_s: The length YouTube gave, or None when unknown.

    Returns:
        A short reason for the logs, or None.
    """
    if "matroska" not in facts.container:
        return f"the container is {facts.container}, not MKV"
    if facts.vcodec is None:
        return "the file has no video stream"
    if facts.acodec is None:
        return "the file has no audio stream"
    if expected_duration_s is not None and (
        facts.duration_s is None
        or abs(facts.duration_s - expected_duration_s) > DURATION_TOLERANCE_S
    ):
        return f"the file lasts {facts.duration_s} s, YouTube said {expected_duration_s} s"
    return None
