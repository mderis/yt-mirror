"""Tests of ``ytmirror.adapters.youtube_api`` against a local server that answers like the API."""

import pytest

from tests.fixtures.youtube_api_server import (
    api_server,
    error_body,
    premiere,
    regular,
)
from ytmirror.adapters.youtube_api import KEY_TEST_VIDEO, YouTubeApi, exact_time_of
from ytmirror.core.errors import AppError, ErrorCode

KEY = "AIzaStandInKeyForTests000000000000000"
"""Not a real key: it has the shape of one, so that a leak would be seen."""


def test_the_key_travels_in_a_header_and_never_in_the_address() -> None:
    """R-DT-12, R-LG-07: the key is sent in X-Goog-Api-Key only."""
    with api_server() as server:
        YouTubeApi(server.address).video_dates(KEY, ["a0000000001"])

    [asked] = server.asked
    assert asked.headers["x-goog-api-key"] == KEY
    assert KEY not in asked.path
    assert all(KEY not in value for values in asked.query.values() for value in values)


def test_videos_are_asked_for_by_id_with_snippet_and_live_streaming_details() -> None:
    """R-DT-05, D-082: one request of videos.list for up to 50 IDs."""
    ids = [f"v{number:010d}" for number in range(50)]
    with api_server() as server:
        YouTubeApi(server.address).video_dates(KEY, ids)

    [asked] = server.asked
    assert asked.path == "/youtube/v3/videos"
    assert asked.query["part"] == ["snippet,liveStreamingDetails"]
    assert asked.query["id"] == [",".join(ids)]


def test_more_than_50_ids_are_refused_before_asking() -> None:
    """R-DT-05: the API answers at most 50 IDs in one request."""
    with pytest.raises(ValueError, match="50"):
        YouTubeApi("http://127.0.0.1:9").video_dates(KEY, ["v"] * 51)


def test_no_ids_ask_nothing() -> None:
    """R-DT-05: an empty request costs no quota."""
    assert YouTubeApi("http://127.0.0.1:9").video_dates(KEY, []) == {}


def test_a_regular_video_has_its_published_time_and_a_premiere_its_actual_start() -> None:
    """R-DT-03, D-082: measured in M4, publishedAt of a premiere is its upload time."""
    with api_server() as server:
        server.items = {
            "reg00000001": regular("reg00000001", "2026-11-03T08:30:15Z"),
            "pre00000001": premiere("pre00000001", "2018-10-27T17:13:22Z", "2018-10-27T17:15:10Z"),
        }
        dates = YouTubeApi(server.address).video_dates(KEY, ["reg00000001", "pre00000001"])

    assert dates == {"reg00000001": 1_793_694_615, "pre00000001": 1_540_660_510}


def test_a_premiere_that_has_not_started_has_no_exact_date() -> None:
    """R-DT-03: neither its scheduled time nor its upload time is taken as exact."""
    assert exact_time_of(premiere("up000000001", "2026-11-20T10:00:00Z", None)) is None


def test_a_video_the_api_does_not_return_is_left_out() -> None:
    """R-DT-05, D-083: an empty answer gives no date and says nothing about the video."""
    with api_server() as server:
        server.items = {"reg00000001": regular("reg00000001", "2026-11-03T08:30:15Z")}
        dates = YouTubeApi(server.address).video_dates(KEY, ["reg00000001", "gone0000001"])

    assert dates == {"reg00000001": 1_793_694_615}


def test_an_item_without_a_time_has_none() -> None:
    """R-DT-05: an answer the adapter cannot read gives no exact date."""
    assert exact_time_of({"id": "x"}) is None
    assert exact_time_of({"id": "x", "snippet": {"publishedAt": "not a time"}}) is None


@pytest.mark.parametrize(
    ("status", "reason", "code"),
    [
        (400, "keyInvalid", ErrorCode.API_KEY_INVALID),
        (400, "badRequest", ErrorCode.API_KEY_INVALID),
        (403, "accessNotConfigured", ErrorCode.API_KEY_INVALID),
        (403, "quotaExceeded", ErrorCode.API_QUOTA_EXCEEDED),
        (403, "rateLimitExceeded", ErrorCode.RATE_LIMITED),
        (429, "somethingNew", ErrorCode.RATE_LIMITED),
        (401, "somethingNew", ErrorCode.API_KEY_INVALID),
    ],
)
def test_an_error_of_the_api_has_a_code(status: int, reason: str, code: ErrorCode) -> None:
    """R-DT-12: a failing key or a used-up quota has its own code, which the app falls back on."""
    with api_server() as server:
        server.answer = (status, error_body(reason, f"API key not valid: {KEY}"))
        with pytest.raises(AppError) as failure:
            YouTubeApi(server.address).video_dates(KEY, ["a0000000001"])

    assert failure.value.code is code
    assert KEY not in str(failure.value.details)


def test_a_server_error_is_a_network_failure() -> None:
    """R-DT-12: a passing fault of the API is not a failing key."""
    with api_server() as server:
        server.answer = (503, {"error": {"message": "backend error"}})
        with pytest.raises(AppError) as failure:
            YouTubeApi(server.address).video_dates(KEY, ["a0000000001"])

    assert failure.value.code is ErrorCode.NETWORK_UNREACHABLE


def test_an_api_that_cannot_be_reached_is_a_network_failure_without_the_key() -> None:
    """R-DT-12, R-LG-07: nothing listens there."""
    with pytest.raises(AppError) as failure:
        YouTubeApi("http://127.0.0.1:9/youtube/v3", timeout_s=2).video_dates(KEY, ["a0000000001"])

    assert failure.value.code is ErrorCode.NETWORK_UNREACHABLE
    assert KEY not in str(failure.value.details)


def test_testing_a_key_asks_for_one_old_video() -> None:
    """R-DT-12: "Test key" asks the API once."""
    with api_server() as server:
        YouTubeApi(server.address).test_key(KEY)

    [asked] = server.asked
    assert asked.query["id"] == [KEY_TEST_VIDEO]
    assert asked.query["part"] == ["id"]
