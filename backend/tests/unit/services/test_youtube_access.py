"""Tests of ``ytmirror.services.youtube_access``: the pause of the whole app."""

from pathlib import Path

import pytest
from structlog.testing import capture_logs

from tests.fixtures.world import BIG_ID, SMALL_ID, World, channel_file
from ytmirror.adapters.fixture_youtube import THUMBNAIL_ADDRESS
from ytmirror.core.channels import ChannelReference, CheckKind, ReferenceKind
from ytmirror.core.errors import AppError, ErrorCode

SMALL = ChannelReference(ReferenceKind.HANDLE, "@small")
PICTURE = f"{THUMBNAIL_ADDRESS}sm000000001"
MINUTE = 60


def refused(world: World, kind: str = "lookup") -> World:
    """Let YouTube answer one kind of request with its "not a bot" check."""
    world.gateway.refuse[kind] = ErrorCode.BOT_CHECK
    return world


def bot_check(call: object) -> AppError:
    """Return the error of a call that must be refused with the "not a bot" check."""
    with pytest.raises(AppError) as failure:
        call()  # pyright: ignore[reportCallIssue]
    assert failure.value.code is ErrorCode.BOT_CHECK
    return failure.value


def test_without_a_refusal_there_is_no_pause(tmp_path: Path) -> None:
    """R-ER-05: an app that YouTube answers does not pause."""
    world = World(tmp_path)

    world.youtube.lookup_channel(SMALL)

    assert world.youtube.pause() is None
    assert world.pauses() == []


def test_the_not_a_bot_check_pauses_the_whole_app_for_a_quarter_of_an_hour(
    tmp_path: Path,
) -> None:
    """R-ER-05: after the check the app stops asking by itself, for 15 minutes at first."""
    world = refused(World(tmp_path))

    bot_check(lambda: world.youtube.lookup_channel(SMALL))

    pause = world.youtube.pause()
    assert pause is not None
    assert (pause.code, pause.until) == (ErrorCode.BOT_CHECK, world.now() + 15 * MINUTE)
    assert [event.pause for event in world.pauses()] == [pause]
    assert [delay for delay, _ in world.later] == [15 * MINUTE]


def test_while_the_app_pauses_it_asks_youtube_for_nothing_by_itself(tmp_path: Path) -> None:
    """R-ER-05: a picture or a check the app would start by itself is not even tried."""
    world = refused(World(tmp_path))
    bot_check(lambda: world.youtube.lookup_channel(SMALL))
    asked_before = list(world.gateway.asked)

    held_picture = bot_check(lambda: world.youtube.fetch_image(PICTURE))
    bot_check(lambda: world.youtube.list_channel(SMALL_ID, by_user=False))

    assert world.gateway.asked == asked_before
    assert held_picture.details == {"paused_until": str(world.now() + 15 * MINUTE)}


def test_what_the_user_starts_by_hand_is_still_tried(tmp_path: Path) -> None:
    """R-ER-05: an action of the user is tried during the pause, and its answer ends the pause."""
    world = refused(World(tmp_path))
    bot_check(lambda: world.youtube.lookup_channel(SMALL))
    world.gateway.refuse.clear()

    facts = world.youtube.lookup_channel(SMALL)

    assert facts.channel_id == SMALL_ID
    assert world.youtube.pause() is None
    assert [event.pause for event in world.pauses()][-1] is None


def test_an_answer_to_another_kind_of_request_does_not_end_the_pause(tmp_path: Path) -> None:
    """R-ER-05: YouTube can refuse lookups and still answer listings: a listing proves nothing."""
    world = refused(World(tmp_path))
    bot_check(lambda: world.youtube.lookup_channel(SMALL))

    listing = world.youtube.list_channel(SMALL_ID, by_user=True)

    assert len(list(listing.videos)) == 5
    assert world.youtube.pause() is not None


def test_every_further_refusal_doubles_the_pause_up_to_six_hours(tmp_path: Path) -> None:
    """R-ER-05: the pause grows: 15, 30, 60 minutes and so on, never beyond 6 hours."""
    world = refused(World(tmp_path))

    lengths: list[int] = []
    for _ in range(7):
        bot_check(lambda: world.youtube.lookup_channel(SMALL))
        pause = world.youtube.pause()
        assert pause is not None
        lengths.append((pause.until - world.now()) // MINUTE)

    assert lengths == [15, 30, 60, 120, 240, 360, 360]


def test_an_answer_of_youtube_starts_the_row_of_pauses_from_the_beginning(
    tmp_path: Path,
) -> None:
    """R-ER-05: once YouTube answered, the next pause is 15 minutes again."""
    world = refused(World(tmp_path))
    bot_check(lambda: world.youtube.lookup_channel(SMALL))
    bot_check(lambda: world.youtube.lookup_channel(SMALL))
    world.gateway.refuse.clear()
    world.youtube.lookup_channel(SMALL)
    world.gateway.refuse["lookup"] = ErrorCode.BOT_CHECK

    bot_check(lambda: world.youtube.lookup_channel(SMALL))

    pause = world.youtube.pause()
    assert pause is not None
    assert pause.until - world.now() == 15 * MINUTE


def test_when_the_time_of_the_pause_is_over_the_waiting_work_is_taken_up(
    tmp_path: Path,
) -> None:
    """R-ER-05: after the pause the app tries again what it held back."""
    world = refused(World(tmp_path))
    taken_up: list[str] = []
    world.youtube.when_asking_again(lambda: taken_up.append("pictures"))
    bot_check(lambda: world.youtube.lookup_channel(SMALL))
    world.clock.advance(15 * MINUTE)

    world.later[0][1]()

    assert world.youtube.pause() is None
    assert taken_up == ["pictures"]
    assert [event.pause for event in world.pauses()][-1] is None


def test_the_end_of_an_old_pause_does_not_end_a_newer_one(tmp_path: Path) -> None:
    """R-ER-05: a pause that was made longer is not cut short by the timer of the first one."""
    world = refused(World(tmp_path))
    bot_check(lambda: world.youtube.lookup_channel(SMALL))
    bot_check(lambda: world.youtube.lookup_channel(SMALL))
    longer = world.youtube.pause()

    world.later[0][1]()

    assert world.youtube.pause() == longer


def test_try_now_ends_the_pause_and_takes_the_work_up(tmp_path: Path) -> None:
    """R-ER-05, R-FB-04: the action of the banner makes the app try again at once."""
    world = refused(World(tmp_path))
    taken_up: list[str] = []
    world.youtube.when_asking_again(lambda: taken_up.append("first listings"))
    bot_check(lambda: world.youtube.lookup_channel(SMALL))

    world.youtube.try_now()
    world.youtube.try_now()

    assert world.youtube.pause() is None
    assert taken_up == ["first listings"]


def test_a_refusal_part_of_the_way_through_a_listing_pauses_as_well(tmp_path: Path) -> None:
    """R-ER-05: the check can come while a listing is read, and counts the same."""
    world = World(tmp_path, channel_file(BIG_ID, handle="@big", videos=95, prefix="big"))
    world.gateway.refuse["listing"] = ErrorCode.BOT_CHECK
    world.gateway.refuse_listing_after = 40
    listing = world.youtube.list_channel(BIG_ID, by_user=True)

    read = [next(listing.videos) for _ in range(40)]
    bot_check(lambda: next(listing.videos))

    assert len(read) == 40
    assert world.youtube.pause() is not None


@pytest.mark.parametrize("code", [ErrorCode.NETWORK_UNREACHABLE, ErrorCode.RATE_LIMITED])
def test_another_failure_does_not_pause_the_app(tmp_path: Path, code: ErrorCode) -> None:
    """R-ER-05: only the "not a bot" check is a condition of the whole app."""
    world = World(tmp_path)
    world.gateway.refuse["lookup"] = code
    world.gateway.refuse["image"] = code

    with pytest.raises(AppError):
        world.youtube.lookup_channel(SMALL)
    with pytest.raises(AppError):
        world.youtube.fetch_image(PICTURE)

    assert world.youtube.pause() is None


def test_the_video_count_goes_through_the_same_door(tmp_path: Path) -> None:
    """R-ER-05: the count of a preview is asked for the user, and a refusal of it pauses too."""
    world = World(tmp_path)
    assert world.youtube.preview_video_count(SMALL_ID) == 5
    world.gateway.refuse["count"] = ErrorCode.BOT_CHECK

    bot_check(lambda: world.youtube.preview_video_count(SMALL_ID))

    assert world.youtube.pause() is not None


def test_the_pause_and_its_end_are_logged_with_the_kind_of_request(tmp_path: Path) -> None:
    """R-LG-06: the log says which kind of request YouTube refused, and when the app goes on."""
    world = refused(World(tmp_path), "image")

    with capture_logs() as logs:
        bot_check(lambda: world.youtube.fetch_image(PICTURE))
        world.youtube.try_now()

    paused = next(line for line in logs if line["event"] == "youtube.paused")
    resumed = next(line for line in logs if line["event"] == "youtube.resumed")
    assert (paused["request"], paused["error_code"], paused["pause_s"]) == (
        "image",
        "BOT_CHECK",
        900,
    )
    assert paused["log_level"] == "warning"
    assert resumed["reason"] == "the user asked to try now"


def test_a_check_refused_with_the_bot_check_leaves_no_error_on_the_channel(
    tmp_path: Path,
) -> None:
    """R-ER-05: there is one banner for the app, never one error per channel."""
    third = channel_file("UCthirdthirdthirdthird03", title="Third", handle="@third", prefix="th")
    world = World(tmp_path, channel_file(), third)
    for handle in ("@small", "@third"):
        world.add_and_list(handle)
    world.gateway.refuse["listing"] = ErrorCode.BOT_CHECK

    world.catalogue.request_check_all()
    world.work()

    channels = world.repository.channels()
    assert [channel.last_check_error for channel in channels] == [None, None]
    assert world.gateway.asked.count("listing") == 3
    assert [world.views.is_checking(channel.id) for channel in channels] == [False, False]
    assert world.youtube.pause() is not None


def test_a_first_listing_that_was_refused_is_taken_up_when_the_pause_ends(
    tmp_path: Path,
) -> None:
    """R-ER-05, R-CH-11: the first listing waits for the pause and then runs by itself."""
    world = World(tmp_path)
    world.catalogue.start()
    world.background.clear()
    world.gateway.refuse["listing"] = ErrorCode.BOT_CHECK
    channel_id = world.add_and_list()
    assert world.ids(channel_id) == []
    world.gateway.refuse.clear()

    world.youtube.try_now()
    world.work()

    assert len(world.ids(channel_id)) == 5
    assert world.repository.channel(channel_id).last_check_error is None  # pyright: ignore[reportOptionalMemberAccess]


def test_a_check_that_the_app_starts_by_itself_waits_during_the_pause(tmp_path: Path) -> None:
    """R-ER-05: a check that no user started is not sent to YouTube while the app pauses."""
    world = World(tmp_path)
    channel_id = world.add_and_list()
    world.gateway.refuse["lookup"] = ErrorCode.BOT_CHECK
    bot_check(lambda: world.youtube.lookup_channel(SMALL))
    asked = world.gateway.asked.count("listing")

    world.catalogue.request_check(channel_id, CheckKind.QUICK, by_user=False)
    world.work()

    assert world.gateway.asked.count("listing") == asked
    assert world.repository.channel(channel_id).last_check_error is None  # pyright: ignore[reportOptionalMemberAccess]
