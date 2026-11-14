"""Records what yt-dlp answers for a real channel, for the tests of the gateway.

The gateway is tested without the network against answers that were recorded
once (docs/TESTING.md section 4). This tool asks the real YouTube exactly as
the gateway does and writes the answers into
``backend/tests/fixtures/ytdlp/``, with every title, name and ID replaced,
so that no real channel is named in the repository.

Run: python -m ytmirror.tools.record_ytdlp <channel handle or ID> <channel without a Videos tab>

It must not be run by the tests or by the app: it needs the real YouTube.

Tests: backend/tests/integration/tools/test_record_ytdlp.py
"""

import itertools
import json
import re
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ytmirror.adapters.ytdlp_gateway import (
    COUNT_OPTIONS,
    LISTING_OPTIONS,
    LOOKUP_OPTIONS,
    UPLOADS_OF_LONG_VIDEOS,
    VIDEOS_TAB,
    extract_with_ytdlp,
)
from ytmirror.core.channel_input import parse_channel_input
from ytmirror.core.channels import CHANNEL_ADDRESS

RECORDINGS_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "ytdlp"
RECORDED_CHANNEL_ID = "UCrecordedchannel0000001"
RECORDED_TITLE = "Recorded Channel"
RECORDED_HANDLE = "@recordedchannel"
EMPTY_CHANNEL_ID = "UCrecordednovideos000002"
UNKNOWN_HANDLE = "@this-handle-does-not-exist-ytm-zz91"
UNKNOWN_CHANNEL_ID = "UCxxxxxxxxxxxxxxxxxxxxxx"
LISTED_VIDEOS = 95
"""How many videos of the listing are kept: a little more than three pages."""

_CHANNEL_KEYS = ("_type", "channel_id", "channel", "uploader", "uploader_id", "playlist_count")
_ENTRY_KEYS = ("_type", "id", "title", "duration", "view_count", "timestamp", "live_status")
_PICTURE_KEYS = ("id", "width", "height", "preference")


def recorded_video_id(number: int) -> str:
    """Return the ID that stands for the video at a place in the listing, from 1."""
    return f"rec{number:08d}"


def anonymised(
    answer: Mapping[str, Any], real_channel_id: str, stand_in_channel_id: str
) -> dict[str, Any]:
    """Return an answer of yt-dlp with every title, name and ID replaced.

    What the gateway reads stays: which fields exist, numbers, dates, the
    sizes of pictures and what kind of answer it is.

    Args:
        answer: The answer of yt-dlp, with its entries already read into a list.
        real_channel_id: The channel ID in the answer.
        stand_in_channel_id: The ID to write instead.

    Returns:
        The answer to store.
    """
    kept: dict[str, Any] = {key: answer[key] for key in _CHANNEL_KEYS if key in answer}
    if kept.get("channel_id") == real_channel_id:
        kept["channel_id"] = stand_in_channel_id
    for key in ("channel", "uploader"):
        if kept.get(key) is not None:
            kept[key] = RECORDED_TITLE
    if kept.get("uploader_id") is not None:
        kept["uploader_id"] = RECORDED_HANDLE
    kept["thumbnails"] = [
        {**_picture(picture), "url": f"https://yt3.googleusercontent.com/recorded-{index}=s0"}
        for index, picture in enumerate(answer.get("thumbnails") or ())
    ]
    kept["entries"] = [
        _entry(entry, number) for number, entry in enumerate(answer.get("entries") or (), start=1)
    ]
    return kept


def without_names(text: str, names: Mapping[str, str]) -> str:
    """Return an error text of yt-dlp with every real name replaced.

    Args:
        text: The error text.
        names: Each real name with what to write instead.
    """
    for real, stand_in in names.items():
        text = re.sub(re.escape(real), stand_in, text, flags=re.IGNORECASE)
    return text


def _picture(picture: Mapping[str, Any]) -> dict[str, Any]:
    return {key: picture[key] for key in _PICTURE_KEYS if key in picture}


def _entry(entry: Mapping[str, Any], number: int) -> dict[str, Any]:
    kept: dict[str, Any] = {key: entry[key] for key in _ENTRY_KEYS if key in entry}
    kept["id"] = recorded_video_id(number)
    kept["title"] = f"Recorded video {number}"
    kept["thumbnails"] = [
        {
            **_picture(picture),
            "url": f"https://i.ytimg.com/vi/{kept['id']}/recorded-{picture.get('width')}.jpg",
        }
        for picture in entry.get("thumbnails") or ()
    ]
    return kept


def _ask(
    address: str, options: Mapping[str, Any], *, process: bool, entries: int
) -> dict[str, Any]:  # pragma: no cover  (the network)
    """Ask yt-dlp and return its answer, or its error, as plain data."""
    try:
        answer = dict(extract_with_ytdlp(address, options, process))
    except Exception as error:  # noqa: BLE001  (every error of yt-dlp is what is recorded)
        return {"error": f"{type(error).__name__}: {error}"}
    answer["entries"] = list(itertools.islice(answer.get("entries") or (), entries))
    return {"answer": answer}


def record(
    channel: str, channel_without_videos: str
) -> dict[str, Any]:  # pragma: no cover  (the network)
    """Ask the real YouTube everything the tests need and return the recordings.

    Args:
        channel: A handle or channel ID of a real channel with at least 100 videos.
        channel_without_videos: The ID of a real channel that has no Videos tab.
    """
    reference = parse_channel_input(channel)
    looked_up = _ask(reference.address + VIDEOS_TAB, LOOKUP_OPTIONS, process=False, entries=0)
    real_id = str(looked_up["answer"]["channel_id"])
    names = {
        real_id: RECORDED_CHANNEL_ID,
        real_id.removeprefix("UC"): RECORDED_CHANNEL_ID.removeprefix("UC"),
        reference.value: RECORDED_HANDLE,
        channel_without_videos: EMPTY_CHANNEL_ID,
    }
    by_id = f"{CHANNEL_ADDRESS}{real_id}"
    asked = {
        "lookup": looked_up,
        "listing": _ask(by_id + VIDEOS_TAB, LISTING_OPTIONS, process=False, entries=LISTED_VIDEOS),
        "count": _ask(
            UPLOADS_OF_LONG_VIDEOS + real_id.removeprefix("UC"),
            COUNT_OPTIONS,
            process=True,
            entries=0,
        ),
        "no_videos_tab": _ask(
            f"{CHANNEL_ADDRESS}{channel_without_videos}{VIDEOS_TAB}",
            LISTING_OPTIONS,
            process=False,
            entries=0,
        ),
        "channel_without_videos": _ask(
            f"{CHANNEL_ADDRESS}{channel_without_videos}", LISTING_OPTIONS, process=False, entries=0
        ),
        "unknown_handle": _ask(
            f"https://www.youtube.com/{UNKNOWN_HANDLE}{VIDEOS_TAB}",
            LOOKUP_OPTIONS,
            process=False,
            entries=0,
        ),
        "unknown_channel_id": _ask(
            f"{CHANNEL_ADDRESS}{UNKNOWN_CHANNEL_ID}{VIDEOS_TAB}",
            LOOKUP_OPTIONS,
            process=False,
            entries=0,
        ),
        "unknown_count": _ask(
            UPLOADS_OF_LONG_VIDEOS + UNKNOWN_CHANNEL_ID.removeprefix("UC"),
            COUNT_OPTIONS,
            process=True,
            entries=0,
        ),
    }
    recordings: dict[str, Any] = {"recorded_at": int(time.time())}
    for name, result in asked.items():
        if "error" in result:
            recordings[name] = {"error": without_names(result["error"], names)}
        else:
            real = str(result["answer"].get("channel_id"))
            recordings[name] = {"answer": anonymised(result["answer"], real, names.get(real, real))}
    return recordings


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover  (the network)
    """Record and write ``recordings.json``. Returns the process exit code."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != len(("channel", "channel without a Videos tab")):
        sys.stderr.write(
            "usage: python -m ytmirror.tools.record_ytdlp"
            " <channel> <channel without a Videos tab>\n"
        )
        return 2
    recordings = record(arguments[0], arguments[1])
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    (RECORDINGS_DIR / "recordings.json").write_text(
        json.dumps(recordings, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    sys.stdout.write(f"Wrote {RECORDINGS_DIR / 'recordings.json'}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
