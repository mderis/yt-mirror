"""Tests of the tool that records answers of yt-dlp: what it keeps and what it replaces."""

from tests.fixtures.ytdlp_replay import RECORDINGS_FILE, recordings
from ytmirror.tools.record_ytdlp import (
    RECORDED_CHANNEL_ID,
    RECORDED_HANDLE,
    RECORDED_TITLE,
    RECORDINGS_DIR,
    anonymised,
    recorded_video_id,
    without_names,
)

REAL_ID = "UCrealrealrealrealreal00"
ANSWER = {
    "_type": "playlist",
    "channel_id": REAL_ID,
    "channel": "A Real Channel",
    "uploader": "A Real Channel",
    "uploader_id": "@arealchannel",
    "description": "Words of a real person",
    "tags": ["real"],
    "webpage_url": "https://www.youtube.com/@arealchannel/videos",
    "thumbnails": [
        {"url": "https://yt3.googleusercontent.com/realkey=s900", "width": 900, "height": 900},
        {"url": "https://yt3.googleusercontent.com/realkey=s0", "id": "avatar_uncropped"},
    ],
    "entries": [
        {
            "_type": "url",
            "id": "realVideo01",
            "title": "A real title",
            "url": "https://www.youtube.com/watch?v=realVideo01",
            "duration": 754,
            "view_count": 4100000,
            "timestamp": 1763078400,
            "live_status": None,
            "thumbnails": [
                {"url": "https://i.ytimg.com/vi/realVideo01/hq720.jpg?sqp=x", "width": 360},
                {"url": "https://i.ytimg.com/vi/realVideo01/hq720.jpg?sqp=y", "width": 720},
            ],
        }
    ],
}


def test_a_recording_names_no_real_channel_or_video() -> None:
    """infra: every title, name, ID and address of a recorded answer is replaced."""
    kept = anonymised(ANSWER, REAL_ID, RECORDED_CHANNEL_ID)

    text = str(kept)
    for real in ("real", "Real", "sqp", "Words"):
        assert real not in text, real
    assert kept["channel_id"] == RECORDED_CHANNEL_ID
    assert (kept["channel"], kept["uploader"], kept["uploader_id"]) == (
        RECORDED_TITLE,
        RECORDED_TITLE,
        RECORDED_HANDLE,
    )


def test_a_recording_keeps_what_the_gateway_reads() -> None:
    """infra: numbers, dates, the kind of answer and the sizes of pictures stay as they were."""
    kept = anonymised(ANSWER, REAL_ID, RECORDED_CHANNEL_ID)

    entry = kept["entries"][0]
    assert kept["_type"] == "playlist"
    assert [picture.get("width") for picture in kept["thumbnails"]] == [900, None]
    assert kept["thumbnails"][1]["id"] == "avatar_uncropped"
    assert (entry["id"], entry["title"]) == (recorded_video_id(1), "Recorded video 1")
    assert (entry["duration"], entry["view_count"], entry["timestamp"]) == (
        754,
        4100000,
        1763078400,
    )
    assert entry["live_status"] is None
    assert [picture["width"] for picture in entry["thumbnails"]] == [360, 720]
    assert all(recorded_video_id(1) in picture["url"] for picture in entry["thumbnails"])


def test_an_answer_of_another_channel_keeps_its_id() -> None:
    """infra: only the ID that was asked to be replaced is replaced."""
    kept = anonymised({"channel_id": "UCother", "uploader_id": None}, REAL_ID, RECORDED_CHANNEL_ID)

    assert kept == {"channel_id": "UCother", "uploader_id": None, "thumbnails": [], "entries": []}


def test_an_error_text_loses_the_real_names() -> None:
    """infra: the text of a recorded error names the stand-ins."""
    text = without_names(
        "ERROR: [youtube:tab] @ARealChannel/videos: failed for UCrealrealrealrealreal00",
        {"@arealchannel": RECORDED_HANDLE, REAL_ID: RECORDED_CHANNEL_ID},
    )

    assert (
        text == f"ERROR: [youtube:tab] {RECORDED_HANDLE}/videos: failed for {RECORDED_CHANNEL_ID}"
    )


def test_the_stored_recordings_are_where_the_tool_writes_them() -> None:
    """infra: the tests read the file that the tool refreshes, and it has every case."""
    assert RECORDINGS_FILE == RECORDINGS_DIR / "recordings.json"
    assert set(recordings()) == {
        "recorded_at",
        "lookup",
        "listing",
        "count",
        "no_videos_tab",
        "channel_without_videos",
        "unknown_handle",
        "unknown_channel_id",
        "unknown_count",
    }
