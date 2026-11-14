"""Tests of the real gateway on recorded answers of yt-dlp: what only it does."""

import itertools
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from tests.fixtures.fakes.clock import FakeClock
from tests.fixtures.ytdlp_replay import (
    CHANNEL_ID,
    EMPTY_CHANNEL_ID,
    HANDLE,
    RECORDED_VIDEOS,
    UNKNOWN_CHANNEL_ID,
    DownloadError,
    Replay,
    recordings,
)
from ytmirror.adapters.ytdlp_gateway import (
    COUNT_OPTIONS,
    LISTING_OPTIONS,
    LOOKUP_OPTIONS,
    YtDlpGateway,
    checked_image,
    code_of,
)
from ytmirror.core.channels import ChannelReference, DatePrecision, ReferenceKind
from ytmirror.core.dates import precision_of
from ytmirror.core.errors import AppError, ErrorCode

BY_HANDLE = ChannelReference(ReferenceKind.HANDLE, HANDLE)


def gateway_with(replay: Replay, clock: FakeClock | None = None) -> YtDlpGateway:
    """Return the real gateway, asking the replay instead of yt-dlp."""
    return YtDlpGateway(clock or FakeClock(), extract=replay, http_get=lambda url: b"picture")


def listing_with(change: Callable[[dict[str, Any]], object]) -> Replay:
    """Return a replay whose recorded listing was changed by a function."""
    recorded = recordings()
    change(recorded["listing"]["answer"])
    return Replay(recorded)


# --- what is asked of yt-dlp


def test_a_lookup_asks_for_the_videos_tab_and_reads_no_videos() -> None:
    """R-CH-03: a lookup reads the channel itself: one request, no listing."""
    replay = Replay()

    gateway_with(replay).lookup_channel(BY_HANDLE)

    assert replay.asked == [(f"https://www.youtube.com/{HANDLE}/videos", LOOKUP_OPTIONS, False)]
    assert replay.entries_read == 0


def test_a_listing_asks_for_the_videos_tab_of_the_channel_id() -> None:
    """R-CH-07: only the Videos tab is listed, so Shorts and streams are not."""
    replay = Replay()

    gateway_with(replay).list_channel(CHANNEL_ID)

    address, options, process = replay.asked[0]
    assert address == f"https://www.youtube.com/channel/{CHANNEL_ID}/videos"
    assert options == LISTING_OPTIONS
    assert process is False


def test_a_listing_asks_for_dates_and_refuses_a_cut_off_answer() -> None:
    """R-DT-04, R-CH-13: without these two arguments a listing has no dates and can end early."""
    assert LISTING_OPTIONS["extractor_args"] == {
        "youtubetab": {"approximate_date": ["true"]},
        "youtube": {"raise_incomplete_data": ["true"]},
    }
    assert LISTING_OPTIONS["extract_flat"] == "in_playlist"


def test_the_count_asks_the_playlist_of_long_videos_with_a_short_time_limit() -> None:
    """R-CH-03: the count comes from one request that reads no video and gives up after 8 s."""
    replay = Replay()

    gateway_with(replay).preview_video_count(CHANNEL_ID)

    address, options, process = replay.asked[0]
    assert address == f"https://www.youtube.com/playlist?list=UULF{CHANNEL_ID.removeprefix('UC')}"
    assert options == COUNT_OPTIONS
    assert (options["socket_timeout"], options["extractor_retries"]) == (8, 0)
    assert options["playlist_items"] == "0"
    assert process is True


@pytest.mark.parametrize("options", [LOOKUP_OPTIONS, LISTING_OPTIONS, COUNT_OPTIONS])
def test_yt_dlp_is_never_given_a_proxy_of_ours(options: dict[str, Any]) -> None:
    """R-PL-08: no proxy is set, so yt-dlp honours the proxy settings of the environment."""
    assert "proxy" not in options
    assert "source_address" not in options


@pytest.mark.parametrize("options", [LOOKUP_OPTIONS, LISTING_OPTIONS, COUNT_OPTIONS])
def test_yt_dlp_writes_nothing_outside_the_app_folder_and_waits_a_set_time(
    options: dict[str, Any],
) -> None:
    """R-CH-11: the app sets the time limits itself, and yt-dlp keeps no cache elsewhere."""
    assert options["cachedir"] is False
    assert options["skip_download"] is True
    assert 0 < options["socket_timeout"] <= 20
    assert options["extractor_retries"] <= 2


# --- what is read from the answer


def test_the_facts_of_a_channel_are_read_from_the_answer() -> None:
    """R-CH-03: name, handle and the square avatar come from the channel's own data."""
    facts = gateway_with(Replay()).lookup_channel(BY_HANDLE)

    assert facts.channel_id == CHANNEL_ID
    assert facts.title == "Recorded Channel"
    assert facts.handle == HANDLE
    assert facts.avatar_url == "https://yt3.googleusercontent.com/recorded-0=s0"
    assert facts.url == f"https://www.youtube.com/channel/{CHANNEL_ID}"


def test_a_channel_without_a_handle_has_none() -> None:
    """R-CH-03: a channel that YouTube gives no handle for is shown without one."""
    facts = gateway_with(Replay()).lookup_channel(
        ChannelReference(ReferenceKind.CHANNEL_ID, EMPTY_CHANNEL_ID)
    )

    assert facts.handle is None
    assert facts.title == "Recorded Channel"


def test_without_a_square_picture_the_named_avatar_is_taken() -> None:
    """R-CH-03: a banner is never taken for the avatar."""

    def keep_banners_and_named_avatar(answer: dict[str, Any]) -> None:
        answer["thumbnails"] = [
            picture for picture in answer["thumbnails"] if picture.get("width") != 900
        ]

    gateway = gateway_with(listing_with(keep_banners_and_named_avatar))

    facts = gateway.list_channel(CHANNEL_ID).facts

    assert facts.avatar_url == "https://yt3.googleusercontent.com/recorded-1=s0"


def test_a_channel_without_pictures_has_no_avatar() -> None:
    """R-CH-03: missing pictures are no error."""

    def no_pictures(answer: dict[str, Any]) -> None:
        answer["thumbnails"] = []

    gateway = gateway_with(listing_with(no_pictures))

    assert gateway.list_channel(CHANNEL_ID).facts.avatar_url is None


def test_a_listed_video_is_read_from_its_entry() -> None:
    """R-CH-10: ID, title, duration, views, the approximate date and a thumbnail are taken over."""
    clock = FakeClock(datetime(2026, 11, 14, 7, 38, 49, tzinfo=UTC))

    video = next(gateway_with(Replay(), clock).list_channel(CHANNEL_ID).videos)

    assert video.id == "rec00000001"
    assert video.title == "Recorded video 1"
    assert (video.duration_s, video.view_count) == (1177, 4_100_000)
    assert video.published_at == 1763078400
    assert video.listed_at == int(clock.now().timestamp())
    assert video.thumbnail_url == "https://i.ytimg.com/vi/rec00000001/recorded-360.jpg"


def test_every_recorded_date_gets_a_unit_by_the_exact_rules() -> None:
    """R-DT-04: for a real listing the unit is found for every video, here all in years."""
    recorded_at = recordings()["recorded_at"]
    clock = FakeClock(datetime.fromtimestamp(recorded_at, UTC))

    videos = list(gateway_with(Replay(), clock).list_channel(CHANNEL_ID).videos)

    units = {precision_of(video.published_at or 0, video.listed_at) for video in videos}
    assert len(videos) == RECORDED_VIDEOS
    assert all(video.published_at is not None for video in videos)
    assert units == {DatePrecision.YEAR}


def test_missing_values_of_an_entry_stay_missing() -> None:
    """R-CH-10: an entry without duration, views, date or pictures is still a video."""

    def strip_first(answer: dict[str, Any]) -> None:
        answer["entries"][0].update(
            duration=None, view_count=None, timestamp=None, thumbnails=[], title=None
        )

    video = next(gateway_with(listing_with(strip_first)).list_channel(CHANNEL_ID).videos)

    assert video.id == "rec00000001"
    assert video.title == ""
    assert (video.duration_s, video.view_count, video.published_at) == (None, None, None)
    assert video.thumbnail_url is None


def test_a_single_thumbnail_is_taken_as_it_is() -> None:
    """R-CH-16: older videos come with one picture, and that one is used."""

    def one_picture(answer: dict[str, Any]) -> None:
        answer["entries"][0]["thumbnails"] = [
            {"url": "https://i.ytimg.com/vi/rec00000001/hqdefault.jpg", "width": 480, "height": 270}
        ]

    video = next(gateway_with(listing_with(one_picture)).list_channel(CHANNEL_ID).videos)

    assert video.thumbnail_url == "https://i.ytimg.com/vi/rec00000001/hqdefault.jpg"


def test_live_streams_are_left_out_of_a_listing() -> None:
    """R-CH-07: what yt-dlp marks as a live stream or a past stream is not listed."""

    def mark_streams(answer: dict[str, Any]) -> None:
        answer["entries"][0]["live_status"] = "is_live"
        answer["entries"][1]["live_status"] = "was_live"
        answer["entries"][2]["live_status"] = "is_upcoming"
        answer["entries"].insert(3, None)

    videos = list(gateway_with(listing_with(mark_streams)).list_channel(CHANNEL_ID).videos)

    assert [video.id for video in videos[:2]] == ["rec00000003", "rec00000004"]
    assert len(videos) == RECORDED_VIDEOS - 2


def test_a_channel_without_a_videos_tab_has_an_empty_listing() -> None:
    """R-CH-07: a channel without regular videos is no error: it lists nothing."""
    replay = Replay()

    listing = gateway_with(replay).list_channel(EMPTY_CHANNEL_ID)

    assert listing.facts.channel_id == EMPTY_CHANNEL_ID
    assert list(listing.videos) == []
    assert [address.rsplit("/", 1)[-1] for address, _, _ in replay.asked] == [
        "videos",
        EMPTY_CHANNEL_ID,
    ]


def test_an_answer_that_names_no_channel_is_not_trusted() -> None:
    """R-CH-03: an answer without a channel ID means YouTube changed, not "a channel"."""

    def no_channel(answer: dict[str, Any]) -> None:
        answer["channel_id"] = None

    gateway = gateway_with(listing_with(no_channel))

    with pytest.raises(AppError) as failure:
        gateway.list_channel(CHANNEL_ID)

    assert failure.value.code is ErrorCode.YOUTUBE_CHANGED


# --- the video count


def test_the_count_is_the_number_the_playlist_reports() -> None:
    """R-CH-03: the playlist of long videos gives the count of the preview."""
    assert gateway_with(Replay()).preview_video_count(CHANNEL_ID) == 149


@pytest.mark.parametrize(
    "change",
    [
        {"playlist_count": None},
        {"playlist_count": "149"},
        {"playlist_count": True},
        {"channel_id": "UCsomebodyelse0000000009"},
    ],
)
def test_a_count_that_is_no_number_or_of_another_channel_is_refused(
    change: dict[str, Any],
) -> None:
    """R-CH-03: an answer that gives no usable number counts as "no count"."""
    recorded = recordings()
    recorded["count"]["answer"].update(change)

    with pytest.raises(AppError) as failure:
        gateway_with(Replay(recorded)).preview_video_count(CHANNEL_ID)

    assert failure.value.code is ErrorCode.YOUTUBE_CHANGED


def test_a_count_for_an_unknown_channel_fails() -> None:
    """R-CH-03: a missing playlist is a failure of the count, which the caller turns into none."""
    with pytest.raises(AppError):
        gateway_with(Replay()).preview_video_count(UNKNOWN_CHANNEL_ID)


# --- errors


@pytest.mark.parametrize(
    ("text", "code"),
    [
        (recordings()["unknown_handle"]["error"], ErrorCode.CHANNEL_NOT_FOUND),
        (recordings()["unknown_channel_id"]["error"], ErrorCode.CHANNEL_NOT_FOUND),
        (
            "DownloadError: ERROR: [youtube] abc: Sign in to confirm you\u2019re not a bot."
            " Use --cookies-from-browser or --cookies for the authentication.",
            ErrorCode.BOT_CHECK,
        ),
        ("ERROR: [youtube] abc: Sign in to confirm you're not a bot", ErrorCode.BOT_CHECK),
        (
            "ERROR: [youtube:tab] @x/videos: Unable to download API page: timed out"
            " (caused by TransportError('timed out'))",
            ErrorCode.NETWORK_UNREACHABLE,
        ),
        (
            "ERROR: Unable to download webpage: [Errno 8] nodename nor servname provided",
            ErrorCode.NETWORK_UNREACHABLE,
        ),
        (
            "ERROR: [youtube:tab] UCx: Incomplete data received; please try again",
            ErrorCode.NETWORK_UNREACHABLE,
        ),
        (
            "ERROR: Unable to download API page: HTTP Error 503: Service Unavailable",
            ErrorCode.NETWORK_UNREACHABLE,
        ),
        (
            "ERROR: Unable to download API page: HTTP Error 429: Too Many Requests",
            ErrorCode.RATE_LIMITED,
        ),
        ("ERROR: [youtube:tab] UCx: This account has been terminated", ErrorCode.CHANNEL_NOT_FOUND),
        ("ERROR: [youtube:tab] UCx: Unable to extract yt initial data", ErrorCode.YOUTUBE_CHANGED),
        ("KeyError: 'contents'", ErrorCode.YOUTUBE_CHANGED),
    ],
)
def test_an_error_text_of_yt_dlp_becomes_an_error_code(text: str, code: ErrorCode) -> None:
    """R-ER-02: every error has a code, and a text nobody knows means YouTube changed."""
    assert code_of(text) is code


def test_the_not_a_bot_check_has_a_code_of_its_own() -> None:
    """R-ER-05: the check is told apart from a rate limit and from a broken connection."""
    text = "Sign in to confirm you\u2019re not a bot. This helps protect our community."

    assert code_of(text) is ErrorCode.BOT_CHECK
    assert code_of(text) not in (ErrorCode.RATE_LIMITED, ErrorCode.NETWORK_UNREACHABLE)


def test_the_full_error_text_travels_with_the_error() -> None:
    """R-ER-02: the technical details carry the original text, so it can be logged in full."""
    with pytest.raises(AppError) as failure:
        gateway_with(Replay()).lookup_channel(
            ChannelReference(ReferenceKind.CHANNEL_ID, UNKNOWN_CHANNEL_ID)
        )

    assert failure.value.code is ErrorCode.CHANNEL_NOT_FOUND
    assert failure.value.details["message"].endswith("YouTube said: This channel does not exist.")


def test_an_error_while_reading_is_an_error_with_a_code() -> None:
    """R-CH-13: a listing that breaks part of the way fails, it never ends as if complete."""
    replay = Replay()
    replay.fail_after = (40, "ERROR: [youtube:tab] x: Incomplete data received")
    listing = gateway_with(replay).list_channel(CHANNEL_ID)

    read = list(itertools.islice(listing.videos, 40))
    with pytest.raises(AppError) as failure:
        next(listing.videos)

    assert len(read) == 40
    assert failure.value.code is ErrorCode.NETWORK_UNREACHABLE


def test_an_error_of_ours_passes_through_unchanged() -> None:
    """infra: an error that already has a code is not classified a second time."""

    def refuses(address: str, options: Any, process: bool) -> Any:
        raise AppError(ErrorCode.RATE_LIMITED, {"from": "a stand-in"})

    gateway = YtDlpGateway(FakeClock(), extract=refuses, http_get=lambda url: b"")

    with pytest.raises(AppError) as failure:
        gateway.lookup_channel(BY_HANDLE)

    assert failure.value.details == {"from": "a stand-in"}


def test_another_error_than_a_missing_tab_is_not_retried_without_the_tab() -> None:
    """infra: only "no videos tab" leads to a second question."""
    replay = Replay()

    with pytest.raises(AppError):
        gateway_with(replay).list_channel(UNKNOWN_CHANNEL_ID)

    assert len(replay.asked) == 1


def test_an_error_of_our_own_while_reading_passes_through() -> None:
    """infra: an error with a code that comes up while reading is not wrapped again."""

    def entries() -> Any:
        yield {"id": "rec00000001", "title": "One"}
        raise AppError(ErrorCode.BOT_CHECK)

    def answers(address: str, options: Any, process: bool) -> Any:
        return {"channel_id": CHANNEL_ID, "channel": "Recorded Channel", "entries": entries()}

    listing = YtDlpGateway(FakeClock(), extract=answers).list_channel(CHANNEL_ID)
    next(listing.videos)

    with pytest.raises(AppError) as failure:
        next(listing.videos)

    assert failure.value.code is ErrorCode.BOT_CHECK
    assert failure.value.details == {}


def test_the_replay_raises_errors_as_yt_dlp_does() -> None:
    """infra: a recorded error comes back under the name of the error class of yt-dlp."""
    with pytest.raises(DownloadError):
        Replay()(f"https://www.youtube.com/channel/{UNKNOWN_CHANNEL_ID}/videos", {}, False)


# --- pictures


def test_a_picture_is_fetched_only_from_the_picture_servers_of_youtube() -> None:
    """R-HE-03: pictures come from YouTube's media servers and from nowhere else."""
    fetched: list[str] = []

    def get(url: str) -> bytes:
        fetched.append(url)
        return b"picture"

    gateway = YtDlpGateway(FakeClock(), extract=Replay(), http_get=get)

    for url in (
        "https://i.ytimg.com/vi/abc/hqdefault.jpg",
        "https://yt3.googleusercontent.com/abc=s900",
        "https://yt3.ggpht.com/abc=s900",
    ):
        assert gateway.fetch_image(url) == b"picture"
    for url in (
        "https://example.org/a.jpg",
        "http://i.ytimg.com/vi/abc/hqdefault.jpg",
        "https://evil-ytimg.com/a.jpg",
        "file:///etc/hosts",
        "fixture://thumbnail/abc",
    ):
        with pytest.raises(AppError) as failure:
            gateway.fetch_image(url)
        assert failure.value.code is ErrorCode.YOUTUBE_CHANGED

    assert len(fetched) == 3


@pytest.mark.parametrize(
    ("status", "content", "code"),
    [
        (429, b"x", ErrorCode.RATE_LIMITED),
        (500, b"x", ErrorCode.NETWORK_UNREACHABLE),
        (503, b"x", ErrorCode.NETWORK_UNREACHABLE),
        (404, b"x", ErrorCode.YOUTUBE_CHANGED),
        (200, b"", ErrorCode.YOUTUBE_CHANGED),
        (200, b"x" * 5_000_001, ErrorCode.YOUTUBE_CHANGED),
    ],
)
def test_an_answer_that_is_no_picture_is_an_error_with_a_code(
    status: int, content: bytes, code: ErrorCode
) -> None:
    """R-CH-16: a refused, missing, empty or huge picture is not cached."""
    with pytest.raises(AppError) as failure:
        checked_image("https://i.ytimg.com/vi/abc/a.jpg", status, content)

    assert failure.value.code is code


def test_a_fetched_picture_is_returned_as_it_came() -> None:
    """R-CH-16: the bytes of a picture are kept unchanged."""
    assert (
        checked_image("https://i.ytimg.com/vi/abc/a.jpg", 200, b"\xff\xd8jpeg") == b"\xff\xd8jpeg"
    )
