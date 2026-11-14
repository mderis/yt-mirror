"""Contract of the YouTubeGateway port, run against the fake and the real adapter.

The fake is the fixture adapter that the app can start with. The real
adapter is asked with recorded answers of yt-dlp in place of the network.
Both must behave the same in everything the services rely on.
"""

import itertools
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from tests.fixtures import ytdlp_replay
from tests.fixtures.fakes.clock import FakeClock
from ytmirror.adapters.fixture_youtube import THUMBNAIL_ADDRESS, FixtureYouTube
from ytmirror.adapters.ytdlp_gateway import YtDlpGateway
from ytmirror.core.channels import ChannelReference, ReferenceKind
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.ports.youtube_gateway import YouTubeGateway

VIDEOS = ytdlp_replay.RECORDED_VIDEOS


@dataclass(frozen=True)
class World:
    """One gateway with what the contract may expect of it.

    Attributes:
        gateway: The gateway under test.
        videos_read: Says how many videos of the last listing were handed out.
        break_listing_after: Makes the next listing fail after so many videos.
    """

    gateway: YouTubeGateway
    videos_read: Callable[[], int]
    break_listing_after: Callable[[int], None]


def fixture_world(folder: Path) -> World:
    """Return the fake YouTube with a channel shaped like the recorded one."""
    channel: dict[str, Any] = {
        "id": ytdlp_replay.CHANNEL_ID,
        "title": "Recorded Channel",
        "handle": ytdlp_replay.HANDLE,
        "listed_at": "2026-11-14T07:38:49Z",
        "video_count": 149,
        "generate": {"count": VIDEOS, "id_prefix": "rec", "title": "Recorded video {number}"},
        "checks": [],
    }
    empty: dict[str, Any] = {
        "id": ytdlp_replay.EMPTY_CHANNEL_ID,
        "title": "Recorded Channel",
        "listed_at": "2026-11-14T07:38:49Z",
        "video_count": {"fail": "YOUTUBE_CHANGED"},
        "videos": [],
    }
    file = folder / "recorded.json"

    def write() -> FixtureYouTube:
        file.write_text(json.dumps(channel), encoding="utf-8")
        (folder / "empty.json").write_text(json.dumps(empty), encoding="utf-8")
        return FixtureYouTube(folder)

    holder = {"youtube": write()}

    class Switching:
        """Passes every call on to the current fake, which a test can replace."""

        def __getattr__(self, name: str) -> object:
            return getattr(holder["youtube"], name)

    def break_after(count: int) -> None:
        channel["checks"] = [{"fail": "NETWORK_UNREACHABLE", "fail_after": count}]
        holder["youtube"] = write()
        list(holder["youtube"].list_channel(ytdlp_replay.CHANNEL_ID).videos)

    return World(
        gateway=Switching(),  # pyright: ignore[reportArgumentType]  (it passes every call on)
        videos_read=lambda: holder["youtube"].videos_served.get(ytdlp_replay.CHANNEL_ID, 0),
        break_listing_after=break_after,
    )


def ytdlp_world() -> World:
    """Return the real gateway, asked with the recorded answers of yt-dlp."""
    replay = ytdlp_replay.Replay()

    def break_after(count: int) -> None:
        replay.fail_after = (count, "ERROR: [youtube:tab] x: Incomplete data received")

    return World(
        gateway=YtDlpGateway(FakeClock(), extract=replay, http_get=lambda url: b"\x89PNG picture"),
        videos_read=lambda: replay.entries_read,
        break_listing_after=break_after,
    )


@pytest.fixture(params=["fixture", "ytdlp"])
def world(request: pytest.FixtureRequest, tmp_path: Path) -> World:
    """The fake and the real gateway, one after the other."""
    return fixture_world(tmp_path) if request.param == "fixture" else ytdlp_world()


def failure_of(call: Callable[[], object]) -> AppError:
    """Return the error with a code that a call raises."""
    with pytest.raises(AppError) as failure:
        call()
    return failure.value


def test_a_lookup_returns_the_facts_of_the_channel(world: World) -> None:
    """R-CH-03: a lookup gives the channel ID, the name, the handle and the avatar."""
    facts = world.gateway.lookup_channel(
        ChannelReference(ReferenceKind.HANDLE, ytdlp_replay.HANDLE)
    )

    assert facts.channel_id == ytdlp_replay.CHANNEL_ID
    assert facts.title == "Recorded Channel"
    assert facts.handle == ytdlp_replay.HANDLE
    assert facts.avatar_url


def test_a_lookup_reads_no_videos(world: World) -> None:
    """R-CH-03: looking a channel up does not list it."""
    world.gateway.lookup_channel(
        ChannelReference(ReferenceKind.CHANNEL_ID, ytdlp_replay.CHANNEL_ID)
    )

    assert world.videos_read() == 0


@pytest.mark.parametrize(
    "reference",
    [
        ChannelReference(ReferenceKind.HANDLE, ytdlp_replay.UNKNOWN_HANDLE),
        ChannelReference(ReferenceKind.CHANNEL_ID, ytdlp_replay.UNKNOWN_CHANNEL_ID),
    ],
)
def test_a_channel_that_youtube_does_not_have_is_not_found(
    world: World, reference: ChannelReference
) -> None:
    """R-CH-03: an unknown handle or channel ID is answered with CHANNEL_NOT_FOUND."""
    failure = failure_of(lambda: world.gateway.lookup_channel(reference))

    assert failure.code is ErrorCode.CHANNEL_NOT_FOUND


def test_a_listing_gives_the_channel_and_its_videos_newest_first(world: World) -> None:
    """R-CH-12, R-CH-10: a listing has the facts of the channel and every video, in order."""
    listing = world.gateway.list_channel(ytdlp_replay.CHANNEL_ID)

    videos = list(listing.videos)

    assert listing.facts.channel_id == ytdlp_replay.CHANNEL_ID
    assert len(videos) == VIDEOS
    assert len({video.id for video in videos}) == VIDEOS
    assert all(video.title and len(video.id) == 11 for video in videos)
    assert all(video.thumbnail_url and video.listed_at > 0 for video in videos)
    dates = [video.published_at for video in videos if video.published_at is not None]
    assert len(dates) == VIDEOS
    assert dates == sorted(dates, reverse=True)


def test_a_listing_asks_for_no_more_than_was_read(world: World) -> None:
    """R-CH-12: a reader that stops early costs no more than what it read."""
    listing = world.gateway.list_channel(ytdlp_replay.CHANNEL_ID)

    read = list(itertools.islice(listing.videos, 30))

    assert len(read) == 30
    assert world.videos_read() == 30


def test_a_listing_can_be_read_only_once(world: World) -> None:
    """R-CH-12: a listing is a reading of YouTube, not a stored list."""
    listing = world.gateway.list_channel(ytdlp_replay.CHANNEL_ID)
    list(listing.videos)

    assert list(listing.videos) == []


def test_a_listing_of_an_unknown_channel_is_not_found(world: World) -> None:
    """R-CH-12: a channel that YouTube no longer has cannot be listed."""
    failure = failure_of(lambda: world.gateway.list_channel(ytdlp_replay.UNKNOWN_CHANNEL_ID))

    assert failure.code is ErrorCode.CHANNEL_NOT_FOUND


def test_a_channel_without_regular_videos_has_an_empty_listing(world: World) -> None:
    """R-CH-07: a channel without regular videos lists nothing and is no error."""
    listing = world.gateway.list_channel(ytdlp_replay.EMPTY_CHANNEL_ID)

    assert listing.facts.channel_id == ytdlp_replay.EMPTY_CHANNEL_ID
    assert list(listing.videos) == []


def test_a_listing_that_breaks_fails_while_it_is_read(world: World) -> None:
    """R-CH-13: a listing that is cut off raises an error, it never looks complete."""
    world.break_listing_after(40)
    listing = world.gateway.list_channel(ytdlp_replay.CHANNEL_ID)

    read = list(itertools.islice(listing.videos, 40))
    failure = failure_of(lambda: next(listing.videos))

    assert len(read) == 40
    assert failure.code is ErrorCode.NETWORK_UNREACHABLE


def test_the_video_count_of_a_preview_is_a_number(world: World) -> None:
    """R-CH-03: the count of a channel is a whole number."""
    assert world.gateway.preview_video_count(ytdlp_replay.CHANNEL_ID) == 149


def test_a_missing_video_count_is_an_error_with_a_code(world: World) -> None:
    """R-CH-03: a count that YouTube does not give fails, so the caller shows none."""
    failure = failure_of(lambda: world.gateway.preview_video_count(ytdlp_replay.EMPTY_CHANNEL_ID))

    assert isinstance(failure.code, ErrorCode)


def test_the_pictures_a_listing_names_can_be_fetched(world: World) -> None:
    """R-CH-16: the thumbnail address of a listed video and the avatar lead to pictures."""
    listing = world.gateway.list_channel(ytdlp_replay.CHANNEL_ID)
    video = next(listing.videos)
    assert video.thumbnail_url is not None
    assert listing.facts.avatar_url is not None

    thumbnail = world.gateway.fetch_image(video.thumbnail_url)
    avatar = world.gateway.fetch_image(listing.facts.avatar_url)

    assert thumbnail.startswith(b"\x89PNG")
    assert avatar.startswith(b"\x89PNG")


@pytest.mark.parametrize("url", ["https://example.org/a.jpg", "file:///etc/hosts", ""])
def test_an_address_the_gateway_did_not_give_is_not_fetched(world: World, url: str) -> None:
    """R-HE-03: a gateway fetches pictures of YouTube only."""
    failure = failure_of(lambda: world.gateway.fetch_image(url))

    assert isinstance(failure.code, ErrorCode)


def test_the_fake_and_the_recorded_world_name_pictures_differently() -> None:
    """infra: the fake serves its own picture addresses, the real one those of YouTube."""
    assert THUMBNAIL_ADDRESS.startswith("fixture://")
