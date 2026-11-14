"""Plays recorded answers of yt-dlp back to the real gateway, in place of yt-dlp.

The recordings are in ``backend/tests/fixtures/ytdlp/recordings.json`` and
are refreshed with ``python -m ytmirror.tools.record_ytdlp``. Every title,
name and ID in them is a stand-in.
"""

import copy
import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

RECORDINGS_FILE = Path(__file__).resolve().parent / "ytdlp" / "recordings.json"
CHANNEL_ID = "UCrecordedchannel0000001"
HANDLE = "@recordedchannel"
EMPTY_CHANNEL_ID = "UCrecordednovideos000002"
UNKNOWN_HANDLE = "@this-handle-does-not-exist-ytm-zz91"
UNKNOWN_CHANNEL_ID = "UCxxxxxxxxxxxxxxxxxxxxxx"
RECORDED_VIDEOS = 95


class DownloadError(Exception):
    """Stands in for the error class of yt-dlp with the same name."""


def recordings() -> dict[str, Any]:
    """Return a fresh copy of everything that was recorded."""
    return json.loads(RECORDINGS_FILE.read_text(encoding="utf-8"))


class Replay:
    """Answers like yt-dlp did when the recordings were made.

    Attributes:
        asked: Every call: the address, the options and whether to process.
        entries_read: How many entries of the last listing were handed out.
        fail_after: Raise this error text after so many entries of a listing, or None.
    """

    def __init__(self, recorded: Mapping[str, Any] | None = None) -> None:
        """Play back the given recordings, or the stored ones."""
        self.recorded = dict(recorded) if recorded is not None else recordings()
        self.asked: list[tuple[str, Mapping[str, Any], bool]] = []
        self.entries_read = 0
        self.fail_after: tuple[int, str] | None = None

    def __call__(
        self, address: str, options: Mapping[str, Any], process: bool
    ) -> Mapping[str, Any]:
        """Return the recorded answer for an address, or raise the recorded error."""
        self.asked.append((address, options, process))
        recording = self.recorded[self._name_of(address, options)]
        if "error" in recording:
            kind, _, text = str(recording["error"]).partition(": ")
            raise (
                DownloadError(text) if kind == "DownloadError" else RuntimeError(recording["error"])
            )
        answer = copy.deepcopy(recording["answer"])
        answer["entries"] = self._handed_out(answer["entries"])
        return answer

    def _name_of(self, address: str, options: Mapping[str, Any]) -> str:
        if "list=UULF" in address:
            return "count" if CHANNEL_ID.removeprefix("UC") in address else "unknown_count"
        if UNKNOWN_HANDLE in address:
            return "unknown_handle"
        if UNKNOWN_CHANNEL_ID in address:
            return "unknown_channel_id"
        if EMPTY_CHANNEL_ID in address:
            return "no_videos_tab" if address.endswith("/videos") else "channel_without_videos"
        if "extractor_args" in options:
            return "listing"
        return "lookup"

    def _handed_out(self, entries: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        self.entries_read = 0
        for entry in entries:
            if self.fail_after is not None and self.entries_read == self.fail_after[0]:
                raise DownloadError(self.fail_after[1])
            self.entries_read += 1
            yield entry
