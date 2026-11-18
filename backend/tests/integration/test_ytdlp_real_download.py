"""Tests of ``download_with_ytdlp`` with the real yt-dlp and the real ffmpeg.

A local HTTP server, started and stopped by each test, serves a small real
MKV; yt-dlp downloads it as a direct link, so nothing leaves this Mac. These
show what the stand-in of ``test_ytdlp_download.py`` assumes: the tags of the
app reach the file, a cancel from either hook of yt-dlp comes out as a
cancel, not as a failure, and a download stopped half way continues from its
partial file with the options of the app (R-QU-05).
"""

import functools
import importlib
import os
import subprocess
import threading
from collections.abc import Iterator, Mapping
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar

import pytest

from tests.fixtures.media import ffmpeg_dir, make_media
from ytmirror.adapters.child_processes_mac import names_folder
from ytmirror.adapters.media_tools import FfprobeMediaTools
from ytmirror.adapters.ytdlp_gateway import (
    DOWNLOAD_OPTIONS,
    TAGS_STEP,
    download_with_ytdlp,
    extract_with_ytdlp,
)
from ytmirror.core.jobs import DownloadCancelledError

pytestmark = pytest.mark.media


class _Videos(SimpleHTTPRequestHandler):
    """Serves the files of one folder, MKV with its media type, and logs nothing.

    Every request is noted in ``asked``, as its method and path.
    """

    asked: ClassVar[list[str]] = []

    def send_head(self) -> Any:
        _Videos.asked.append(f"{self.command} {self.path}")
        return super().send_head()

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


def looked_up(address: str) -> Mapping[str, Any]:
    """The metadata of the clip, as the lookup before a download gives it."""
    return extract_with_ytdlp(address, {"quiet": True, "cachedir": False}, True)


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

    answer: Mapping[str, Any] = download_with_ytdlp(looked_up(address), options(ffmpeg, work), tags)

    file = work / "clip0000001.mkv"
    facts = FfprobeMediaTools(ffmpeg / "ffprobe").probe(file)
    assert answer["id"] == "clip0000001"
    assert facts.tags.get("video_id") == "clip0000001"
    assert facts.tags.get("published_at") == "2026-11-01T12:00:00Z"


def cancel(report: Mapping[str, Any]) -> None:
    """A hook that cancels, as the hooks of the gateway do when Cancel was pressed."""
    raise DownloadCancelledError(f"cancelled at {report.get('status')}")


def test_a_download_asks_the_server_only_for_the_file_after_its_lookup(
    ffmpeg: Path, address: str, tmp_path: Path
) -> None:
    """R-DT-06, D-088, D-089: the download is made from the lookup; the page is not asked again."""
    info = looked_up(address)
    _Videos.asked.clear()

    download_with_ytdlp(info, options(ffmpeg, tmp_path / "work"), {})

    assert _Videos.asked == ["GET /clip0000001.mkv"]


def test_a_cancel_while_the_bytes_arrive_comes_out_of_yt_dlp_as_a_cancel(
    ffmpeg: Path, address: str, tmp_path: Path
) -> None:
    """R-QU-02: the progress hook ends the real download, and the gateway sees a cancel."""
    work = tmp_path / "work"

    with pytest.raises(DownloadCancelledError):
        download_with_ytdlp(looked_up(address), options(ffmpeg, work, progress_hooks=[cancel]), {})

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
            looked_up(address),
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
        looked_up(address),
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


@pytest.fixture
def served(tmp_path: Path) -> Iterator[tuple[str, Path]]:
    """A server on this Mac for the files of a folder. Gives its address and the folder."""
    folder = tmp_path / "served"
    folder.mkdir()
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(_Videos, directory=str(folder))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", folder
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def recording_tools(ffmpeg: Path, folder: Path) -> Path:
    """Stand-ins for ffmpeg and ffprobe that note their arguments and run the real ones.

    Returns the file of the notes: one line per call, the arguments split by US (0x1f).
    """
    folder.mkdir()
    notes = folder / "calls.txt"
    for program in ("ffmpeg", "ffprobe"):
        tool = folder / program
        tool.write_text(
            "#!/bin/bash\n"
            f"{{ printf '%s\\x1f' {program} \"$@\"; printf '\\n'; }} >> '{notes}'\n"
            f"exec '{ffmpeg / program}' \"$@\"\n"
        )
        tool.chmod(0o755)
    return notes


def test_every_ffmpeg_step_of_a_real_download_names_the_job_folder(
    ffmpeg: Path, served: tuple[str, Path], tmp_path: Path
) -> None:
    """R-QU-02: Cancel finds the ffmpeg of its job by the temp folder in its arguments.

    Real yt-dlp merges a video and an audio stream, converts the thumbnail and
    embeds the subtitles, the metadata and the cover, as for YouTube. Every
    call of ffmpeg or ffprobe that works on a file names the job folder.
    """
    address, folder = served
    make_media(ffmpeg / "ffmpeg", folder / "video.mp4", seconds=2, audio=False)
    quiet = [str(ffmpeg / "ffmpeg"), "-hide_banner", "-loglevel", "error", "-f", "lavfi"]
    subprocess.run(
        [*quiet, "-i", "sine=duration=2", "-c:a", "aac", "-y", str(folder / "audio.m4a")],
        check=True,
    )
    subprocess.run(
        [*quiet, "-i", "color=c=red:s=64x36", "-frames:v", "1", "-y", str(folder / "cover.png")],
        check=True,
    )
    (folder / "en.vtt").write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nHello\n")
    notes = recording_tools(ffmpeg, tmp_path / "tools")
    work = tmp_path / "library" / "Channel" / ".yt-mirror" / "tmp" / "01JD0000000000000000000001"
    information = {
        "id": "clip0000001",
        "title": "A clip",
        "extractor": "generic",
        "extractor_key": "Generic",
        "webpage_url": f"{address}/watch",
        "duration": 2,
        "formats": [
            {"format_id": "v", "url": f"{address}/video.mp4", "ext": "mp4"}
            | {"vcodec": "mpeg4", "acodec": "none", "protocol": "http"},
            {"format_id": "a", "url": f"{address}/audio.m4a", "ext": "m4a"}
            | {"vcodec": "none", "acodec": "aac", "protocol": "http"},
        ],
        "subtitles": {"en": [{"url": f"{address}/en.vtt", "ext": "vtt"}]},
        "thumbnails": [{"url": f"{address}/cover.png", "id": "0"}],
    }
    yt_dlp = importlib.import_module("yt_dlp")
    settings = {
        **DOWNLOAD_OPTIONS,
        "format": "v+a",
        "writesubtitles": True,
        "subtitleslangs": ["en"],
        "ffmpeg_location": str(tmp_path / "tools"),
        "outtmpl": {"default": str(work / "%(id)s.%(ext)s")},
    }

    with yt_dlp.YoutubeDL(settings) as ydl:
        ydl.process_ie_result(information, download=True)

    calls = [line.split("\x1f")[:-1] for line in notes.read_text().splitlines()]
    # yt-dlp gives ffmpeg its files as "file:<path>".
    working = [call for call in calls if any(argument.startswith("file:") for argument in call)]
    asking = [call for call in calls if call not in working]
    facts = FfprobeMediaTools(ffmpeg / "ffprobe").probe(work / "clip0000001.mkv")
    assert (facts.vcodec, facts.acodec, len(facts.subtitles)) == ("mpeg4", "aac", 1)
    # The thumbnail, the merge, the subtitles, the metadata and the cover.
    assert len([call for call in working if call[0] == "ffmpeg"]) == 5
    assert all(names_folder(call[1:], work) for call in working), working
    # What does not name the folder only asks ffmpeg what it is: it ends at once.
    assert all(set(call[1:]) <= {"-version", "-bsfs", "-hide_banner"} for call in asking), asking


class _RangeVideos(_Videos):
    """Serves files as ``_Videos`` does, and answers a request for a part of a file (Range).

    Each request is noted with the part it asked for, as ``GET /path bytes=N-``.
    """

    def send_head(self) -> Any:
        wanted = self.headers.get("Range")
        if not wanted or not wanted.startswith("bytes="):
            return super().send_head()
        _Videos.asked.append(f"{self.command} {self.path} {wanted}")
        path = Path(self.translate_path(self.path))
        start = int(wanted.removeprefix("bytes=").split("-")[0])
        size = path.stat().st_size
        file = path.open("rb")
        file.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{size - 1}/{size}")
        self.send_header("Content-Length", str(size - start))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        return file


@pytest.fixture
def ranged(ffmpeg: Path, tmp_path: Path) -> Iterator[str]:
    """The address of a real MKV of a few hundred KB on a server that serves parts of files."""
    served = tmp_path / "served"
    served.mkdir()
    make_media(ffmpeg / "ffmpeg", served / "clip0000002.mkv", seconds=20)
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(_RangeVideos, directory=str(served))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/clip0000002.mkv"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def stop_after(size: int) -> Any:
    """A progress hook that stops the download once ``size`` bytes arrived, as a quit does."""

    def hook(report: Mapping[str, Any]) -> None:
        if report.get("status") == "downloading" and (report.get("downloaded_bytes") or 0) >= size:
            raise DownloadCancelledError("stopped by a quit")

    return hook


def test_a_stopped_download_continues_from_its_partial_file(
    ffmpeg: Path, ranged: str, tmp_path: Path
) -> None:
    """R-QU-05, D-091: a download stopped half way asks only for the rest when it runs again."""
    work = tmp_path / "work"
    info = looked_up(ranged)
    total = (tmp_path / "served" / "clip0000002.mkv").stat().st_size
    stopping = options(ffmpeg, work, progress_hooks=[stop_after(total // 3)])
    with pytest.raises(DownloadCancelledError):
        download_with_ytdlp(info, stopping, {})
    parts = list(work.glob("*.part"))
    assert len(parts) == 1, sorted(path.name for path in work.iterdir())
    kept = parts[0].stat().st_size
    assert 0 < kept < total
    again = looked_up(ranged)  # a resume after a quit reads the metadata again (D-089)
    _Videos.asked.clear()

    download_with_ytdlp(again, options(ffmpeg, work), {})

    assert _Videos.asked == [f"GET /clip0000002.mkv bytes={kept}-"]
    assert (work / "clip0000002.mkv").stat().st_size >= total
