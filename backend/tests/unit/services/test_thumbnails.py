"""Tests of ``ytmirror.services.thumbnails``: the cache of pictures."""

from pathlib import Path

from structlog.testing import capture_logs

from tests.fixtures.world import BIG_ID, SMALL_ID, World, channel_file
from ytmirror.core.channels import CheckKind
from ytmirror.core.errors import ErrorCode
from ytmirror.ports.image_cache import ImageKind
from ytmirror.services.thumbnails import BATCH

BIG = channel_file(BIG_ID, title="Big Channel", handle="@big", videos=95, prefix="big")
PNG = b"\x89PNG"


def test_after_the_first_listing_every_thumbnail_and_the_avatar_are_cached(
    tmp_path: Path,
) -> None:
    """R-CH-16: the pictures of the catalogue are cached locally, all of them."""
    world = World(tmp_path)

    channel_id = world.add_and_list()

    assert (world.thumbnails.avatar(channel_id) or b"").startswith(PNG)
    assert all(
        (world.thumbnails.thumbnail(video_id) or b"").startswith(PNG)
        for video_id in world.ids(channel_id)
    )
    assert len(world.cache.pictures) == 6


def test_a_picture_that_is_not_cached_is_simply_missing(tmp_path: Path) -> None:
    """R-CH-16: asking for a picture never fetches it: it is cached or it is not there."""
    world = World(tmp_path)
    asked = list(world.gateway.asked)

    assert world.thumbnails.thumbnail("sm000000001") is None
    assert world.thumbnails.avatar(SMALL_ID) is None
    assert world.gateway.asked == asked


def test_the_list_works_offline_once_the_pictures_are_cached(tmp_path: Path) -> None:
    """R-CH-16: cached pictures are served when YouTube cannot be reached."""
    world = World(tmp_path)
    channel_id = world.add_and_list()
    world.gateway.refuse["image"] = ErrorCode.NETWORK_UNREACHABLE
    asked = world.gateway.asked.count("image")

    world.thumbnails.fill(channel_id)
    world.run_background()

    assert world.thumbnails.thumbnail("sm000000005") is not None
    assert world.gateway.asked.count("image") == asked


def test_the_thumbnail_of_a_removed_video_stays(tmp_path: Path) -> None:
    """R-CH-16: the list still shows the picture of a video that was removed from YouTube."""
    world = World(tmp_path, channel_file(checks=[{"remove": ["sm000000003"]}, {}]))
    channel_id = world.add_and_list()

    world.check(channel_id, CheckKind.FULL)
    world.check(channel_id, CheckKind.FULL)

    assert world.repository.video("sm000000003").gone is True  # pyright: ignore[reportOptionalMemberAccess]
    assert world.thumbnails.thumbnail("sm000000003") is not None


def test_pictures_are_fetched_newest_first_and_the_interface_is_told_in_groups(
    tmp_path: Path,
) -> None:
    """R-CH-16, R-FB-03: the newest videos get their pictures first, and the list hears of it."""
    world = World(tmp_path, BIG)
    channel_id = world.add("@big")
    world.run_background()
    world.catalogue.work_once()
    world.events.clear()
    fetched: list[str] = []
    real_fetch = world.fixture.fetch_image

    def recording(url: str) -> bytes:
        fetched.append(url.rsplit("/", 1)[-1])
        return real_fetch(url)

    world.fixture.fetch_image = recording  # pyright: ignore[reportAttributeAccessIssue]
    world.run_background()

    pictures = [event.view.pictures for event in world.updates()]
    assert fetched[:4] == [BIG_ID, "big00000095", "big00000094", "big00000093"]
    assert len(fetched) == 96
    assert pictures == [2, 3, 4, 5]
    assert BATCH == 24
    assert world.views.of(channel_id).pictures == 5  # pyright: ignore[reportOptionalMemberAccess]


def test_a_new_video_gets_its_picture_after_the_check_that_found_it(tmp_path: Path) -> None:
    """R-CH-16: every check is followed by fetching what is missing, and only that."""
    new = {"id": "smnew000001", "title": "New", "point": "2026-11-13"}
    world = World(tmp_path, channel_file(checks=[{"add": [new]}]))
    channel_id = world.add_and_list()
    before = world.gateway.asked.count("image")

    world.check(channel_id)

    assert world.thumbnails.thumbnail("smnew000001") is not None
    assert world.gateway.asked.count("image") == before + 1


def test_a_full_check_fetches_the_avatar_again(tmp_path: Path) -> None:
    """R-CH-12: a channel can change its avatar, and a full check takes the new one over."""
    world = World(tmp_path)
    channel_id = world.add_and_list()
    world.cache.store(ImageKind.AVATAR, channel_id, b"an old avatar")

    world.check(channel_id, CheckKind.QUICK)
    after_quick = world.thumbnails.avatar(channel_id)
    world.check(channel_id, CheckKind.FULL)

    assert after_quick == b"an old avatar"
    assert (world.thumbnails.avatar(channel_id) or b"").startswith(PNG)


def test_the_interface_is_told_when_the_avatar_was_cached_anew_and_only_then(
    tmp_path: Path,
) -> None:
    """R-CH-12, R-FB-03: a new avatar is told apart from more thumbnails."""
    world = World(tmp_path, BIG)
    channel_id = world.add_and_list("@big")
    after_listing = world.views.of(channel_id)
    world.events.clear()

    world.cache.pictures.pop((ImageKind.THUMBNAIL, "big00000001"))
    world.check(channel_id, CheckKind.QUICK)
    after_thumbnail = world.views.of(channel_id)
    world.check(channel_id, CheckKind.FULL)
    after_avatar = world.views.of(channel_id)

    assert after_listing is not None and after_thumbnail is not None and after_avatar is not None
    assert after_thumbnail.pictures > after_listing.pictures
    assert after_thumbnail.avatar_version == after_listing.avatar_version
    assert after_avatar.avatar_version == after_listing.avatar_version + 1


def test_pictures_that_fail_are_left_for_later_and_logged(tmp_path: Path) -> None:
    """R-CH-16: when pictures cannot be fetched the app stops trying this channel for now."""
    world = World(tmp_path, BIG)
    world.gateway.refuse["image"] = ErrorCode.NETWORK_UNREACHABLE

    with capture_logs() as logs:
        channel_id = world.add_and_list("@big")

    finished = [line for line in logs if line["event"] == "image.cache.finished"][-1]
    assert world.cache.pictures == {}
    assert world.gateway.asked.count("image") == 1 + 2 * BATCH
    assert (finished["stored"], finished["failed"], finished["left"]) == (0, 48, 48)
    assert finished["log_level"] == "warning"
    assert world.views.of(channel_id).pictures == 0  # pyright: ignore[reportOptionalMemberAccess]


def test_missing_pictures_are_fetched_at_the_next_start(tmp_path: Path) -> None:
    """R-CH-16: what could not be cached is tried again when the app starts."""
    world = World(tmp_path)
    world.gateway.refuse["image"] = ErrorCode.NETWORK_UNREACHABLE
    channel_id = world.add_and_list()
    world.gateway.refuse.clear()

    world.thumbnails.start()
    world.run_background()

    assert len(world.cache.pictures) == 6
    assert world.thumbnails.avatar(channel_id) is not None


def test_the_pause_of_the_app_holds_the_pictures_up_and_its_end_takes_them_up(
    tmp_path: Path,
) -> None:
    """R-ER-05: pictures are work the app does by itself: it waits for the pause and goes on."""
    second = channel_file(BIG_ID, title="Big Channel", handle="@big", videos=3, prefix="big")
    world = World(tmp_path, channel_file(), second)
    world.thumbnails.start()
    world.gateway.refuse["image"] = ErrorCode.BOT_CHECK
    world.add_and_list("@small")
    world.add_and_list("@big")
    asked = world.gateway.asked.count("image")
    world.gateway.refuse.clear()

    world.youtube.try_now()
    world.run_background()

    assert asked == 1
    assert len(world.cache.pictures) == 5 + 1 + 3 + 1


def test_the_pictures_of_a_removed_channel_are_dropped(tmp_path: Path) -> None:
    """R-CH-32: removing a channel removes its cached pictures, and only its own."""
    second = channel_file(BIG_ID, title="Big Channel", handle="@big", videos=3, prefix="big")
    world = World(tmp_path, channel_file(), second)
    world.add_and_list("@small")
    world.add_and_list("@big")

    world.channels.remove(SMALL_ID)

    assert world.thumbnails.avatar(SMALL_ID) is None
    assert world.thumbnails.thumbnail("sm000000001") is None
    assert len(world.cache.pictures) == 4


def test_a_channel_that_is_removed_before_its_pictures_were_fetched_is_skipped(
    tmp_path: Path,
) -> None:
    """R-CH-32: pictures that still wait for a removed channel are never fetched."""
    world = World(tmp_path)
    channel_id = world.add()
    world.catalogue.work_once()
    world.repository.remove_channel(channel_id)

    world.run_background()

    assert world.cache.pictures == {}


def test_asking_twice_for_the_same_channel_fetches_once(tmp_path: Path) -> None:
    """infra: a channel waits in line once, and one worker empties the line."""
    world = World(tmp_path)
    channel_id = world.add_and_list()
    world.cache.pictures.clear()

    world.thumbnails.fill(channel_id)
    world.thumbnails.fill(channel_id)
    started = len(world.background)
    world.run_background()

    assert started == 1
    assert len(world.cache.pictures) == 6
