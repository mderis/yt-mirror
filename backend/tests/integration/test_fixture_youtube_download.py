"""Tests of the downloads of the fake YouTube: real MKV files, written with the real ffmpeg.

These files stand for what yt-dlp writes (ARCHITECTURE section 7.3), so the
rest of the download is tested on real files (TESTING section 4).
"""

import json
from pathlib import Path
from typing import Any

import pytest

from tests.fixtures.media import ffmpeg_dir
from ytmirror.adapters.fixture_youtube import FixtureYouTube
from ytmirror.adapters.media_tools import FfprobeMediaTools
from ytmirror.core.channels import Quality
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.jobs import (
    DownloadCancelledError,
    DownloadProgress,
    DownloadRequest,
    Stage,
    SubtitleKind,
    SubtitlesFailedError,
)
from ytmirror.core.media import verification_problem

pytestmark = pytest.mark.media

PUBLISHED = "2026-10-30T17:02:41Z"
PUBLISHED_S = 1_793_379_761


def channel(folder: Path, **download: Any) -> Path:
    """Write a fixture channel with two videos, the first with download facts. Gives its folder."""
    world = folder / "youtube"
    world.mkdir()
    (world / "one.json").write_text(
        json.dumps(
            {
                "id": "UCdownloadsdownloads0001",
                "title": "Download Channel",
                "handle": "@downloads",
                "listed_at": "2026-11-14T06:42:00Z",
                "video_count": 2,
                "videos": [
                    {
                        "id": "dl000000001",
                        "title": "How I organize my workshop",
                        "point": "2026-10-30",
                        "published_at": PUBLISHED,
                        "chapters": [[0, "Intro"], [1, "Tools"]],
                        **download,
                    },
                    {"id": "dl000000002", "title": "A second video", "point": "2026-10-01"},
                ],
            }
        ),
        encoding="utf-8",
    )
    return world


def youtube(tmp_path: Path, **download: Any) -> FixtureYouTube:
    """The fake YouTube with the real ffmpeg."""
    return FixtureYouTube(
        channel(tmp_path, **download), sleep=lambda _s: None, ffmpeg=ffmpeg_dir() / "ffmpeg"
    )


def request(tmp_path: Path, video_id: str = "dl000000001", **changes: Any) -> DownloadRequest:
    """Return a download into a temp folder of a job."""
    return DownloadRequest(
        video_id=video_id,
        quality=Quality.BEST,
        work_folder=tmp_path / "Download Channel" / ".yt-mirror" / "tmp" / "01JOB",
        log_file=tmp_path / "logs" / "01JOB.log",
        **changes,
    )


def never() -> bool:
    """Is never cancelled."""
    return False


def test_a_download_is_a_valid_mkv_with_metadata_chapters_subtitles_and_cover(
    tmp_path: Path,
) -> None:
    """R-QL-03, R-MD-01, R-MD-02, R-MD-03, R-DT-08: the file has everything a real download has."""
    result = youtube(tmp_path).download(request(tmp_path), lambda _progress: None, never)

    facts = FfprobeMediaTools(ffmpeg_dir() / "ffprobe").probe(result.file)
    assert verification_problem(facts, result.duration_s) is None
    assert facts.tags["title"] == "How I organize my workshop"
    assert facts.tags["artist"] == "Download Channel"
    assert facts.tags["purl"] == "https://www.youtube.com/watch?v=dl000000001"
    assert facts.tags["published_at"] == PUBLISHED
    assert facts.tags["video_id"] == "dl000000001"
    assert facts.tags["description"] == "The description of How I organize my workshop."
    assert facts.chapters == 2
    assert [(track.language, track.title) for track in facts.subtitles] == [("eng", "English")]
    assert set(facts.attachments) == {"info.json", "cover.jpg"}
    assert json.loads(result.info_json)["id"] == "dl000000001"
    assert result.thumbnail is not None
    assert result.thumbnail.read_bytes().startswith(b"\xff\xd8")
    assert (result.upload_time, result.release_time) == (PUBLISHED_S, None)


def test_auto_generated_subtitles_are_labelled_as_such(tmp_path: Path) -> None:
    """R-MD-03: auto-generated subtitles are embedded and labelled as auto-generated."""
    result = youtube(tmp_path, subtitles="auto").download(
        request(tmp_path), lambda _progress: None, never
    )

    facts = FfprobeMediaTools(ffmpeg_dir() / "ffprobe").probe(result.file)
    assert result.subtitles is SubtitleKind.AUTO
    assert [track.title for track in facts.subtitles] == ["English (auto-generated)"]


def test_a_video_without_english_subtitles_has_none(tmp_path: Path) -> None:
    """R-MD-03: without subtitles in English, the file has no subtitle track."""
    result = youtube(tmp_path, subtitles="none").download(
        request(tmp_path), lambda _progress: None, never
    )

    facts = FfprobeMediaTools(ffmpeg_dir() / "ffprobe").probe(result.file)
    assert result.subtitles is None
    assert facts.subtitles == ()


def test_a_premiere_is_tagged_with_its_release_time(tmp_path: Path) -> None:
    """R-DT-03, R-DT-08: the published time of a premiere is when it became public."""
    result = youtube(tmp_path, release_at="2026-10-31T18:00:00Z").download(
        request(tmp_path), lambda _progress: None, never
    )

    facts = FfprobeMediaTools(ffmpeg_dir() / "ffprobe").probe(result.file)
    assert facts.tags["published_at"] == "2026-10-31T18:00:00Z"
    assert result.release_time == 1_793_469_600


def test_progress_goes_through_video_audio_and_processing(tmp_path: Path) -> None:
    """R-QU-04, D-088: the fake sends video and audio as separate downloads, like yt-dlp.

    One percent for the whole Mirror grows once through both streams, then processing.
    """
    told: list[DownloadProgress] = []

    youtube(tmp_path).download(request(tmp_path), told.append, never)

    assert [report.stage for report in told] == [Stage.VIDEO] * 4 + [Stage.AUDIO] * 4 + [
        Stage.PROCESSING
    ]
    fractions = [report.fraction or 0 for report in told[:8]]
    assert fractions == sorted(fractions)
    assert fractions.count(1.0) == 1
    assert 0.7 < (told[3].fraction or 0) < 0.8
    assert told[7].fraction == 1.0
    assert told[7].downloaded_bytes == told[7].total_bytes
    video_parts = [part for part in told[3].parts if part.kind.value == "video"]
    assert video_parts[0].finished
    assert told[8].fraction is None


def test_a_download_without_a_size_is_estimated_and_never_goes_down(tmp_path: Path) -> None:
    """R-QU-04, D-088: with ``size_unknown`` the sizes are estimated and the percent only grows."""
    told: list[DownloadProgress] = []

    youtube(tmp_path, size_unknown=True).download(request(tmp_path), told.append, never)

    fractions = [report.fraction or 0 for report in told[:8]]
    assert fractions == sorted(fractions)
    assert fractions[-1] == 1.0
    assert any(part.estimated for part in told[0].parts)


def test_a_cancel_ends_the_download_before_its_file_is_written(tmp_path: Path) -> None:
    """R-QU-02: a cancel while the bytes arrive leaves no MKV."""
    told: list[DownloadProgress] = []
    asked = request(tmp_path)

    with pytest.raises(DownloadCancelledError):
        youtube(tmp_path).download(asked, told.append, lambda: len(told) >= 2)

    assert not (asked.work_folder / "dl000000001.mkv").exists()


def test_a_fixture_can_fail_a_download_with_a_code(tmp_path: Path) -> None:
    """R-ER-02: the fake can fail like YouTube, with the code of the failure."""
    with pytest.raises(AppError) as failure:
        youtube(tmp_path, download_fails="MEMBERS_ONLY").download(
            request(tmp_path), lambda _progress: None, never
        )

    assert failure.value.code is ErrorCode.MEMBERS_ONLY


def test_a_fixture_can_fail_only_the_subtitles(tmp_path: Path) -> None:
    """R-MD-04: the fake can fail the subtitles, and succeeds without them."""
    fake = youtube(tmp_path, subtitles_fail=True)

    with pytest.raises(SubtitlesFailedError):
        fake.download(request(tmp_path), lambda _progress: None, never)
    result = fake.download(request(tmp_path, manual_subtitles=False), lambda _progress: None, never)

    assert result.subtitles is None


def test_an_unknown_video_is_gone(tmp_path: Path) -> None:
    """R-ER-02: a video no fixture channel has is reported as removed."""
    with pytest.raises(AppError) as failure:
        youtube(tmp_path).download(request(tmp_path, "nosuchvideo"), lambda _progress: None, never)

    assert failure.value.code is ErrorCode.VIDEO_REMOVED


def test_without_ffmpeg_the_fake_cannot_write_a_file(tmp_path: Path) -> None:
    """R-IN-04: a download needs ffmpeg, and its absence is a missing tool."""
    fake = FixtureYouTube(channel(tmp_path), sleep=lambda _s: None)

    with pytest.raises(AppError) as failure:
        fake.download(request(tmp_path), lambda _progress: None, never)

    assert failure.value.code is ErrorCode.TOOL_MISSING


def test_a_download_can_be_held_in_the_middle_until_it_is_cancelled(tmp_path: Path) -> None:
    """infra: ``hold_after_report`` keeps a row in the middle of a download for a screenshot."""
    told: list[DownloadProgress] = []
    cancelled = False

    def cancel_when_held() -> bool:
        return cancelled

    def told_and_cancel_on_hold(progress: DownloadProgress) -> None:
        nonlocal cancelled
        told.append(progress)
        cancelled = len(told) == 3

    held = youtube(tmp_path, hold_after_report=3, hold_ms=60_000)

    with pytest.raises(DownloadCancelledError, match="held"):
        held.download(request(tmp_path), told_and_cancel_on_hold, cancel_when_held)

    assert len(told) == 3
    assert 0.5 < (told[-1].fraction or 0) < 0.6
