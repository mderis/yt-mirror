"""Live test of a download: one real short video from the real YouTube, end to end.

Opt-in with ``uv run pytest -m live``, never run in CI (docs/TESTING.md
section 8). It uses the ffmpeg and Deno of the app folder, which it only
reads (TESTING rule 9), and keeps everything else in a temp folder.
"""

from pathlib import Path

import pytest

from tests.conftest import REAL_TOOLS
from ytmirror.adapters.filesystem_mac import MacFileSystem
from ytmirror.adapters.media_tools import FfprobeMediaTools
from ytmirror.app.config import AppPaths
from ytmirror.app.container import build_container
from ytmirror.core.channels import Quality, VideoStatus
from ytmirror.core.media import verification_problem
from ytmirror.services.channels import NewChannel

pytestmark = pytest.mark.live

# The first channel of YouTube: one video of 19 seconds since 2005.
CHANNEL = "@jawed"


def test_one_real_video_is_downloaded_at_480p_with_metadata_and_dates(tmp_path: Path) -> None:
    """R-QA-02, R-QL-01, R-QL-03, R-MD-01, R-MD-02, R-DT-07: a real download, verified."""
    if not (REAL_TOOLS / "ffmpeg" / "ffprobe").is_file() or not (REAL_TOOLS / "deno").is_dir():
        pytest.fail("the live download needs the tools of the app folder: run ./start once")
    data = tmp_path / "data"
    paths = AppPaths(
        code_root=tmp_path,
        home_dir=tmp_path,
        data_dir=data,
        logs_dir=data / "logs",
        database_file=data / "yt-mirror.db",
        frontend_dir=tmp_path / "frontend",
        uv_executable=tmp_path / "uv",
        tool_dir=REAL_TOOLS,
        cache_dir=data / "cache",
        default_library=tmp_path / "library",
    )
    app = build_container(paths, files=MacFileSystem(trash=lambda _path: None))
    app.schema.bring_up_to_date()
    looked_up = app.channels.lookup(CHANNEL)
    app.channels.add(NewChannel(looked_up.facts.channel_id, quality=Quality.P480))
    assert app.catalogue.work_once() is True
    video_id = app.videos.videos(looked_up.facts.channel_id)[0].id

    app.downloader.mirror([video_id])
    assert app.downloader.work_once() is True

    video = app.videos.video(video_id)
    assert video is not None
    assert (video.status, video.last_error_code) == (VideoStatus.SYNCED, None)
    assert video.file_name is not None
    file = paths.default_library / looked_up.facts.title / video.file_name
    facts = FfprobeMediaTools(REAL_TOOLS / "ffmpeg" / "ffprobe").probe(file)
    assert verification_problem(facts, 19) is None
    assert facts.height is not None
    assert facts.height <= 480
    assert facts.tags["video_id"] == video_id
    assert facts.tags["published_at"].startswith("2005-04-2")
    assert facts.chapters >= 1
    assert "info.json" in facts.attachments
    assert any(name.startswith("cover") for name in facts.attachments)
    assert [track.language for track in facts.subtitles] == ["eng"]
    assert facts.tags["title"] == video.title
    assert facts.tags["artist"] == looked_up.facts.title
    assert video.published_exact is True
    stat = file.stat()
    assert (int(stat.st_birthtime), int(stat.st_mtime)) == (video.published_at, video.published_at)
    assert (file.parent / ".yt-mirror" / f"{video_id}.info.json").is_file()
    assert (file.parent / ".yt-mirror" / f"{video_id}.jpg").read_bytes().startswith(b"\xff\xd8")
    assert (paths.cache_dir / "deno").is_dir()
