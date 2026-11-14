"""Tests of the fake YouTube that the app can start with, and of the fixture world it ships."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from ytmirror.adapters.fixture_youtube import AVATAR_ADDRESS, THUMBNAIL_ADDRESS, FixtureYouTube
from ytmirror.core.channels import ChannelReference, ReferenceKind
from ytmirror.core.errors import AppError, ErrorCode

WORLD = Path(__file__).resolve().parents[3] / "e2e" / "fixtures" / "youtube"
CHANGING = "UCchangingchannel0000005"
SMALL = "UCsmallchannel0000000001"
PNG = b"\x89PNG\r\n\x1a\n"


def world() -> FixtureYouTube:
    """Return the fake YouTube with the channels of the end-to-end tests."""
    return FixtureYouTube(WORLD)


def one_channel(folder: Path, **values: Any) -> FixtureYouTube:
    """Return a fake YouTube with one channel, described by the given values."""
    channel: dict[str, Any] = {
        "id": "UCtestchannel00000000001",
        "title": "Test Channel",
        "handle": "@testchannel",
        "listed_at": "2026-11-14T06:42:00Z",
        "video_count": 3,
        "videos": [
            {"id": f"test{number:07d}", "title": f"Test {number}", "point": "2026-11-05"}
            for number in (3, 2, 1)
        ],
    }
    channel.update(values)
    (folder / "test.json").write_text(json.dumps(channel), encoding="utf-8")
    return FixtureYouTube(folder)


def ids(youtube: FixtureYouTube, channel_id: str) -> list[str]:
    """Return the IDs of the next listing of a channel."""
    return [video.id for video in youtube.list_channel(channel_id).videos]


def test_the_world_has_the_channels_this_milestone_needs() -> None:
    """infra: small, tricky-titles, large, changing and empty exist (TESTING section 4)."""
    names = sorted(file.stem for file in WORLD.glob("*.json"))

    assert names == ["changing", "empty", "large", "small", "tricky-titles"]


def test_small_has_twelve_videos_newest_first() -> None:
    """infra: the default channel of most tests has 12 videos and a matching video count."""
    youtube = world()

    listing = youtube.list_channel(SMALL)

    assert listing.facts.title == "Sample Channel One"
    assert len(list(listing.videos)) == 12
    assert youtube.preview_video_count(SMALL) == 12


def test_large_has_five_thousand_generated_videos() -> None:
    """infra: the channel for performance has 5,000 videos with unique IDs of the usual length."""
    videos = list(world().list_channel("UClargechannel0000000003").videos)

    assert len(videos) == 5000
    assert len({video.id for video in videos}) == 5000
    assert {len(video.id) for video in videos} == {11}
    assert videos[0].title == "Generated video 5000"
    assert videos[0].published_at is not None
    assert videos[-1].published_at is not None
    assert videos[0].published_at > videos[-1].published_at


def test_empty_has_no_videos() -> None:
    """infra: a channel without regular videos lists nothing and is no error."""
    assert ids(world(), "UCemptychannel0000000004") == []


def test_tricky_titles_keep_their_titles_exactly() -> None:
    """infra: the titles with slashes, colons, emoji and other scripts are served unchanged."""
    titles = [video.title for video in world().list_channel("UCtrickytitles0000000002").videos]

    assert "AC/DC: Live at the workshop" in titles
    assert ".hidden gem" in titles
    assert titles.count("Same title") == 2
    assert any(len(title) > 255 for title in titles)


def test_a_channel_is_found_by_every_form_of_its_name() -> None:
    """infra: a fixture channel answers to its ID, its handle, and its custom and user name."""
    youtube = world()

    for kind, value in (
        (ReferenceKind.CHANNEL_ID, SMALL),
        (ReferenceKind.HANDLE, "@SampleChannelOne"),
        (ReferenceKind.CUSTOM_NAME, "samplechannelone"),
        (ReferenceKind.USER_NAME, "samplechannelone"),
    ):
        facts = youtube.lookup_channel(ChannelReference(kind, value))

        assert facts.channel_id == SMALL
        assert facts.handle == "@samplechannelone"
        assert facts.avatar_url == f"{AVATAR_ADDRESS}{SMALL}"


def test_an_unknown_channel_is_not_found() -> None:
    """infra: what no fixture names is answered as YouTube answers an unknown channel."""
    youtube = world()

    for call in (
        lambda: youtube.lookup_channel(ChannelReference(ReferenceKind.HANDLE, "@nobody")),
        lambda: youtube.list_channel("UCnobody0000000000000000"),
        lambda: youtube.preview_video_count("UCnobody0000000000000000"),
    ):
        with pytest.raises(AppError) as failure:
            call()
        assert failure.value.code is ErrorCode.CHANNEL_NOT_FOUND


def test_a_channel_without_a_custom_name_is_not_found_by_one() -> None:
    """infra: a form of the name that a fixture does not have matches nothing."""
    with pytest.raises(AppError):
        world().lookup_channel(ChannelReference(ReferenceKind.CUSTOM_NAME, "trickytitles"))


def test_a_lookup_can_be_made_to_fail(tmp_path: Path) -> None:
    """infra: a fixture can answer its lookup with an error code."""
    youtube = one_channel(tmp_path, lookup_fails="RATE_LIMITED")

    with pytest.raises(AppError) as failure:
        youtube.lookup_channel(ChannelReference(ReferenceKind.HANDLE, "@testchannel"))

    assert failure.value.code is ErrorCode.RATE_LIMITED


def test_the_video_count_can_be_present_fail_or_disagree() -> None:
    """infra: the world has a count that is right, one that fails and one that disagrees."""
    youtube = world()

    assert youtube.preview_video_count(SMALL) == len(ids(youtube, SMALL))
    with pytest.raises(AppError) as failure:
        youtube.preview_video_count("UCtrickytitles0000000002")
    assert failure.value.code is ErrorCode.NETWORK_UNREACHABLE
    assert youtube.preview_video_count(CHANGING) != len(ids(youtube, CHANGING))


def test_a_listing_is_handed_out_video_by_video_and_counted() -> None:
    """infra: the fake counts what a reader took, so a test can prove that reading stopped."""
    youtube = world()
    listing = youtube.list_channel("UClargechannel0000000003")

    taken = [next(listing.videos) for _ in range(30)]

    assert len(taken) == 30
    assert youtube.videos_served["UClargechannel0000000003"] == 30
    assert youtube.listings_started["UClargechannel0000000003"] == 1


def test_every_listing_of_changing_serves_the_next_step_of_its_script() -> None:
    """infra: new on top, new between known ones, new title, removed, failed, restored."""
    youtube = world()

    base = ids(youtube, CHANGING)
    with_new = ids(youtube, CHANGING)
    renamed = list(youtube.list_channel(CHANGING).videos)
    unchanged = [ids(youtube, CHANGING), ids(youtube, CHANGING)]
    with pytest.raises(AppError) as failure:
        youtube.list_channel(CHANGING)
    restored = ids(youtube, CHANGING)
    after_the_script = ids(youtube, CHANGING)

    assert len(base) == 45
    assert base[0] == "chg00000045"
    assert with_new[0] == "chgnew00001"
    assert with_new.index("chgnew00002") == with_new.index("chg00000041") - 1 == 5
    assert with_new.index("chgnew00003") == 42
    titles = {video.id: video.title for video in renamed}
    assert titles["chg00000044"] == "Episode 44, now with a better title"
    assert titles["chg00000003"] == "Episode 3, renamed far down the channel"
    assert "chg00000042" not in titles
    assert unchanged == [[video.id for video in renamed]] * 2
    assert failure.value.code is ErrorCode.NETWORK_UNREACHABLE
    assert restored.index("chg00000042") == with_new.index("chg00000042")
    assert after_the_script == restored


def test_a_listing_can_fail_part_of_the_way(tmp_path: Path) -> None:
    """infra: a step can cut a listing off after some videos, as a broken connection does."""
    youtube = one_channel(tmp_path, checks=[{"fail": "NETWORK_UNREACHABLE", "fail_after": 2}])
    list(youtube.list_channel("UCtestchannel00000000001").videos)

    listing = youtube.list_channel("UCtestchannel00000000001")
    read = [next(listing.videos), next(listing.videos)]
    with pytest.raises(AppError) as failure:
        next(listing.videos)

    assert [video.id for video in read] == ["test0000003", "test0000002"]
    assert failure.value.code is ErrorCode.NETWORK_UNREACHABLE


def test_a_listing_can_fail_at_its_end(tmp_path: Path) -> None:
    """infra: a failure after the last video is still a failed listing, not a complete one."""
    youtube = one_channel(tmp_path, checks=[{"fail": "YOUTUBE_CHANGED", "fail_after": 3}])
    list(youtube.list_channel("UCtestchannel00000000001").videos)
    listing = youtube.list_channel("UCtestchannel00000000001")

    with pytest.raises(AppError):
        list(listing.videos)


def test_a_video_without_a_point_has_no_date(tmp_path: Path) -> None:
    """infra: a fixture video can come without any date, for "date pending"."""
    youtube = one_channel(tmp_path, videos=[{"id": "test0000001", "title": "No date"}])

    video = next(youtube.list_channel("UCtestchannel00000000001").videos)

    assert video.published_at is None
    assert video.thumbnail_url == f"{THUMBNAIL_ADDRESS}test0000001"


def test_the_moment_of_the_listing_is_the_one_of_the_fixture() -> None:
    """infra: dates of the world do not move with the real clock, so screenshots stay the same."""
    video = next(world().list_channel(SMALL).videos)

    assert video.listed_at == 1794638520
    assert video.published_at == 1794592800


def test_pictures_are_png_images_that_differ_by_name() -> None:
    """infra: every thumbnail and avatar of the world is a small picture of its own colour."""
    youtube = world()

    thumbnail = youtube.fetch_image(f"{THUMBNAIL_ADDRESS}small000012")
    other = youtube.fetch_image(f"{THUMBNAIL_ADDRESS}small000011")
    avatar = youtube.fetch_image(f"{AVATAR_ADDRESS}{SMALL}")

    assert thumbnail.startswith(PNG)
    assert avatar.startswith(PNG)
    assert thumbnail != other
    assert thumbnail == youtube.fetch_image(f"{THUMBNAIL_ADDRESS}small000012")


def test_a_picture_from_anywhere_else_cannot_be_fetched() -> None:
    """infra: the fake never goes to the network for a picture."""
    with pytest.raises(AppError) as failure:
        world().fetch_image("https://i.ytimg.com/vi/abc/hqdefault.jpg")

    assert failure.value.code is ErrorCode.NETWORK_UNREACHABLE


def test_the_pictures_of_a_channel_can_be_made_to_fail(tmp_path: Path) -> None:
    """infra: a fixture can make its pictures unreachable."""
    youtube = one_channel(tmp_path, pictures_fail=True)

    with pytest.raises(AppError):
        youtube.fetch_image(f"{THUMBNAIL_ADDRESS}test0000001")
    with pytest.raises(AppError):
        youtube.fetch_image(f"{AVATAR_ADDRESS}UCtestchannel00000000001")


@pytest.mark.parametrize(
    "broken",
    [
        {"video_count": "many"},
        {"video_count": {"fail": "NOT_A_CODE"}},
        {"listed_at": "yesterday"},
        {"videos": [{"title": "no id"}]},
    ],
)
def test_a_file_that_describes_no_channel_is_refused(
    tmp_path: Path, broken: Mapping[str, Any]
) -> None:
    """infra: a mistake in a fixture file is reported with the name of the file."""
    with pytest.raises(ValueError, match="'test'"):
        one_channel(tmp_path, **broken)
