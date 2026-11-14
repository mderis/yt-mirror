"""The YouTubeGateway port on the real YouTube, through yt-dlp as a library.

From milestone M2: channel lookup, the listing of a channel's Videos tab,
the optional video count of a preview, and pictures. The options were
checked against the pinned yt-dlp and the real YouTube in that milestone
(docs/ARCHITECTURE.md section 7.3, docs/DECISIONS.md D-069).

Every error text of yt-dlp is turned into an error code here. This module
must not decide anything about the catalogue, and it must not set a proxy:
yt-dlp and the HTTP client honour the proxy settings of the environment by
themselves (R-PL-08).

Tests: backend/tests/integration/test_ytdlp_gateway.py and
backend/tests/integration/test_youtube_gateway_contract.py. The one call
that reaches the network is tested by backend/tests/live/test_youtube_live.py.
"""

import importlib
import logging
from collections.abc import Callable, Iterator, Mapping
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
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.ports.clock import Clock

type Extract = Callable[[str, Mapping[str, Any], bool], Mapping[str, Any]]
"""Asks yt-dlp about an address: the address, the options, and whether yt-dlp
should also process the answer. Returns the answer of yt-dlp. With processing
off, the entries of a listing are fetched page by page while they are read."""

type HttpGet = Callable[[str], bytes]
"""Fetches the bytes behind an address, or raises ``AppError``."""

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


def code_of(error_text: str) -> ErrorCode:
    """Return the error code for an error text of yt-dlp.

    A text that is not known becomes ``YOUTUBE_CHANGED``: most likely YouTube
    changed something that yt-dlp does not know yet (docs/DECISIONS.md D-069).

    Args:
        error_text: The text of the error.
    """
    text = error_text.lower()
    for code, signs in _CODES:
        if any(sign in text for sign in signs):
            return code
    return ErrorCode.YOUTUBE_CHANGED


class YtDlpGateway:
    """Asks the real YouTube through yt-dlp."""

    def __init__(
        self, clock: Clock, *, extract: Extract | None = None, http_get: HttpGet | None = None
    ) -> None:
        """Create the gateway.

        Args:
            clock: Says when a listed video was read.
            extract: A stand-in for yt-dlp. For tests.
            http_get: A stand-in for the HTTP client. For tests.
        """
        self._clock = clock
        self._extract = extract if extract is not None else extract_with_ytdlp
        self._http_get = http_get if http_get is not None else _get_with_httpx

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
