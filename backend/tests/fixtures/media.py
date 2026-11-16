"""A real ffmpeg for the tests that read and write media files.

The tests take ffmpeg and ffprobe from ``YTM_TEST_FFMPEG_DIR`` when it is
set (CI installs each ffmpeg source there, D-053), else from the tools of
the app folder, which they only read (TESTING rule 9). Without either they
are skipped, unless ``YTM_REQUIRE_FFMPEG`` is set, as in CI.
"""

import os
import subprocess
from pathlib import Path

import pytest

from tests.conftest import REAL_TOOLS


def ffmpeg_dir() -> Path:
    """Return the folder with ffmpeg and ffprobe, or skip or fail the test without one."""
    given = os.environ.get("YTM_TEST_FFMPEG_DIR")
    folder = Path(given) if given else REAL_TOOLS / "ffmpeg"
    if (folder / "ffmpeg").is_file() and (folder / "ffprobe").is_file():
        return folder
    if os.environ.get("YTM_REQUIRE_FFMPEG"):
        pytest.fail(f"ffmpeg and ffprobe are needed in {folder}")
    pytest.skip(f"no ffmpeg in {folder}")


def make_media(
    ffmpeg: Path,
    target: Path,
    *,
    seconds: int = 3,
    audio: bool = True,
    inputs: list[str] | None = None,
    extra: list[str] | None = None,
) -> Path:
    """Write a small real video file with ffmpeg.

    Args:
        ffmpeg: The ffmpeg program.
        target: The file. Its ending chooses the container.
        seconds: The length.
        audio: Whether it has an audio stream.
        inputs: More inputs, each as ``-i <file>``.
        extra: More arguments before the target, for example tags.

    Returns:
        The file.
    """
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size=320x180:rate=30:duration={seconds}",
    ]
    if audio:
        command += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
    command += [
        *(inputs or []),
        "-c:v",
        "mpeg4",
        *(["-c:a", "aac"] if audio else []),
        *(extra or []),
    ]
    subprocess.run([*command, "-y", str(target)], check=True)
    return target
