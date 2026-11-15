"""Tests of the MediaTools port with the real ffprobe."""

from pathlib import Path

import pytest

from tests.fixtures.media import ffmpeg_dir, make_media
from ytmirror.adapters.media_tools import FfprobeMediaTools, facts_of
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.media import verification_problem


@pytest.fixture
def ffmpeg() -> Path:
    """The folder of the real ffmpeg and ffprobe."""
    return ffmpeg_dir()


def test_a_finished_mkv_is_read_with_its_streams_tags_and_tracks(
    ffmpeg: Path, tmp_path: Path
) -> None:
    """R-UI-08, R-MD-01, R-MD-03: the formats, tags, subtitles and cover of a file are read."""
    subtitles = tmp_path / "en.srt"
    subtitles.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
    cover = make_media(
        ffmpeg / "ffmpeg", tmp_path / "cover.png", seconds=1, audio=False, extra=["-frames:v", "1"]
    )
    video = make_media(
        ffmpeg / "ffmpeg",
        tmp_path / "video.mkv",
        inputs=["-i", str(subtitles)],
        extra=[
            "-map",
            "0",
            "-map",
            "1",
            "-map",
            "2",
            "-c:s",
            "srt",
            "-metadata:s:s:0",
            "language=eng",
            "-attach",
            str(cover),
            "-metadata:s:t",
            "mimetype=image/png",
            "-metadata:s:t",
            "filename=cover.png",
            "-metadata",
            "title=How I organize my workshop",
        ],
    )

    facts = FfprobeMediaTools(ffmpeg / "ffprobe").probe(video)

    assert "matroska" in facts.container
    assert (facts.width, facts.height, facts.fps) == (320, 180, 30.0)
    assert (facts.vcodec, facts.acodec, facts.audio_channels) == ("mpeg4", "aac", 1)
    assert facts.duration_s is not None
    assert abs(facts.duration_s - 3) < 0.2
    assert [track.language for track in facts.subtitles] == ["eng"]
    assert facts.attachments == ("cover.png",)
    assert facts.tags["title"] == "How I organize my workshop"
    assert verification_problem(facts, expected_duration_s=3) is None


def test_a_file_without_audio_fails_verification(ffmpeg: Path, tmp_path: Path) -> None:
    """R-QA-06: a file with video only is not a finished video."""
    video = make_media(ffmpeg / "ffmpeg", tmp_path / "silent.mkv", audio=False)

    facts = FfprobeMediaTools(ffmpeg / "ffprobe").probe(video)

    assert verification_problem(facts, expected_duration_s=3) == "the file has no audio stream"


def test_a_file_that_is_not_media_fails_with_its_reason(ffmpeg: Path, tmp_path: Path) -> None:
    """R-QA-06, R-ER-02: a broken file fails verification with ffprobe's reason."""
    broken = tmp_path / "broken.mkv"
    broken.write_bytes(b"not a video at all")

    with pytest.raises(AppError) as failure:
        FfprobeMediaTools(ffmpeg / "ffprobe").probe(broken)

    assert failure.value.code is ErrorCode.VERIFY_FAILED
    assert failure.value.details["reason"]


def test_a_missing_ffprobe_is_a_missing_tool(tmp_path: Path) -> None:
    """R-IN-04: when ffprobe cannot run, the tool is reported missing."""
    with pytest.raises(AppError) as failure:
        FfprobeMediaTools(tmp_path / "no-ffprobe").probe(tmp_path / "video.mkv")

    assert failure.value.code is ErrorCode.TOOL_MISSING


def test_odd_answers_of_ffprobe_give_no_made_up_facts() -> None:
    """R-UI-08: values ffprobe does not give stay unknown."""
    facts = facts_of({"format": {"format_name": "matroska,webm", "duration": "n/a"}})

    assert facts.duration_s is None
    assert (facts.vcodec, facts.acodec, facts.fps, facts.height) == (None, None, None, None)
    assert facts_of({"streams": [{"codec_type": "video", "avg_frame_rate": "0/0"}]}).fps is None
