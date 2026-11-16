"""The MediaTools port with ffprobe.

ffprobe is the program of the ffmpeg tool in the app folder; its path is
given by the container (R-PL-15: no program from PATH).

Tests: backend/tests/integration/test_media_tools.py
"""

import json
import subprocess
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import structlog
from structlog.typing import FilteringBoundLogger

from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.media import MediaFacts, SubtitleTrack

_log: FilteringBoundLogger = structlog.get_logger(__name__)

_TIMEOUT_S = 60


class FfprobeMediaTools:
    """Reads media files with ffprobe."""

    def __init__(self, ffprobe: Path) -> None:
        """Create the adapter.

        Args:
            ffprobe: The ffprobe program of the ffmpeg tool.
        """
        self._ffprobe = ffprobe

    def probe(self, path: Path) -> MediaFacts:
        """Return what a media file contains.

        Args:
            path: The file.

        Raises:
            AppError: ``VERIFY_FAILED`` or ``TOOL_MISSING``.
        """
        command = [
            str(self._ffprobe),
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            "-show_chapters",
            str(path),
        ]
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=_TIMEOUT_S, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise AppError(
                ErrorCode.TOOL_MISSING, {"tool": "ffprobe", "reason": str(error)}
            ) from error
        _log.debug("ffprobe.ran", msg="ffprobe read a file", exit_code=result.returncode)
        if result.returncode != 0:
            raise AppError(
                ErrorCode.VERIFY_FAILED,
                {"file": str(path), "reason": result.stderr.strip()[-500:]},
            )
        try:
            answer = json.loads(result.stdout)
        except ValueError as error:
            raise AppError(
                ErrorCode.VERIFY_FAILED,
                {"file": str(path), "reason": f"ffprobe gave no JSON: {error}"},
            ) from error
        return facts_of(_mapping(answer))


def facts_of(answer: Mapping[str, Any]) -> MediaFacts:
    """Return the facts in the JSON answer of ffprobe.

    Args:
        answer: What ffprobe printed with ``-print_format json``.
    """
    streams = [_mapping(stream) for stream in _list(answer.get("streams"))]
    container = _mapping(answer.get("format"))
    video = _first(streams, "video", attached_picture=False)
    audio = _first(streams, "audio")
    return MediaFacts(
        container=str(container.get("format_name", "")),
        duration_s=_float(container.get("duration")),
        width=_int(video.get("width")),
        height=_int(video.get("height")),
        fps=_rate(video.get("avg_frame_rate")),
        vcodec=_text(video.get("codec_name")),
        acodec=_text(audio.get("codec_name")),
        audio_channels=_int(audio.get("channels")),
        subtitles=tuple(
            SubtitleTrack(
                language=_text(_mapping(stream.get("tags")).get("language")),
                title=_text(_mapping(stream.get("tags")).get("title")),
            )
            for stream in streams
            if stream.get("codec_type") == "subtitle"
        ),
        attachments=tuple(
            _text(_mapping(stream.get("tags")).get("filename")) or "cover"
            for stream in streams
            if stream.get("codec_type") == "attachment"
            or _mapping(stream.get("disposition")).get("attached_pic") == 1
        ),
        tags={
            str(name).lower(): str(value) for name, value in _mapping(container.get("tags")).items()
        },
        chapters=len(_list(answer.get("chapters"))),
    )


def _first(
    streams: list[dict[str, Any]], kind: str, *, attached_picture: bool | None = None
) -> dict[str, Any]:
    """Return the first stream of a kind, or an empty mapping when there is none."""
    for stream in streams:
        if stream.get("codec_type") != kind:
            continue
        picture = _mapping(stream.get("disposition")).get("attached_pic") == 1
        if attached_picture is None or picture == attached_picture:
            return stream
    return {}


def _mapping(value: object) -> dict[str, Any]:
    return cast("dict[str, Any]", value) if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return cast("list[object]", value) if isinstance(value, list) else []


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _float(value: object) -> float | None:
    try:
        return float(str(value))
    except ValueError:
        return None


def _int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _rate(value: object) -> float | None:
    try:
        rate = Fraction(str(value))
    except ValueError, ZeroDivisionError:
        return None
    return round(float(rate), 3) if rate else None
