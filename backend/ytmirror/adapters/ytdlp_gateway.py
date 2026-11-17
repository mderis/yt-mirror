"""The YouTubeGateway port on the real YouTube, through yt-dlp as a library.

From milestone M2: channel lookup, the listing of a channel's Videos tab,
the optional video count of a preview, and pictures. The options were
checked against the pinned yt-dlp and the real YouTube in that milestone
(docs/ARCHITECTURE.md section 7.3, docs/DECISIONS.md D-069).

Every error text of yt-dlp is turned into an error code here. This module
must not decide anything about the catalogue, and it must not set a proxy:
yt-dlp and the HTTP client honour the proxy settings of the environment by
themselves (R-PL-08).

Tests: backend/tests/integration/test_ytdlp_gateway.py,
backend/tests/integration/test_youtube_gateway_contract.py,
backend/tests/integration/test_ytdlp_download.py and, with the real yt-dlp
against a server on this Mac, backend/tests/integration/test_ytdlp_real_download.py.
The calls that reach YouTube are tested by backend/tests/live/.
"""

import copy
import datetime
import importlib
import json
import logging
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

import httpx2

from ytmirror.core.channels import (
    CHANNEL_ADDRESS,
    ChannelFacts,
    ChannelListing,
    ChannelReference,
    ListedVideo,
)
from ytmirror.core.dates import published_time
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
from ytmirror.core.progress import PartKind, PlannedPart, ProgressTracker, stream_size
from ytmirror.core.quality import format_selector
from ytmirror.ports.clock import Clock

type Extract = Callable[[str, Mapping[str, Any], bool], Mapping[str, Any]]
"""Asks yt-dlp about an address: the address, the options, and whether yt-dlp
should also process the answer. Returns the answer of yt-dlp. With processing
off, the entries of a listing are fetched page by page while they are read."""

type HttpGet = Callable[[str], bytes]
"""Fetches the bytes behind an address, or raises ``AppError``."""

type Download = Callable[
    [Mapping[str, Any], Mapping[str, Any], Mapping[str, str]], Mapping[str, Any]
]
"""Downloads a video with yt-dlp from the metadata the lookup before it gave, with the
options and tags to add to the file: YouTube is not asked a second time (D-088).
Returns the processed answer of yt-dlp, ready to be written as JSON."""

VIDEOS_TAB = "/videos"
UPLOADS_OF_LONG_VIDEOS = "https://www.youtube.com/playlist?list=UULF"
"""The playlist of a channel's long videos: this prefix, then the channel ID without
its ``UC``. A convention of YouTube that is documented nowhere (docs/DECISIONS.md D-061)."""

_COMMON_OPTIONS: Mapping[str, Any] = {
    "quiet": True,
    "no_warnings": True,
    "noprogress": True,
    "skip_download": True,
    "extract_flat": "in_playlist",
    # Nothing is written outside the app folder (docs/SPEC.md section 1.2, principle 5).
    "cachedir": False,
}
LOOKUP_OPTIONS: Mapping[str, Any] = {
    **_COMMON_OPTIONS,
    "socket_timeout": 10,
    "extractor_retries": 0,
}
LISTING_OPTIONS: Mapping[str, Any] = {
    **_COMMON_OPTIONS,
    "socket_timeout": 20,
    "extractor_retries": 2,
    "extractor_args": {
        # Without it a listing has no dates at all (R-DT-04).
        "youtubetab": {"approximate_date": ["true"]},
        # Without it yt-dlp ends a cut-off listing as if it were complete (R-CH-13).
        "youtube": {"raise_incomplete_data": ["true"]},
    },
}
COUNT_OPTIONS: Mapping[str, Any] = {
    **_COMMON_OPTIONS,
    "socket_timeout": 8,
    "extractor_retries": 0,
    "playlist_items": "0",
}
_NO_VIDEOS_TAB = "does not have a videos tab"
METADATA_OPTIONS: Mapping[str, Any] = {
    **_COMMON_OPTIONS,
    "extract_flat": False,
    "socket_timeout": 20,
    "extractor_retries": 2,
}
"""The full metadata of one video, read before its download (ARCHITECTURE section 7.3)."""

EXACT_DATE_OPTIONS: Mapping[str, Any] = {
    "quiet": True,
    "no_warnings": True,
    "noprogress": True,
    "skip_download": True,
    "cachedir": False,
    "socket_timeout": 20,
    "extractor_retries": 0,
    "check_formats": False,
    "extractor_args": {
        "youtube": {
            "player_client": ["web"],
            "player_skip": ["configs", "js"],
            "skip": ["hls", "dash", "translated_subs"],
        }
    },
}
"""The lightest lookup that still gives the exact time of a video, read without
processing (ARCHITECTURE section 7.4, measured in M2 and M4)."""

DOWNLOAD_OPTIONS: Mapping[str, Any] = {
    "quiet": True,
    "noprogress": True,
    "cachedir": False,
    "socket_timeout": 20,
    "retries": 3,
    "fragment_retries": 3,
    "extractor_retries": 2,
    "merge_output_format": "mkv",
    "writethumbnail": True,
    "overwrites": True,
    "postprocessors": [
        {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"},
        {"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False},
        {
            "key": "FFmpegMetadata",
            "add_chapters": True,
            "add_metadata": True,
            "add_infojson": True,
        },
        {"key": "EmbedThumbnail", "already_have_thumbnail": True},
    ],
}
"""The download of one video, verified in milestone M3 (Q-04, ARCHITECTURE section 7.3).
The thumbnail is kept as JPEG next to the file, for the hidden folder (R-MD-05)."""

TAGS_STEP = "_AddTags"
"""The step that adds the tags of the app (``download_with_ytdlp``). It runs before the
download, and yt-dlp calls the post-processor hook for it too: it is not processing."""

_SUBTITLE_STEP = "EmbedSubtitle"
_SUBTITLE_FAILURE = "unable to download video subtitles"

_NOT_REGULAR = frozenset({"is_live", "was_live"})
_IMAGE_HOSTS = ("ytimg.com", "ggpht.com", "googleusercontent.com")
_IMAGE_TIMEOUT_S = 15.0
_MAX_IMAGE_BYTES = 5_000_000
_TOO_MANY_REQUESTS = 429

# The first text that is found in an error of yt-dlp decides its code.
_CODES: tuple[tuple[ErrorCode, tuple[str, ...]], ...] = (
    # YouTube writes the apostrophe as U+2019. Both spellings are looked for.
    (ErrorCode.BOT_CHECK, ("confirm you\u2019re not a bot", "confirm you're not a bot")),
    (ErrorCode.RATE_LIMITED, ("http error 429", "too many requests", "rate-limit", "rate limit")),
    (
        ErrorCode.CHANNEL_NOT_FOUND,
        (
            "this channel does not exist",
            "http error 404",
            "this account has been terminated",
            "this channel is not available",
        ),
    ),
    (
        ErrorCode.NETWORK_UNREACHABLE,
        (
            "timed out",
            "transporterror",
            "name resolution",
            "nodename nor servname",
            "getaddrinfo",
            "connection reset",
            "connection refused",
            "connection aborted",
            "network is unreachable",
            "unable to connect",
            "remote end closed",
            "incomplete data received",
            "http error 5",
            "ssl",
            "proxy",
        ),
    ),
)


# Errors about one video, looked for before the others when a video is downloaded.
_VIDEO_CODES: tuple[tuple[ErrorCode, tuple[str, ...]], ...] = (
    (ErrorCode.BOT_CHECK, ("confirm you\u2019re not a bot", "confirm you're not a bot")),
    (ErrorCode.MEMBERS_ONLY, ("members-only", "members only", "join this channel")),
    (ErrorCode.AGE_RESTRICTED, ("confirm your age", "age-restricted", "age restricted")),
    (ErrorCode.VIDEO_PRIVATE, ("private video", "video is private")),
    (
        ErrorCode.GEO_BLOCKED,
        ("available in your country", "blocked it in your country", "geo restrict"),
    ),
    (
        ErrorCode.NOT_YET_AVAILABLE,
        ("premieres in", "premiere will begin", "live event will begin", "is upcoming"),
    ),
    (
        ErrorCode.VIDEO_REMOVED,
        (
            "video unavailable",
            "has been removed",
            "no longer available",
            "account associated with this video has been terminated",
            "http error 404",
        ),
    ),
    (
        ErrorCode.NO_FORMATS,
        ("requested format is not available", "no video formats found"),
    ),
    (ErrorCode.DISK_FULL, ("no space left on device",)),
    (ErrorCode.FFMPEG_FAILED, ("postprocessing:", "ffmpeg", "conversion failed")),
)


def code_of(error_text: str, *, video: bool = False) -> ErrorCode:
    """Return the error code for an error text of yt-dlp.

    A text that is not known becomes ``YOUTUBE_CHANGED``: most likely YouTube
    changed something that yt-dlp does not know yet (docs/DECISIONS.md D-069).

    Args:
        error_text: The text of the error.
        video: Whether the error is about one video: then the errors of a
            video come first, and "not found" means the video is gone.
    """
    text = error_text.lower()
    for code, signs in (*_VIDEO_CODES, *_CODES) if video else _CODES:
        if any(sign in text for sign in signs):
            return code
    return ErrorCode.YOUTUBE_CHANGED


class YtDlpGateway:
    """Asks the real YouTube through yt-dlp."""

    def __init__(
        self,
        clock: Clock,
        *,
        tools: GatewayTools | None = None,
        extract: Extract | None = None,
        http_get: HttpGet | None = None,
        download: Download | None = None,
    ) -> None:
        """Create the gateway.

        Args:
            clock: Says when a listed video was read.
            tools: Where ffmpeg and Deno are, given to yt-dlp (ARCHITECTURE section 7.3).
            extract: A stand-in for yt-dlp. For tests.
            http_get: A stand-in for the HTTP client. For tests.
            download: A stand-in for a download with yt-dlp. For tests.
        """
        self._clock = clock
        self._tools = tools
        self._extract = extract if extract is not None else extract_with_ytdlp
        self._http_get = http_get if http_get is not None else _get_with_httpx
        self._download = download if download is not None else download_with_ytdlp

    def download(
        self,
        request: DownloadRequest,
        on_progress: Callable[[DownloadProgress], None],
        is_cancelled: Callable[[], bool],
        *,
        start_writing: Callable[[], None] = lambda: None,
    ) -> DownloadResult:
        """Download one video into the temp folder of its job (ARCHITECTURE section 7.3).

        The full metadata is read first, to choose the subtitles (R-MD-03).
        Then yt-dlp downloads the streams, merges them into MKV and embeds the
        subtitles, the metadata with chapters, the info JSON and the cover.

        Args:
            request: What to download, and where to.
            on_progress: Told how far the download is.
            is_cancelled: Asked while the download runs. When it says yes, the
                download ends with ``DownloadCancelledError`` at the next step.
            start_writing: Called after the metadata lookup, which only reads,
                and before yt-dlp writes anything (R-QU-02).

        Raises:
            AppError: With the code of what went wrong.
            DownloadCancelledError: When it was cancelled.
            SubtitlesFailedError: When only the subtitles failed (R-MD-04).
        """
        address = f"https://www.youtube.com/watch?v={request.video_id}"
        # The same format choice as the download: yt-dlp then names the streams it
        # will fetch, with their sizes, for one progress of the whole Mirror (D-088).
        info = self._ask_about_video(
            address,
            {**METADATA_OPTIONS, **self._runtime(), "format": format_selector(request.quality)},
        )
        if info.get("live_status") == "is_upcoming":
            raise AppError(
                ErrorCode.NOT_YET_AVAILABLE,
                {"message": "The video is not public yet", "video": request.video_id},
            )
        subtitles, languages = _subtitles_for(info, request)
        steps = _Steps(
            on_progress,
            is_cancelled,
            ProgressTracker(planned_parts(info, subtitles is not None)),
        )
        options: dict[str, Any] = {
            **DOWNLOAD_OPTIONS,
            **self._runtime(),
            "format": format_selector(request.quality),
            "outtmpl": {"default": str(request.work_folder / "%(id)s.%(ext)s")},
            "writesubtitles": subtitles is SubtitleKind.MANUAL,
            "writeautomaticsub": subtitles is SubtitleKind.AUTO,
            "subtitleslangs": languages,
            "progress_hooks": [steps.downloading],
            "postprocessor_hooks": [steps.processing],
            "logger": _JobLog(request.log_file),
        }
        if subtitles is None:
            options["postprocessors"] = [
                step
                for step in DOWNLOAD_OPTIONS["postprocessors"]
                if step["key"] != "FFmpegEmbedSubtitle"
            ]
        published = published_time(_int(info.get("release_timestamp")), _int(info.get("timestamp")))
        tags = {"video_id": request.video_id}
        if published is not None:
            tags["published_at"] = _iso(published)
        # Until here only YouTube was asked; from here yt-dlp writes into the temp folder.
        start_writing()
        try:
            answer = self._download(info, options, tags)
        except DownloadCancelledError:
            raise
        except Exception as error:
            # Asked first: when the job was cancelled or the app quits, its ffmpeg was
            # stopped, and what yt-dlp raises then is the cancel (R-QU-02, R-PL-13).
            if is_cancelled():
                raise DownloadCancelledError("cancelled: the tools were stopped") from error
            if isinstance(error, AppError):
                raise
            text = f"{type(error).__name__}: {error}"
            if steps.current == _SUBTITLE_STEP or _SUBTITLE_FAILURE in text.lower():
                raise SubtitlesFailedError(text) from error
            raise AppError(code_of(text, video=True), {"message": str(error)}) from error
        file = request.work_folder / f"{request.video_id}.mkv"
        if not file.is_file():
            raise AppError(
                ErrorCode.FFMPEG_FAILED,
                {"message": "yt-dlp ended without an MKV file", "video": request.video_id},
            )
        thumbnail = request.work_folder / f"{request.video_id}.jpg"
        return DownloadResult(
            file=file,
            thumbnail=thumbnail if thumbnail.is_file() else None,
            info_json=_json_text(answer),
            title=str(answer.get("title") or info.get("title") or ""),
            description=str(answer.get("description") or info.get("description") or ""),
            duration_s=_int(answer.get("duration") or info.get("duration")),
            release_time=_int(info.get("release_timestamp")),
            upload_time=_int(info.get("timestamp")),
            subtitles=subtitles,
            chapters=tuple(
                Chapter(
                    start_s=float(chapter.get("start_time") or 0),
                    title=str(chapter.get("title") or ""),
                )
                for chapter in info.get("chapters") or ()
            ),
        )

    def exact_date(self, video_id: str) -> int | None:
        """Return the exact published time of one video, with the lightest lookup (R-DT-05).

        Args:
            video_id: The video ID.

        Returns:
            The release time, else the upload time (R-DT-03), or None for a
            video that has not been released yet.

        Raises:
            AppError: With the code of what went wrong.
        """
        address = f"https://www.youtube.com/watch?v={video_id}"
        info = self._ask_about_video(address, EXACT_DATE_OPTIONS, process=False)
        if info.get("live_status") == "is_upcoming":
            # Its release time is only the time it is scheduled for.
            return None
        return published_time(_int(info.get("release_timestamp")), _int(info.get("timestamp")))

    def _runtime(self) -> dict[str, Any]:
        """Return the options that point yt-dlp at the tools of the app folder."""
        if self._tools is None:
            return {}
        return {
            "ffmpeg_location": str(self._tools.ffmpeg_folder),
            "js_runtimes": {"deno": {"path": str(self._tools.deno)}},
        }

    def _ask_about_video(
        self, address: str, options: Mapping[str, Any], *, process: bool = True
    ) -> Mapping[str, Any]:
        try:
            return self._extract(address, options, process)
        except AppError as error:
            raise AppError(
                code_of(error.details.get("message", ""), video=True), error.details
            ) from error
        except Exception as error:
            raise AppError(
                code_of(f"{type(error).__name__}: {error}", video=True), {"message": str(error)}
            ) from error

    def lookup_channel(self, reference: ChannelReference) -> ChannelFacts:
        """Return what YouTube says about a channel, without reading its videos (R-CH-03).

        Args:
            reference: The channel as the user named it.

        Raises:
            AppError: ``CHANNEL_NOT_FOUND``, or the code of a request that failed.
        """
        return _facts_of(self._channel_page(reference.address, LOOKUP_OPTIONS), reference.value)

    def list_channel(self, channel_id: str) -> ChannelListing:
        """Start a listing of the regular videos of a channel, newest first (R-CH-12).

        Args:
            channel_id: The channel ID.

        Raises:
            AppError: Here or while the videos are read.
        """
        answer = self._channel_page(f"{CHANNEL_ADDRESS}{channel_id}", LISTING_OPTIONS)
        return ChannelListing(_facts_of(answer, channel_id), self._videos(answer))

    def preview_video_count(self, channel_id: str) -> int:
        """Return how many long videos YouTube says a channel has (R-CH-03, D-061).

        Args:
            channel_id: The channel ID.

        Raises:
            AppError: When the playlist of the channel's long videos gives no number.
        """
        address = f"{UPLOADS_OF_LONG_VIDEOS}{channel_id.removeprefix('UC')}"
        answer = self._ask(address, COUNT_OPTIONS, process=True)
        count = answer.get("playlist_count")
        if (
            answer.get("channel_id") != channel_id
            or isinstance(count, bool)
            or not isinstance(count, int)
        ):
            raise AppError(
                ErrorCode.YOUTUBE_CHANGED, {"message": "The playlist gave no video count"}
            )
        return count

    def fetch_image(self, url: str) -> bytes:
        """Return the bytes of a thumbnail or an avatar (R-CH-16).

        Only addresses of YouTube's picture servers are fetched (R-HE-03).

        Args:
            url: The address a lookup or a listing gave.

        Raises:
            AppError: When the address is not a picture of YouTube or cannot be fetched.
        """
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.scheme != "https" or not any(
            host == allowed or host.endswith(f".{allowed}") for allowed in _IMAGE_HOSTS
        ):
            raise AppError(
                ErrorCode.YOUTUBE_CHANGED, {"message": "Not a picture address", "url": url}
            )
        return self._http_get(url)

    def _channel_page(self, address: str, options: Mapping[str, Any]) -> Mapping[str, Any]:
        """Ask for the Videos tab of a channel. A channel without one is asked for itself."""
        try:
            return self._ask(f"{address}{VIDEOS_TAB}", options, process=False)
        except AppError as error:
            if _NO_VIDEOS_TAB not in error.details.get("message", ""):
                raise
        answer = dict(self._ask(address, options, process=False))
        answer["entries"] = ()
        return answer

    def _ask(self, address: str, options: Mapping[str, Any], *, process: bool) -> Mapping[str, Any]:
        try:
            return self._extract(address, options, process)
        except AppError:
            raise
        except Exception as error:
            raise _as_app_error(error) from error

    def _videos(self, answer: Mapping[str, Any]) -> Iterator[ListedVideo]:
        try:
            for entry in answer.get("entries") or ():
                if entry is None or entry.get("live_status") in _NOT_REGULAR:
                    continue
                yield _video_of(entry, int(self._clock.now().timestamp()))
        except AppError:
            raise
        except Exception as error:
            raise _as_app_error(error) from error


def _as_app_error(error: Exception) -> AppError:
    """Turn an error of yt-dlp into an error with a code. The text is kept in full."""
    text = str(error)
    return AppError(code_of(f"{type(error).__name__}: {text}"), {"message": text})


def _facts_of(answer: Mapping[str, Any], asked_for: str) -> ChannelFacts:
    channel_id = answer.get("channel_id")
    if not isinstance(channel_id, str) or not channel_id.startswith("UC"):
        raise AppError(
            ErrorCode.YOUTUBE_CHANGED,
            {"message": "The answer names no channel", "channel": asked_for},
        )
    handle = answer.get("uploader_id")
    return ChannelFacts(
        channel_id=channel_id,
        title=str(answer.get("channel") or answer.get("uploader") or channel_id),
        handle=handle if isinstance(handle, str) and handle.startswith("@") else None,
        avatar_url=_avatar_of(answer.get("thumbnails") or ()),
    )


def _avatar_of(pictures: Any) -> str | None:
    """Return the avatar among the pictures of a channel: the square one, not a banner."""
    square = [
        picture
        for picture in pictures
        if picture.get("url")
        and picture.get("width")
        and picture.get("width") == picture.get("height")
    ]
    if square:
        return str(max(square, key=lambda picture: picture["width"])["url"])
    named = [picture for picture in pictures if picture.get("id") == "avatar_uncropped"]
    return str(named[0]["url"]) if named and named[0].get("url") else None


def _video_of(entry: Mapping[str, Any], listed_at: int) -> ListedVideo:
    duration = entry.get("duration")
    views = entry.get("view_count")
    point = entry.get("timestamp")
    return ListedVideo(
        id=str(entry["id"]),
        title=str(entry.get("title") or ""),
        duration_s=None if duration is None else int(duration),
        view_count=None if views is None else int(views),
        published_at=None if point is None else int(point),
        listed_at=listed_at,
        thumbnail_url=_thumbnail_of(entry.get("thumbnails") or ()),
    )


def _thumbnail_of(pictures: Any) -> str | None:
    """Return the smallest thumbnail a listing offers: it is the one a list row needs."""
    usable = [picture for picture in pictures if picture.get("url")]
    if not usable:
        return None
    return str(min(usable, key=lambda picture: picture.get("width") or 0)["url"])


@dataclass(frozen=True, slots=True)
class GatewayTools:
    """Where yt-dlp finds the programs it needs, inside the app folder (R-PL-15).

    Attributes:
        ffmpeg_folder: The folder with ffmpeg and ffprobe.
        deno: The Deno program.
    """

    ffmpeg_folder: Path
    deno: Path


class _Steps:
    """Turns the hooks of yt-dlp into one progress, and ends the download when it is cancelled.

    What the real yt-dlp reports, in order (seen with a real download in M3):
    the step that adds the tags and the conversion of the thumbnail, both
    before the download; the subtitle file; the video stream; the audio
    stream; then the processing steps. yt-dlp reports each file it downloads
    from 0 to 100% on its own, and the information of each holds no list of
    the others (it removes ``requested_formats``). The parts are therefore
    known from the metadata lookup before the download, and ``ProgressTracker``
    adds them up into one percent for the whole Mirror (R-QU-04, D-088). The
    thumbnail is not reported: it is complete when the first file arrives.
    Only a step after the first byte of a stream is processing.
    """

    def __init__(
        self,
        on_progress: Callable[[DownloadProgress], None],
        is_cancelled: Callable[[], bool],
        tracker: ProgressTracker,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._on_progress = on_progress
        self._is_cancelled = is_cancelled
        self._tracker = tracker
        self._monotonic = monotonic
        self.current: str | None = None
        self._streams_started = False
        self._thumbnail_done = False

    def downloading(self, report: Mapping[str, Any]) -> None:
        """The progress hook: called while the bytes of a file arrive."""
        if self._is_cancelled():
            raise DownloadCancelledError("cancelled while downloading")
        status = report.get("status")
        if status not in ("downloading", "finished"):
            return
        now = self._monotonic()
        if not self._thumbnail_done:
            self._thumbnail_done = True
            self._tracker.finish_kind(PartKind.THUMBNAIL, now)
        stream = _mapping(report.get("info_dict"))
        has_video = stream.get("vcodec") not in (None, "none")
        if _is_media(stream):
            self._streams_started = True
            key, kind = (
                str(stream.get("format_id")),
                PartKind.VIDEO if has_video else PartKind.AUDIO,
            )
        else:
            key, kind = PartKind.SUBTITLES.value, PartKind.SUBTITLES
        done = _int(report.get("downloaded_bytes")) or 0
        size = _int(report.get("total_bytes") or report.get("total_bytes_estimate"))
        if status == "finished":
            totals = self._tracker.finished(key, kind, size or done or None, now)
        else:
            totals = self._tracker.arrived(key, kind, done, size, now)
        self._on_progress(
            DownloadProgress(
                stage=Stage.AUDIO if kind is PartKind.AUDIO else Stage.VIDEO,
                fraction=totals.fraction,
                speed_bps=totals.speed_bps,
                left_s=totals.left_s,
                height=_int(stream.get("height")) if has_video else None,
                downloaded_bytes=totals.done_bytes,
                total_bytes=totals.total_bytes,
                parts=totals.parts,
            )
        )

    def processing(self, report: Mapping[str, Any]) -> None:
        """The post-processor hook: called before and after each processing step.

        Steps before the streams (the tags, the thumbnail) may end the download
        when it is cancelled, but they are no processing of the video.
        """
        step = str(report.get("postprocessor"))
        if step != TAGS_STEP and report.get("status") == "started":
            self.current = step
        if self._is_cancelled():
            raise DownloadCancelledError(f"cancelled at {step}")
        if self._streams_started and report.get("status") == "started" and step != TAGS_STEP:
            self._on_progress(DownloadProgress(stage=Stage.PROCESSING))


def planned_parts(info: Mapping[str, Any], subtitles: bool) -> list[PlannedPart]:
    """Return the parts a download fetches, with the sizes yt-dlp knows before it starts.

    The metadata lookup is made with the format choice of the download, so
    ``requested_formats`` names the streams that will be fetched (D-088).

    Args:
        info: The processed metadata of the video.
        subtitles: Whether a subtitle file is fetched.
    """
    duration = info.get("duration")
    listed = info.get("requested_formats")
    streams = [
        _mapping(item) for item in (cast(list[object], listed) if isinstance(listed, list) else [])
    ]
    if not streams and _is_media(info) and "+" not in str(info.get("format_id", "")):
        # One file with video and audio together: the info is that stream.
        streams = [dict(info)]
    parts = [PlannedPart(PartKind.THUMBNAIL.value, PartKind.THUMBNAIL, None)]
    if subtitles:
        parts.append(PlannedPart(PartKind.SUBTITLES.value, PartKind.SUBTITLES, None))
    for stream in streams:
        kind = PartKind.VIDEO if stream.get("vcodec") not in (None, "none") else PartKind.AUDIO
        tbr = stream.get("tbr")
        size = stream_size(
            _int(stream.get("filesize")),
            _int(stream.get("filesize_approx")),
            float(tbr) if isinstance(tbr, int | float) else None,
            float(duration) if isinstance(duration, int | float) else None,
        )
        parts.append(PlannedPart(str(stream.get("format_id")), kind, size))
    return parts


def _is_media(stream: Mapping[str, Any]) -> bool:
    """Whether a file yt-dlp downloads is a stream of the video: it has a codec."""
    return any(stream.get(codec) not in (None, "none") for codec in ("vcodec", "acodec"))


def _subtitles_for(
    info: Mapping[str, Any], request: DownloadRequest
) -> tuple[SubtitleKind | None, list[str]]:
    """Choose the English subtitles to embed: the creator's, else the automatic ones (R-MD-03)."""
    manual = sorted(_english(info.get("subtitles")))
    if request.manual_subtitles and manual:
        return SubtitleKind.MANUAL, ["en"] if "en" in manual else manual[:1]
    automatic = sorted(_english(info.get("automatic_captions")))
    if request.manual_subtitles and request.auto_subtitles and automatic:
        return SubtitleKind.AUTO, ["en"] if "en" in automatic else automatic[:1]
    return None, []


def _english(tracks: object) -> list[str]:
    if not isinstance(tracks, dict):
        return []
    return [
        str(language)
        for language in cast(dict[str, Any], tracks)
        if str(language) == "en" or str(language).startswith("en-")
    ]


def _mapping(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _json_text(answer: Mapping[str, Any]) -> str:
    """The raw metadata as JSON text that can always be written as UTF-8 (R-MD-02).

    Readable text is kept as it is. YouTube can give a lone surrogate, for
    example half an emoji cut off in a description: then everything outside
    ASCII is escaped, which keeps the exact text and is still valid JSON.
    """
    text = json.dumps(answer, ensure_ascii=False, default=str)
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return json.dumps(answer, ensure_ascii=True, default=str)
    return text


def _int(value: object) -> int | None:
    return int(value) if isinstance(value, int | float) else None


def _iso(moment: int) -> str:
    return datetime.datetime.fromtimestamp(moment, datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class _JobLog:
    """Writes all that yt-dlp and ffmpeg say in one download into the log of its job (R-LG-02)."""

    def __init__(self, file: Path) -> None:
        self._file = file
        file.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, level: str, message: str) -> None:
        with self._file.open("a", encoding="utf-8") as log:
            log.write(f"{level} {message}\n")

    def debug(self, message: str) -> None:
        self._write("debug", message)

    def info(self, message: str) -> None:
        self._write("info", message)

    def warning(self, message: str) -> None:
        self._write("warning", message)

    def error(self, message: str) -> None:
        self._write("error", message)


class _YtDlpLog:
    """Passes what yt-dlp says on to the debug log, as lines of a library."""

    def __init__(self) -> None:
        self._log = logging.getLogger("yt_dlp")

    def debug(self, message: str) -> None:
        self._log.debug(message)

    def info(self, message: str) -> None:
        self._log.info(message)

    def warning(self, message: str) -> None:
        self._log.warning(message)

    def error(self, message: str) -> None:
        # The error is raised as well and logged once where it is handled (LOGGING rule 6).
        self._log.debug(message)


def extract_with_ytdlp(
    address: str, options: Mapping[str, Any], process: bool
) -> Mapping[str, Any]:  # pragma: no cover  (the network. Tested live)
    """Ask the real yt-dlp. Imported late: only a run that asks YouTube needs it."""
    yt_dlp = importlib.import_module("yt_dlp")
    with yt_dlp.YoutubeDL({**options, "logger": _YtDlpLog()}) as ydl:
        answer = ydl.extract_info(address, download=False, process=process)
    if not isinstance(answer, dict):
        raise AppError(ErrorCode.YOUTUBE_CHANGED, {"message": "yt-dlp gave no answer"})
    return cast(dict[str, Any], answer)


def _get_with_httpx(url: str) -> bytes:  # pragma: no cover  (the network. Tested live)
    """Fetch a picture with the HTTP client of the app."""
    try:
        response = httpx2.get(url, follow_redirects=True, timeout=_IMAGE_TIMEOUT_S)
    except httpx2.HTTPError as error:
        raise AppError(
            ErrorCode.NETWORK_UNREACHABLE, {"message": str(error), "url": url}
        ) from error
    return checked_image(url, response.status_code, response.content)


def checked_image(url: str, status: int, content: bytes) -> bytes:
    """Return the bytes of a fetched picture, or raise the code of what went wrong.

    Args:
        url: The address that was fetched.
        status: The HTTP status of the answer.
        content: The body of the answer.

    Raises:
        AppError: For a status that is not a success, or a body that is too large.
    """
    if status == _TOO_MANY_REQUESTS:
        raise AppError(ErrorCode.RATE_LIMITED, {"url": url, "status": str(status)})
    if status >= 500:
        raise AppError(ErrorCode.NETWORK_UNREACHABLE, {"url": url, "status": str(status)})
    if status >= 400 or len(content) > _MAX_IMAGE_BYTES or not content:
        raise AppError(ErrorCode.YOUTUBE_CHANGED, {"url": url, "status": str(status)})
    return content


def download_with_ytdlp(
    info: Mapping[str, Any], options: Mapping[str, Any], tags: Mapping[str, str]
) -> Mapping[str, Any]:
    """Download with the real yt-dlp from metadata already looked up, adding tags of our own.

    The metadata of the lookup before the download is processed again with the
    options of the download, as yt-dlp does for ``--load-info-json``: the page
    of the video is not asked for a second time, so a download counts as one
    lookup in the budget (R-DT-06), and the streams fetched are the ones the
    progress was planned with (D-088).

    A post-processor that runs before the download sets ``meta_<name>``
    fields, which the metadata step of yt-dlp writes as tags (R-MD-01, R-DT-08).
    """
    yt_dlp = importlib.import_module("yt_dlp")
    base: Any = importlib.import_module("yt_dlp.postprocessor.common").PostProcessor

    # yt-dlp names a step after its class, without the last two letters.
    class _AddTagsPP(base):  # type: ignore[misc, valid-type]
        def run(self, information: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
            for name, value in tags.items():
                information[f"meta_{name}"] = value
            return [], information

    with yt_dlp.YoutubeDL(dict(options)) as ydl:
        ydl.add_post_processor(_AddTagsPP(), when="pre_process")
        answer = ydl.process_ie_result(copy.deepcopy(dict(info)), download=True)
        clean = ydl.sanitize_info(answer)
    if not isinstance(clean, dict):
        raise AppError(ErrorCode.YOUTUBE_CHANGED, {"message": "yt-dlp gave no answer"})
    return cast(dict[str, Any], clean)
