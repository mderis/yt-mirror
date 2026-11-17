"""The ExactDateSource port on the real YouTube Data API (``videos.list``).

Implements the source with a key of R-DT-05 (docs/DECISIONS.md D-082). The
videos are asked for by ID, 50 per request, with ``part=snippet,liveStreamingDetails``.
The exact time of a video is its actual start when it has one (a premiere,
R-DT-03), else ``snippet.publishedAt`` when it has no live streaming details.
A video with live streaming details and no actual start has not been
released and gets None. A video the API does not return is left out (D-083).

The key travels only in the ``X-Goog-Api-Key`` header, never in an address,
so it cannot appear in an error text of the HTTP client; an error text of
the API is still cleaned of it before it goes into an error.

Tests: backend/tests/integration/test_youtube_api.py and
backend/tests/integration/test_exact_date_source_contract.py
"""

import datetime
from collections.abc import Mapping, Sequence
from typing import Any, cast

import httpx2

from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.ports.exact_date_source import MOST_IDS_PER_REQUEST

API_ADDRESS = "https://www.googleapis.com/youtube/v3"
KEY_TEST_VIDEO = "jNQXAC9IVRw"
"""A video that has been public since 2005, asked for when a key is tested."""
_TIMEOUT_S = 15.0
_OK = 200
_FORBIDDEN = 403
_TOO_MANY = 429
_SERVER_ERRORS = 500

# The reasons the API gives, and the code each one means.
_REASONS: Mapping[str, ErrorCode] = {
    "keyInvalid": ErrorCode.API_KEY_INVALID,
    "keyExpired": ErrorCode.API_KEY_INVALID,
    "badRequest": ErrorCode.API_KEY_INVALID,
    "accessNotConfigured": ErrorCode.API_KEY_INVALID,
    "forbidden": ErrorCode.API_KEY_INVALID,
    "ipRefererBlocked": ErrorCode.API_KEY_INVALID,
    "quotaExceeded": ErrorCode.API_QUOTA_EXCEEDED,
    "dailyLimitExceeded": ErrorCode.API_QUOTA_EXCEEDED,
    "rateLimitExceeded": ErrorCode.RATE_LIMITED,
    "userRateLimitExceeded": ErrorCode.RATE_LIMITED,
}


class YouTubeApi:
    """Asks the YouTube Data API for exact dates."""

    def __init__(self, address: str = API_ADDRESS, timeout_s: float = _TIMEOUT_S) -> None:
        """Create the client.

        Args:
            address: The address of the API. Tests give a local server.
            timeout_s: How long one request may take.
        """
        self._address = address.rstrip("/")
        self._timeout_s = timeout_s

    def video_dates(self, key: str, video_ids: Sequence[str]) -> Mapping[str, int | None]:
        """Return the exact published times of up to 50 videos (R-DT-03, R-DT-05, D-083).

        Args:
            key: The API key.
            video_ids: At most 50 video IDs.

        Raises:
            AppError: ``API_KEY_INVALID``, ``API_QUOTA_EXCEEDED``, ``RATE_LIMITED`` or
                ``NETWORK_UNREACHABLE``.
            ValueError: For more than 50 IDs.
        """
        if len(video_ids) > MOST_IDS_PER_REQUEST:
            raise ValueError(f"at most {MOST_IDS_PER_REQUEST} video IDs in one request")
        if not video_ids:
            return {}
        answer = self._get(key, {"part": "snippet,liveStreamingDetails", "id": ",".join(video_ids)})
        dates: dict[str, int | None] = {}
        for item in _items(answer):
            video_id = item.get("id")
            if isinstance(video_id, str) and video_id in video_ids:
                dates[video_id] = exact_time_of(item)
        return dates

    def test_key(self, key: str) -> None:
        """Ask for one video with the key, to see whether it works (R-DT-12).

        Args:
            key: The API key.

        Raises:
            AppError: With the code of what went wrong.
        """
        self._get(key, {"part": "id", "id": KEY_TEST_VIDEO})

    def _get(self, key: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        try:
            response = httpx2.get(
                f"{self._address}/videos",
                params=dict(params),
                headers={"X-Goog-Api-Key": key, "Accept": "application/json"},
                timeout=self._timeout_s,
            )
        except httpx2.HTTPError as error:
            raise AppError(
                ErrorCode.NETWORK_UNREACHABLE,
                {"message": _without(f"{type(error).__name__}: {error}", key)},
            ) from error
        try:
            body = response.json()
        except ValueError:
            body = {}
        if not isinstance(body, dict):
            body = {}
        if response.status_code >= _SERVER_ERRORS:
            raise AppError(
                ErrorCode.NETWORK_UNREACHABLE,
                {"message": f"the API answered {response.status_code}"},
            )
        if response.status_code != _OK:
            raise _error_of(response.status_code, cast(dict[str, Any], body), key)
        return cast(dict[str, Any], body)


def exact_time_of(item: Mapping[str, Any]) -> int | None:
    """Return the exact published time of one item of ``videos.list`` (R-DT-03, D-082).

    Args:
        item: One item of the answer.

    Returns:
        The actual start of a premiere, else the time it became public, or None
        for a video with live streaming details and no actual start.
    """
    live = item.get("liveStreamingDetails")
    if isinstance(live, dict):
        started = cast(dict[str, Any], live).get("actualStartTime")
        return _seconds(started) if isinstance(started, str) else None
    snippet = item.get("snippet")
    if isinstance(snippet, dict):
        published = cast(dict[str, Any], snippet).get("publishedAt")
        if isinstance(published, str):
            return _seconds(published)
    return None


def _items(answer: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    items = answer.get("items")
    if not isinstance(items, list):
        return []
    return [cast(dict[str, Any], item) for item in cast(list[Any], items) if isinstance(item, dict)]


def _error_of(status: int, body: Mapping[str, Any], key: str) -> AppError:
    error = body.get("error")
    error = cast(dict[str, Any], error) if isinstance(error, dict) else {}
    reasons = [
        str(cast(dict[str, Any], entry).get("reason", ""))
        for entry in cast(list[Any], error.get("errors") or [])
        if isinstance(entry, dict)
    ]
    message = _without(str(error.get("message", "")), key)
    for reason in reasons:
        if reason in _REASONS:
            return AppError(
                _REASONS[reason], {"reason": reason, "status": str(status), "message": message}
            )
    if status == _TOO_MANY:
        code = ErrorCode.RATE_LIMITED
    elif status == _FORBIDDEN and "quota" in message.lower():
        code = ErrorCode.API_QUOTA_EXCEEDED
    else:
        code = ErrorCode.API_KEY_INVALID
    return AppError(code, {"reason": ",".join(reasons), "status": str(status), "message": message})


def _without(text: str, key: str) -> str:
    """Return a text with the key taken out, should it ever be in it."""
    return text.replace(key, "[key]") if key else text


def _seconds(text: str) -> int | None:
    try:
        moment = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=datetime.UTC)
    return int(moment.timestamp())
