"""A YouTube that is read from files: the fake of the YouTubeGateway port.

It is part of the app, not of the tests, because the real app can start
with it: ``YTM_FAKE_YOUTUBE=<folder> ./start`` (docs/DECISIONS.md D-062).
The end-to-end tests, the screenshots and the service tests use it, and a
problem can be reproduced with it without the network.

The folder holds one JSON file per channel (docs/TESTING.md section 4). A
channel can have a script of changes: every listing of it serves the next
step, so a test can let a new video appear, a title change, a video vanish
and come back, or a check fail. Pictures are plain coloured rectangles.

This module must not talk to the network and must not decide anything
about the catalogue.

Tests: backend/tests/integration/test_fixture_youtube.py and
backend/tests/integration/test_youtube_gateway_contract.py
"""

import calendar
import datetime
import json
import struct
import threading
import zlib
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from ytmirror.core.channels import (
    ChannelFacts,
    ChannelListing,
    ChannelReference,
    ListedVideo,
    ReferenceKind,
)
from ytmirror.core.errors import AppError, ErrorCode

THUMBNAIL_ADDRESS = "fixture://thumbnail/"
AVATAR_ADDRESS = "fixture://avatar/"
_THUMBNAIL_SIZE = (320, 180)
_AVATAR_SIZE = (96, 96)
_DAY_S = 24 * 60 * 60


class FixtureYouTube:
    """Serves channels, listings, counts and pictures from a folder of JSON files."""

    def __init__(self, folder: Path) -> None:
        """Read every channel file of a folder.

        Args:
            folder: The folder with one ``*.json`` file per channel.

        Raises:
            ValueError: When a file does not describe a channel.
        """
        self._channels: dict[str, _FixtureChannel] = {}
        for file in sorted(folder.glob("*.json")):
            channel = _FixtureChannel(file.stem, json.loads(file.read_text(encoding="utf-8")))
            self._channels[channel.facts.channel_id] = channel
        self._lock = threading.Lock()
        self.listings_started: dict[str, int] = {}
        """How many listings of each channel were started, by channel ID."""
        self.videos_served: dict[str, int] = {}
        """How many videos the last listing of each channel handed out, by channel ID."""

    def lookup_channel(self, reference: ChannelReference) -> ChannelFacts:
        """Return the channel that a reference names.

        Args:
            reference: The channel as the user named it.

        Raises:
            AppError: ``CHANNEL_NOT_FOUND`` for an unknown channel, or the code a
                fixture asks for.
        """
        for channel in self._channels.values():
            if channel.is_named_by(reference):
                if channel.lookup_fails is not None:
                    raise AppError(channel.lookup_fails, {"channel": reference.value})
                return channel.facts
        raise AppError(ErrorCode.CHANNEL_NOT_FOUND, {"channel": reference.value})

    def list_channel(self, channel_id: str) -> ChannelListing:
        """Start the next listing of a channel. Every listing serves the next step of its script.

        Args:
            channel_id: The channel ID.

        Raises:
            AppError: ``CHANNEL_NOT_FOUND`` for an unknown channel, or the code the
                step of the script asks for.
        """
        channel = self._known(channel_id)
        with self._lock:
            number = self.listings_started.get(channel_id, 0)
            self.listings_started[channel_id] = number + 1
            self.videos_served[channel_id] = 0
        videos, failure, fails_after = channel.listing(number)
        if failure is not None and fails_after is None:
            raise AppError(failure, {"channel": channel_id})
        return ChannelListing(channel.facts, self._served(channel_id, videos, failure, fails_after))

    def preview_video_count(self, channel_id: str) -> int:
        """Return the video count a fixture gives for its preview.

        Args:
            channel_id: The channel ID.

        Raises:
            AppError: The code the fixture asks for, or ``CHANNEL_NOT_FOUND``.
        """
        channel = self._known(channel_id)
        if isinstance(channel.video_count, ErrorCode):
            raise AppError(channel.video_count, {"channel": channel_id})
        return channel.video_count

    def fetch_image(self, url: str) -> bytes:
        """Return a coloured rectangle as PNG for a thumbnail or avatar address of a fixture.

        Args:
            url: An address that a fixture lookup or listing gave.

        Raises:
            AppError: ``NETWORK_UNREACHABLE`` for any other address, and for a
                channel whose pictures are set to fail.
        """
        for prefix, size in ((THUMBNAIL_ADDRESS, _THUMBNAIL_SIZE), (AVATAR_ADDRESS, _AVATAR_SIZE)):
            if url.startswith(prefix):
                name = url.removeprefix(prefix)
                if any(name in channel.unreachable_pictures for channel in self._channels.values()):
                    break
                return _png(*size, _colour_of(name))
        raise AppError(ErrorCode.NETWORK_UNREACHABLE, {"url": url})

    def _known(self, channel_id: str) -> _FixtureChannel:
        channel = self._channels.get(channel_id)
        if channel is None:
            raise AppError(ErrorCode.CHANNEL_NOT_FOUND, {"channel": channel_id})
        return channel

    def _served(
        self,
        channel_id: str,
        videos: list[ListedVideo],
        failure: ErrorCode | None,
        fails_after: int | None,
    ) -> Iterator[ListedVideo]:
        for index, video in enumerate(videos):
            if failure is not None and index == fails_after:
                raise AppError(failure, {"channel": channel_id})
            with self._lock:
                self.videos_served[channel_id] += 1
            yield video
        if failure is not None:
            raise AppError(failure, {"channel": channel_id})


class _FixtureChannel:
    """One channel file: its facts, its videos and its script of changes."""

    def __init__(self, name: str, data: Mapping[str, Any]) -> None:
        try:
            self.facts = ChannelFacts(
                channel_id=str(data["id"]),
                title=str(data["title"]),
                handle=data.get("handle"),
                avatar_url=f"{AVATAR_ADDRESS}{data['id']}",
            )
            self._custom_name: str | None = data.get("custom_name")
            self._user_name: str | None = data.get("user_name")
            self._listed_at = _seconds(str(data["listed_at"]))
            count = data["video_count"]
            self.video_count: int | ErrorCode = (
                ErrorCode(count["fail"]) if isinstance(count, dict) else int(count)
            )
            self.lookup_fails = ErrorCode(data["lookup_fails"]) if "lookup_fails" in data else None
            self._videos = [self._video(entry) for entry in data.get("videos", [])]
            self._videos += self._generated(data.get("generate"))
            self._steps: list[Mapping[str, Any]] = list(data.get("checks", []))
            self.unreachable_pictures = frozenset(
                [self.facts.channel_id, *(video.id for video in self._videos)]
                if data.get("pictures_fail")
                else []
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"The fixture channel {name!r} is not valid: {error!r}") from error

    def is_named_by(self, reference: ChannelReference) -> bool:
        """Return whether a reference of the user names this channel."""
        names = {
            ReferenceKind.CHANNEL_ID: self.facts.channel_id,
            ReferenceKind.HANDLE: self.facts.handle,
            ReferenceKind.CUSTOM_NAME: self._custom_name,
            ReferenceKind.USER_NAME: self._user_name,
        }
        name = names[reference.kind]
        return name is not None and name.casefold() == reference.value.casefold()

    def listing(self, number: int) -> tuple[list[ListedVideo], ErrorCode | None, int | None]:
        """Return what listing number ``number`` (from 0) serves.

        Returns:
            The videos, the failure of this listing if its step has one, and after
            how many videos it fails (None: before the first).
        """
        videos = list(self._videos)
        removed: dict[str, tuple[int, ListedVideo]] = {}
        failure: ErrorCode | None = None
        fails_after: int | None = None
        for index, step in enumerate(self._steps[:number]):
            if "fail" in step:
                if index == number - 1:
                    failure = ErrorCode(step["fail"])
                    fails_after = step.get("fail_after")
                continue
            self._apply(step, videos, removed)
        return videos, failure, fails_after

    def _apply(
        self,
        step: Mapping[str, Any],
        videos: list[ListedVideo],
        removed: dict[str, tuple[int, ListedVideo]],
    ) -> None:
        ids = [video.id for video in videos]
        for video_id in step.get("remove", []):
            place = ids.index(video_id)
            removed[video_id] = (place, videos.pop(place))
            ids.pop(place)
        for video_id in step.get("restore", []):
            place, video = removed.pop(video_id)
            videos.insert(min(place, len(videos)), video)
        for video_id, title in step.get("retitle", {}).items():
            place = [video.id for video in videos].index(video_id)
            old = videos[place]
            videos[place] = ListedVideo(
                old.id,
                title,
                old.duration_s,
                old.view_count,
                old.published_at,
                old.listed_at,
                old.thumbnail_url,
            )
        for entry in step.get("add", []):
            before = entry.get("before")
            place = [video.id for video in videos].index(before) if before else 0
            videos.insert(place, self._video(entry))

    def _video(self, entry: Mapping[str, Any]) -> ListedVideo:
        point = entry.get("point")
        return ListedVideo(
            id=str(entry["id"]),
            title=str(entry["title"]),
            duration_s=entry.get("duration_s"),
            view_count=entry.get("view_count"),
            published_at=None if point is None else _seconds(str(point)),
            listed_at=self._listed_at,
            thumbnail_url=f"{THUMBNAIL_ADDRESS}{entry['id']}",
        )

    def _generated(self, plan: Mapping[str, Any] | None) -> list[ListedVideo]:
        """Return many videos from a short description, one day apart, newest first."""
        if plan is None:
            return []
        midnight = (self._listed_at // _DAY_S) * _DAY_S
        prefix, count = str(plan["id_prefix"]), int(plan["count"])
        videos: list[ListedVideo] = []
        for number in range(count, 0, -1):
            video_id = f"{prefix}{number:0{11 - len(prefix)}d}"
            videos.append(
                ListedVideo(
                    id=video_id,
                    title=str(plan["title"]).format(number=number),
                    duration_s=60 + (number * 37) % 3600,
                    view_count=(number * 7919) % 2_000_000,
                    published_at=midnight - (count - number + 1) * _DAY_S,
                    listed_at=self._listed_at,
                    thumbnail_url=f"{THUMBNAIL_ADDRESS}{video_id}",
                )
            )
        return videos


def _seconds(text: str) -> int:
    """Read ``2026-11-14`` or ``2026-11-14T06:42:00Z`` as seconds since the epoch, in UTC."""
    moment = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=datetime.UTC)
    return calendar.timegm(moment.utctimetuple())


def _colour_of(name: str) -> tuple[int, int, int]:
    """Return a muted colour that is always the same for a name."""
    seed = zlib.crc32(name.encode("utf-8"))
    return 60 + seed % 90, 60 + (seed >> 8) % 90, 70 + (seed >> 16) % 90


def _png(width: int, height: int, colour: tuple[int, int, int]) -> bytes:
    """Return a PNG picture of one colour."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    row = b"\x00" + bytes(colour) * width
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(row * height, 9))
        + chunk(b"IEND", b"")
    )
