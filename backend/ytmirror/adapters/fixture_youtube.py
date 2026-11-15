"""A YouTube that is read from files: the fake of the YouTubeGateway port.

It is part of the app, not of the tests, because the real app can start
with it: ``YTM_FAKE_YOUTUBE=<folder> ./start`` (docs/DECISIONS.md D-062).
The end-to-end tests, the screenshots and the service tests use it, and a
problem can be reproduced with it without the network.

The folder holds one JSON file per channel (docs/TESTING.md section 4). A
channel can have a script of changes: every listing of it serves the next
step, so a test can let a new video appear, a title change, a video vanish
and come back, or a check fail. A channel can answer slowly on request
(``page_delay_ms``, and ``delay_ms`` in a step), so that what the interface
shows while a listing runs can be seen and tested. Pictures are plain
coloured rectangles.

This module must not talk to the network and must not decide anything
about the catalogue.

Tests: backend/tests/integration/test_fixture_youtube.py and
backend/tests/integration/test_youtube_gateway_contract.py
"""

import calendar
import datetime
import json
import struct
import subprocess
import threading
import time
import zlib
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
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
from ytmirror.core.jobs import (
    Chapter,
    DownloadCancelledError,
    DownloadProgress,
    DownloadRequest,
    DownloadResult,
    Stage,
    SubtitleKind,
    SubtitlesFailedError,
)

THUMBNAIL_ADDRESS = "fixture://thumbnail/"
AVATAR_ADDRESS = "fixture://avatar/"
_THUMBNAIL_SIZE = (320, 180)
_AVATAR_SIZE = (96, 96)
_DAY_S = 24 * 60 * 60
_PAGE = 30
"""A slow channel waits once per this many videos, as YouTube answers page by page."""


class FixtureYouTube:
    """Serves channels, listings, counts and pictures from a folder of JSON files."""

    def __init__(
        self,
        folder: Path,
        sleep: Callable[[float], None] = time.sleep,
        ffmpeg: Path | None = None,
    ) -> None:
        """Read every channel file of a folder.

        Args:
            folder: The folder with one ``*.json`` file per channel.
            sleep: Waits a number of seconds, for the channels that answer slowly.
            ffmpeg: The ffmpeg program that writes the video files of downloads.

        Raises:
            ValueError: When a file does not describe a channel.
        """
        self._channels: dict[str, _FixtureChannel] = {}
        for file in sorted(folder.glob("*.json")):
            channel = _FixtureChannel(file.stem, json.loads(file.read_text(encoding="utf-8")))
            self._channels[channel.facts.channel_id] = channel
        self._sleep = sleep
        self._ffmpeg = ffmpeg
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
        videos, failure, fails_after, delay_s = channel.listing(number)
        if delay_s:
            self._sleep(delay_s)
        if failure is not None and fails_after is None:
            raise AppError(failure, {"channel": channel_id})
        return ChannelListing(
            channel.facts,
            self._served(channel_id, videos, failure, fails_after, channel.page_delay_s),
        )

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

    def download(
        self,
        request: DownloadRequest,
        on_progress: Callable[[DownloadProgress], None],
        is_cancelled: Callable[[], bool],
    ) -> DownloadResult:
        """Write a few seconds of real MKV for a fixture video, as yt-dlp would.

        The file has the tags, chapters, subtitles, cover and info JSON of a
        real download (ARCHITECTURE section 7.3), written by the real ffmpeg.
        A fixture video can fail with a code, fail its subtitles, be slow, or
        be a premiere.

        Args:
            request: What to download, and where to.
            on_progress: Told how far the download is.
            is_cancelled: Asked before every step.

        Raises:
            AppError: ``VIDEO_REMOVED`` for an unknown video, the code the
                fixture asks for, or ``TOOL_MISSING`` without ffmpeg.
            DownloadCancelledError: When it was cancelled.
            SubtitlesFailedError: When the fixture fails the subtitles.
        """
        found = [
            (channel, plan)
            for channel in self._channels.values()
            for plan in (channel.download_plan(request.video_id),)
            if plan is not None
        ]
        if not found:
            raise AppError(ErrorCode.VIDEO_REMOVED, {"video": request.video_id})
        channel, plan = found[0]
        request.log_file.parent.mkdir(parents=True, exist_ok=True)
        with request.log_file.open("a", encoding="utf-8") as log:
            log.write(f"info [fixture] Downloading {request.video_id} at {request.quality.value}\n")
        if plan.fails is not None:
            raise AppError(plan.fails, {"message": f"the fixture fails {request.video_id}"})
        subtitles = _chosen_subtitles(plan.subtitles, request)
        # As the real gateway reports it: one share of the whole video, the video
        # stream first (three quarters of the bytes), then the audio stream.
        sizes = {Stage.VIDEO: _VIDEO_BYTES, Stage.AUDIO: _AUDIO_BYTES}
        total = _VIDEO_BYTES + _AUDIO_BYTES
        arrived = 0
        for stage in (Stage.VIDEO, Stage.AUDIO):
            for _ in range(4):
                if is_cancelled():
                    raise DownloadCancelledError(f"cancelled during {stage.value}")
                if plan.step_delay_s:
                    self._sleep(plan.step_delay_s)
                arrived += sizes[stage] // 4
                on_progress(
                    DownloadProgress(
                        stage=stage,
                        fraction=None if plan.size_unknown else arrived / total,
                        speed_bps=1_500_000.0,
                        left_s=None if plan.size_unknown else round((total - arrived) / 1_500_000),
                        height=_HEIGHT if stage is Stage.VIDEO else None,
                        downloaded_bytes=arrived,
                    )
                )
        on_progress(DownloadProgress(stage=Stage.PROCESSING))
        if is_cancelled():
            raise DownloadCancelledError("cancelled before the merge")
        if subtitles is not None and plan.subtitles_fail:
            raise SubtitlesFailedError("the fixture fails the subtitles")
        result = self._write_video(request, channel.facts.title, plan, subtitles)
        if is_cancelled():
            raise DownloadCancelledError("cancelled after the merge")
        return result

    def _write_video(
        self,
        request: DownloadRequest,
        channel_title: str,
        plan: _DownloadPlan,
        subtitles: SubtitleKind | None,
    ) -> DownloadResult:
        if self._ffmpeg is None:
            raise AppError(ErrorCode.TOOL_MISSING, {"tool": "ffmpeg"})
        work = request.work_folder
        work.mkdir(parents=True, exist_ok=True)
        published = plan.release_time if plan.release_time is not None else plan.upload_time
        address = f"https://www.youtube.com/watch?v={request.video_id}"
        info: dict[str, Any] = {
            "id": request.video_id,
            "title": plan.title,
            "description": plan.description,
            "duration": plan.length_s,
            "timestamp": plan.upload_time,
            "release_timestamp": plan.release_time,
            "channel": channel_title,
            "webpage_url": address,
            "chapters": [
                {"start_time": chapter.start_s, "title": chapter.title} for chapter in plan.chapters
            ],
        }
        info_json = json.dumps(info, ensure_ascii=False)
        (work / "info.json").write_text(info_json, encoding="utf-8")
        cover = work / f"{request.video_id}.jpg"
        tags = {
            "title": plan.title,
            "ARTIST": channel_title,
            "DESCRIPTION": plan.description,
            "DATE": time.strftime("%Y%m%d", time.gmtime(published)),
            "PURL": address,
            "COMMENT": address,
            "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(published)),
            "video_id": request.video_id,
        }
        metadata = work / "metadata.txt"
        metadata.write_text(_ffmetadata(tags, plan.chapters, plan.length_s), encoding="utf-8")
        self._ffmpeg_run(
            [
                "-f",
                "lavfi",
                "-i",
                f"testsrc2=size=320x{_HEIGHT}:rate=25:duration=1",
                "-frames:v",
                "1",
                str(cover),
            ]
        )
        inputs = [
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size=480x{_HEIGHT}:rate=25:duration={plan.length_s}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={plan.length_s}",
            "-i",
            str(metadata),
        ]
        maps = ["-map", "0:v", "-map", "1:a", "-map_metadata", "2", "-map_chapters", "2"]
        if subtitles is not None:
            track = work / "en.srt"
            track.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
            inputs += ["-i", str(track)]
            title = "English" if subtitles is SubtitleKind.MANUAL else "English (auto-generated)"
            maps += [
                "-map",
                "3:s",
                "-c:s",
                "srt",
                "-metadata:s:s:0",
                "language=eng",
                "-metadata:s:s:0",
                f"title={title}",
            ]
        self._ffmpeg_run(
            [
                *inputs,
                *maps,
                "-c:v",
                "mpeg4",
                "-c:a",
                "aac",
                "-attach",
                str(work / "info.json"),
                "-metadata:s:t:0",
                "mimetype=application/json",
                "-metadata:s:t:0",
                "filename=info.json",
                "-attach",
                str(cover),
                "-metadata:s:t:1",
                "mimetype=image/jpeg",
                "-metadata:s:t:1",
                "filename=cover.jpg",
                str(work / f"{request.video_id}.mkv"),
            ]
        )
        return DownloadResult(
            file=work / f"{request.video_id}.mkv",
            thumbnail=cover,
            info_json=info_json,
            title=plan.title,
            description=plan.description,
            duration_s=plan.length_s,
            release_time=plan.release_time,
            upload_time=plan.upload_time,
            subtitles=subtitles,
            chapters=plan.chapters,
        )

    def _ffmpeg_run(self, arguments: list[str]) -> None:
        command = [str(self._ffmpeg), "-hide_banner", "-loglevel", "error", "-y", *arguments]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise AppError(ErrorCode.FFMPEG_FAILED, {"message": result.stderr.strip()[-500:]})

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
        page_delay_s: float,
    ) -> Iterator[ListedVideo]:
        for index, video in enumerate(videos):
            if failure is not None and index == fails_after:
                raise AppError(failure, {"channel": channel_id})
            if page_delay_s and index % _PAGE == 0:
                self._sleep(page_delay_s)
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
            self._download_defaults: Mapping[str, Any] = dict(data.get("download", {}))
            self._entries: dict[str, Mapping[str, Any]] = {
                str(entry["id"]): entry for entry in data.get("videos", [])
            }
            self._steps: list[Mapping[str, Any]] = list(data.get("checks", []))
            self.page_delay_s = float(data.get("page_delay_ms", 0)) / 1000
            self._listing_failures = {
                int(number): ErrorCode(code)
                for number, code in dict(data.get("listing_failures", {})).items()
            }
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

    def listing(self, number: int) -> tuple[list[ListedVideo], ErrorCode | None, int | None, float]:
        """Return what listing number ``number`` (from 0) serves.

        Returns:
            The videos, the failure of this listing if it has one, after how many
            videos it fails (None: before the first), and the seconds it waits
            before it answers.
        """
        videos = list(self._videos)
        removed: dict[str, tuple[int, ListedVideo]] = {}
        failure: ErrorCode | None = self._listing_failures.get(number)
        fails_after: int | None = None
        delay_s = 0.0
        for index, step in enumerate(self._steps[:number]):
            if index == number - 1:
                delay_s = float(step.get("delay_ms", 0)) / 1000
            if "fail" in step:
                if index == number - 1:
                    failure = ErrorCode(step["fail"])
                    fails_after = step.get("fail_after")
                continue
            self._apply(step, videos, removed)
        return videos, failure, fails_after, delay_s

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

    def download_plan(self, video_id: str) -> _DownloadPlan | None:
        """Return how a download of a video of this channel goes, or None for another video."""
        video = next((video for video in self._videos if video.id == video_id), None)
        if video is None:
            return None
        entry = {**self._download_defaults, **self._entries.get(video_id, {})}
        upload = entry.get("published_at")
        release = entry.get("release_at")
        fails = entry.get("download_fails")
        return _DownloadPlan(
            title=video.title,
            description=str(entry.get("description", f"The description of {video.title}.")),
            upload_time=_seconds(str(upload))
            if upload
            else (video.published_at or self._listed_at),
            release_time=_seconds(str(release)) if release else None,
            length_s=int(entry.get("length_s", 2)),
            subtitles=str(entry.get("subtitles", "manual")),
            subtitles_fail=bool(entry.get("subtitles_fail", False)),
            fails=ErrorCode(fails) if fails else None,
            step_delay_s=float(entry.get("step_delay_ms", 0)) / 1000,
            size_unknown=bool(entry.get("size_unknown", False)),
            chapters=tuple(
                Chapter(start_s=float(start), title=str(title))
                for start, title in entry.get("chapters", [[0, "Start"], [1, "The middle"]])
            ),
        )

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


_HEIGHT = 270
"""The height of every fake video file."""

_VIDEO_BYTES = 6_000_000
_AUDIO_BYTES = 2_000_000
"""The sizes the fake reports for the two streams of a video."""


@dataclass(frozen=True, slots=True)
class _DownloadPlan:
    """How the download of one fixture video goes."""

    title: str
    description: str
    upload_time: int
    release_time: int | None
    length_s: int
    subtitles: str
    subtitles_fail: bool
    fails: ErrorCode | None
    step_delay_s: float
    size_unknown: bool
    chapters: tuple[Chapter, ...]


def _chosen_subtitles(available: str, request: DownloadRequest) -> SubtitleKind | None:
    """Choose subtitles like the real gateway: the creator's, else the automatic ones."""
    if available == "manual" and request.manual_subtitles:
        return SubtitleKind.MANUAL
    if available == "auto" and request.manual_subtitles and request.auto_subtitles:
        return SubtitleKind.AUTO
    return None


def _ffmetadata(tags: Mapping[str, str], chapters: tuple[Chapter, ...], length_s: int) -> str:
    """Return the tags and chapters of a file in the metadata format of ffmpeg."""

    def escaped(text: str) -> str:
        for special in ("\\", "=", ";", "#", "\n"):
            text = text.replace(special, "\\" + special)
        return text

    lines = [";FFMETADATA1", *(f"{name}={escaped(value)}" for name, value in tags.items())]
    ends = [chapter.start_s for chapter in chapters[1:]] + [float(length_s)]
    for chapter, end in zip(chapters, ends, strict=True):
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={int(chapter.start_s * 1000)}",
            f"END={int(end * 1000)}",
            f"title={escaped(chapter.title)}",
        ]
    return "\n".join(lines) + "\n"


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
