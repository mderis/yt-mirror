"""The acceptance test of milestone M3, on real files (IMPLEMENTATION-PLAN.md).

A video mirrored from the fake YouTube is a valid MKV with the right name,
embedded metadata, cover and subtitles, and creation and modification dates
equal to the published time. Everything is real but YouTube: the container,
the database, the file system of macOS, ffmpeg and ffprobe.
"""

import calendar
import dataclasses
import json
import os
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.fixtures.media import ffmpeg_dir
from ytmirror.adapters.filesystem_mac import MacFileSystem
from ytmirror.adapters.media_tools import FfprobeMediaTools
from ytmirror.app.config import AppPaths
from ytmirror.app.container import Container, build_container
from ytmirror.core.channels import VideoStatus
from ytmirror.core.media import MediaFacts
from ytmirror.services.channels import NewChannel

pytestmark = pytest.mark.media

FAKE_YOUTUBE = Path(__file__).resolve().parents[4] / "e2e" / "fixtures" / "youtube"


def moment(text: str) -> int:
    """Return an ISO time in UTC as seconds since the epoch."""
    return calendar.timegm(time.strptime(text, "%Y-%m-%dT%H:%M:%SZ"))


@pytest.fixture(params=["UTC", "Asia/Tehran"])
def zone(request: pytest.FixtureRequest) -> Iterator[str]:
    """Run in a time zone, as CI runs the whole suite in both (TESTING rule 4)."""
    before = os.environ.get("TZ")
    os.environ["TZ"] = request.param
    time.tzset()
    yield request.param
    if before is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = before
    time.tzset()


@pytest.fixture
def app(paths: AppPaths, tmp_path: Path) -> Container:
    """The real container with the fake YouTube and the real ffmpeg."""
    trash = tmp_path / "trash"

    def to_trash(path: Path) -> None:
        trash.mkdir(exist_ok=True)
        path.rename(trash / path.name)

    container = build_container(
        dataclasses.replace(paths, fake_youtube=FAKE_YOUTUBE, tool_dir=ffmpeg_dir().parent),
        files=MacFileSystem(trash=to_trash),
    )
    container.schema.bring_up_to_date()
    return container


def mirrored(app: Container, handle: str, video_id: str) -> Path:
    """Add a channel, list it, mirror one video and let it download. Returns the channel folder."""
    looked_up = app.channels.lookup(handle)
    app.channels.add(NewChannel(looked_up.facts.channel_id))
    assert app.catalogue.work_once() is True
    app.downloader.mirror([video_id])
    assert app.downloader.work_once() is True
    view = app.views.of(looked_up.facts.channel_id)
    assert view is not None
    return Path(view.folder)


def probe(file: Path) -> MediaFacts:
    """Read a file with the real ffprobe."""
    return FfprobeMediaTools(ffmpeg_dir() / "ffprobe").probe(file)


def test_a_mirrored_video_is_a_valid_mkv_with_metadata_cover_subtitles_and_dates(
    app: Container, paths: AppPaths, zone: str
) -> None:
    """R-MI-01, R-FN-01, R-QL-03, R-MD-01, R-MD-02, R-MD-03, R-MD-05, R-DT-07, R-DT-08, R-LG-02."""
    folder = mirrored(app, "@failingdownloads", "fail0000ok0")

    video = app.videos.video("fail0000ok0")
    assert video is not None
    published = moment("2026-11-13T09:15:22Z")
    file = folder / "This one works.mkv"
    facts = probe(file)
    birth = file.stat()
    assert video.status is VideoStatus.SYNCED
    assert video.file_name == file.name
    assert "matroska" in facts.container
    assert facts.vcodec is not None
    assert facts.acodec is not None
    assert facts.tags["title"] == "This one works"
    assert facts.tags["artist"] == "Failing Downloads"
    assert facts.tags["video_id"] == "fail0000ok0"
    assert facts.tags["published_at"] == "2026-11-13T09:15:22Z"
    assert facts.chapters == 2
    assert [track.title for track in facts.subtitles] == ["English"]
    assert set(facts.attachments) == {"info.json", "cover.jpg"}
    assert (int(birth.st_birthtime), int(birth.st_mtime)) == (published, published)
    assert video.published_at == published
    assert json.loads((folder / ".yt-mirror" / "fail0000ok0.info.json").read_text())["id"] == (
        "fail0000ok0"
    )
    assert (folder / ".yt-mirror" / "fail0000ok0.jpg").read_bytes().startswith(b"\xff\xd8")
    assert sorted(entry.name for entry in folder.iterdir()) == [".yt-mirror", file.name]
    assert sorted(entry.name for entry in (folder / ".yt-mirror").iterdir()) == [
        "fail0000ok0.info.json",
        "fail0000ok0.jpg",
        "tmp",
    ]
    assert list((folder / ".yt-mirror" / "tmp").iterdir()) == []
    assert len(list((paths.logs_dir / "jobs").glob("*.log"))) == 1


def test_a_premiere_has_its_release_time_as_its_file_dates(app: Container) -> None:
    """R-DT-03, R-DT-07: a premiere's file dates are when it became public."""
    folder = mirrored(app, "@premierechannel", "prem0000001")

    facts = (folder / "A premiere that has been shown.mkv").stat()

    released = moment("2026-11-10T18:30:00Z")
    assert (int(facts.st_birthtime), int(facts.st_mtime)) == (released, released)


def test_auto_generated_subtitles_are_embedded_and_labelled(app: Container) -> None:
    """R-MD-03: without creator subtitles the auto-generated ones are embedded, labelled."""
    folder = mirrored(app, "@autosubtitles", "autosubs001")

    facts = probe(folder / "A video with automatic subtitles.mkv")

    assert [track.title for track in facts.subtitles] == ["English (auto-generated)"]
    assert app.videos.video("autosubs001").has_subtitles == "auto"  # pyright: ignore[reportOptionalMemberAccess]


def test_a_video_without_subtitles_is_synced_without_a_track(app: Container) -> None:
    """R-MD-03: a video without English subtitles syncs without a subtitle track."""
    folder = mirrored(app, "@nosubtitles", "nosubs00001")

    assert probe(folder / "A video without subtitles.mkv").subtitles == ()


def test_subtitles_that_fail_still_give_a_synced_video(app: Container) -> None:
    """R-MD-04: the video is completed without subtitles."""
    folder = mirrored(app, "@failingdownloads", "failsubs001")

    video = app.videos.video("failsubs001")
    assert video is not None
    assert (video.status, video.has_subtitles) == (VideoStatus.SYNCED, None)
    assert probe(folder / "Its subtitles fail.mkv").subtitles == ()


def test_a_failed_download_leaves_no_file(app: Container) -> None:
    """R-QU-08, R-FI-03: a members-only video fails with its code and nothing is left."""
    folder = mirrored(app, "@failingdownloads", "fail0000001")

    video = app.videos.video("fail0000001")
    assert video is not None
    assert (video.status, video.last_error_code) == (VideoStatus.FAILED, "MEMBERS_ONLY")
    assert [entry.name for entry in folder.iterdir()] in ([], [".yt-mirror"])
    assert list(folder.rglob("*.mkv")) == []
