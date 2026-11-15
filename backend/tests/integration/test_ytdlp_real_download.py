"""Tests of ``download_with_ytdlp`` with the real yt-dlp and the real ffmpeg.

A local HTTP server, started and stopped by each test, serves a small real
MKV; yt-dlp downloads it as a direct link, so nothing leaves this Mac. These
show what the stand-in of ``test_ytdlp_download.py`` assumes: the tags of the
app reach the file, and a cancel from either hook of yt-dlp comes out as a
cancel, not as a failure.
"""

import functools
import os
import threading
from collections.abc import Iterator, Mapping
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from tests.fixtures.media import ffmpeg_dir, make_media
from ytmirror.adapters.media_tools import FfprobeMediaTools
from ytmirror.adapters.ytdlp_gateway import DOWNLOAD_OPTIONS, TAGS_STEP, download_with_ytdlp
from ytmirror.core.jobs import DownloadCancelledError

pytestmark = pytest.mark.media


class _Videos(SimpleHTTPRequestHandler):
    """Serves the files of one folder, MKV with its media type, and logs nothing."""

    def guess_type(self, path: str | os.PathLike[str]) -> str:
        return "video/x-matroska" if str(path).endswith(".mkv") else super().guess_type(path)

    def log_message(self, format: str, *args: Any) -> None:
        return


@pytest.fixture
def ffmpeg() -> Path:
    """The folder of the real ffmpeg and ffprobe."""
    return ffmpeg_dir()


@pytest.fixture
def address(ffmpeg: Path, tmp_path: Path) -> Iterator[str]:
    """The address of a small real MKV on a server on this Mac."""
    served = tmp_path / "served"
    served.mkdir()
    make_media(ffmpeg / "ffmpeg", served / "clip0000001.mkv", seconds=2)
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(_Videos, directory=str(served))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/clip0000001.mkv"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def options(ffmpeg: Path, work: Path, **more: Any) -> dict[str, Any]:
    """The download options of the app, without the steps a direct link has nothing for."""
    return {
        **DOWNLOAD_OPTIONS,
        "writethumbnail": False,
        "postprocessors": [
            step for step in DOWNLOAD_OPTIONS["postprocessors"] if step["key"] == "FFmpegMetadata"
        ],
        "ffmpeg_location": str(ffmpeg),
        "outtmpl": {"default": str(work / "%(id)s.%(ext)s")},
        **more,
    }


def test_a_real_download_carries_the_tags_of_the_app(
    ffmpeg: Path, address: str, tmp_path: Path
) -> None:
    """R-MD-01, R-DT-08: the video ID and the published time are tags of the file yt-dlp makes."""
    work = tmp_path / "work"
    tags = {"video_id": "clip0000001", "published_at": "2026-11-01T12:00:00Z"}

    answer: Mapping[str, Any] = download_with_ytdlp(address, options(ffmpeg, work), tags)

    file = work / "clip0000001.mkv"
    facts = FfprobeMediaTools(ffmpeg / "ffprobe").probe(file)
    assert answer["id"] == "clip0000001"
    assert facts.tags.get("video_id") == "clip0000001"
    assert facts.tags.get("published_at") == "2026-11-01T12:00:00Z"


def cancel(report: Mapping[str, Any]) -> None:
    """A hook that cancels, as the hooks of the gateway do when Cancel was pressed."""
    raise DownloadCancelledError(f"cancelled at {report.get('status')}")


def test_a_cancel_while_the_bytes_arrive_comes_out_of_yt_dlp_as_a_cancel(
    ffmpeg: Path, address: str, tmp_path: Path
) -> None:
    """R-QU-02: the progress hook ends the real download, and the gateway sees a cancel."""
    work = tmp_path / "work"

    with pytest.raises(DownloadCancelledError):
        download_with_ytdlp(address, options(ffmpeg, work, progress_hooks=[cancel]), {})

    assert not (work / "clip0000001.mkv").exists()


def test_a_cancel_between_processing_steps_comes_out_of_yt_dlp_as_a_cancel(
    ffmpeg: Path, address: str, tmp_path: Path
) -> None:
    """R-QU-02: the post-processor hook ends the real download before the metadata step."""
    work = tmp_path / "work"
    steps: list[str] = []

    def cancel_at_the_metadata_step(report: Mapping[str, Any]) -> None:
        steps.append(str(report.get("postprocessor")))
        if report.get("postprocessor") == "Metadata":
            cancel(report)

    with pytest.raises(DownloadCancelledError):
        download_with_ytdlp(
            address,
            options(ffmpeg, work, postprocessor_hooks=[cancel_at_the_metadata_step]),
            {"video_id": "clip0000001"},
        )

    assert steps[-1] == "Metadata"


def test_the_hook_is_called_for_the_tags_step_before_the_bytes_arrive(
    ffmpeg: Path, address: str, tmp_path: Path
) -> None:
    """R-QU-04: what the stand-in of yt-dlp does first, the real one does: the tags step."""
    told: list[str] = []

    def downloading(report: Mapping[str, Any]) -> None:
        told.append(f"bytes {report.get('status')}")

    def processing(report: Mapping[str, Any]) -> None:
        told.append(f"{report.get('postprocessor')} {report.get('status')}")

    download_with_ytdlp(
        address,
        options(
            ffmpeg,
            tmp_path / "work",
            progress_hooks=[downloading],
            postprocessor_hooks=[processing],
        ),
        {"video_id": "clip0000001"},
    )

    assert told[:2] == [f"{TAGS_STEP} started", f"{TAGS_STEP} finished"]
    assert told[2].startswith("bytes ")
    assert "Metadata started" in told[told.index(told[2]) :]
