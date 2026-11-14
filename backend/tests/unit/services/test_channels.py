"""Tests of ``ytmirror.services.channels``: look up, add, pause, remove, open the folder."""

from pathlib import Path

import pytest
from structlog.testing import capture_logs

from tests.fixtures.world import BIG_ID, SMALL_ID, World, channel_file, log_lines
from ytmirror.core.channels import ChannelStatus, CheckKind, Quality
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.services.channels import COUNT_TIME_LIMIT_S, NewChannel

BIG = channel_file(BIG_ID, title="Big Channel", handle="@big", videos=40, prefix="big")


def failure_of(call: object) -> AppError:
    """Return the error with a code that a call raises."""
    with pytest.raises(AppError) as failure:
        call()  # pyright: ignore[reportCallIssue]
    return failure.value


# --- lookup


@pytest.mark.parametrize(
    "text",
    [
        "@small",
        "https://www.youtube.com/@small/videos",
        SMALL_ID,
        f"youtube.com/channel/{SMALL_ID}",
    ],
)
def test_a_channel_is_looked_up_from_what_the_user_pasted(tmp_path: Path, text: str) -> None:
    """R-CH-01, R-CH-03: the preview shows the name, the handle and the avatar of the channel."""
    world = World(tmp_path)

    looked_up = world.channels.lookup(text)

    assert looked_up.facts.channel_id == SMALL_ID
    assert (looked_up.facts.title, looked_up.facts.handle) == ("Small Channel", "@small")
    assert looked_up.facts.avatar_url
    assert looked_up.existing is False


def test_what_is_not_a_channel_is_refused_before_youtube_is_asked(tmp_path: Path) -> None:
    """R-CH-02: a video address is rejected with a reason, without a request to YouTube."""
    world = World(tmp_path)

    failure = failure_of(lambda: world.channels.lookup("https://youtu.be/abcdefghijk"))

    assert failure.code is ErrorCode.INVALID_CHANNEL_INPUT
    assert failure.details == {"reason": "video"}
    assert world.gateway.asked == []


def test_a_channel_that_youtube_does_not_have_is_not_found(tmp_path: Path) -> None:
    """R-CH-03: a handle nobody has is answered with CHANNEL_NOT_FOUND."""
    failure = failure_of(lambda: World(tmp_path).channels.lookup("@nobody"))

    assert failure.code is ErrorCode.CHANNEL_NOT_FOUND


def test_the_preview_says_where_the_channel_would_be_saved(tmp_path: Path) -> None:
    """R-CH-05: the default folder is the library folder plus the name of the channel."""
    world = World(tmp_path)

    looked_up = world.channels.lookup("@small")

    assert looked_up.folder == str(world.library / "Small Channel")
    assert looked_up.video_files == 0


def test_the_preview_says_how_many_video_files_the_folder_already_has(tmp_path: Path) -> None:
    """R-CH-06: video files that are already in the folder are counted for the dialog."""
    world = World(tmp_path)
    world.files.add_files(world.library / "Small Channel", ["a.mkv", "b.mp4", "notes.txt"])

    assert world.channels.lookup("@small").video_files == 2


def test_looking_up_a_channel_that_was_added_says_that_it_exists(tmp_path: Path) -> None:
    """R-CH-04: a channel that already exists is recognised when it is looked up again."""
    world = World(tmp_path)
    world.add_and_list()

    assert world.channels.lookup("@small").existing is True


# --- the video count of the preview


def test_the_video_count_arrives_apart_from_the_preview(tmp_path: Path) -> None:
    """R-CH-03: the preview is there before the count, and the count follows."""
    world = World(tmp_path)

    world.channels.lookup("@small")
    asked_in_the_background = len(world.background)
    world.run_background()

    assert asked_in_the_background == 1
    assert world.channels.video_count(SMALL_ID) == 5


def test_with_a_channel_id_the_count_is_asked_for_at_the_same_time_as_the_lookup(
    tmp_path: Path,
) -> None:
    """R-CH-03: when the pasted text has the channel ID, the count does not wait for the lookup."""
    world = World(tmp_path)
    order: list[str] = []
    real_lookup = world.gateway.lookup_channel
    world.gateway.lookup_channel = lambda reference: (  # pyright: ignore[reportAttributeAccessIssue]
        order.append(f"lookup with {len(world.background)} waiting") or real_lookup(reference)
    )

    world.channels.lookup(SMALL_ID)

    assert order == ["lookup with 1 waiting"]
    assert len(world.background) == 1


def test_a_count_that_fails_gives_a_preview_without_a_count_and_logs_why(tmp_path: Path) -> None:
    """R-CH-03: a failed count never fails the lookup. The reason is logged."""
    world = World(tmp_path, channel_file(count={"fail": "NETWORK_UNREACHABLE"}))

    with capture_logs() as logs:
        looked_up = world.channels.lookup("@small")
        world.run_background()
        count = world.channels.video_count(SMALL_ID)

    unavailable = log_lines(logs, "channel.count_unavailable")
    assert looked_up.facts.channel_id == SMALL_ID
    assert count is None
    assert unavailable[0]["error_code"] == "NETWORK_UNREACHABLE"
    assert unavailable[0]["channel_id"] == SMALL_ID


def test_a_count_that_takes_longer_than_eight_seconds_is_given_up(tmp_path: Path) -> None:
    """R-CH-03: after the time limit the preview goes without a count."""
    world = World(tmp_path)
    world.channels.lookup("@small")
    world.clock.advance(COUNT_TIME_LIMIT_S)

    with capture_logs() as logs:
        count = world.channels.video_count(SMALL_ID)

    assert count is None
    assert COUNT_TIME_LIMIT_S == 8.0
    assert "time limit" in str(log_lines(logs, "channel.count_unavailable")[0]["reason"])


@pytest.mark.parametrize("implausible", [-1, 1_000_001])
def test_an_implausible_count_is_not_shown(tmp_path: Path, implausible: int) -> None:
    """R-CH-03: a number that cannot be a count of videos is treated as no count."""
    world = World(tmp_path, channel_file(count=implausible))
    world.channels.lookup("@small")

    with capture_logs() as logs:
        world.run_background()

    assert world.channels.video_count(SMALL_ID) is None
    assert "plausible" in str(log_lines(logs, "channel.count_unavailable")[0]["reason"])


def test_a_channel_that_was_not_looked_up_has_no_count(tmp_path: Path) -> None:
    """R-CH-03: there is a count only for a preview that was asked for."""
    assert World(tmp_path).channels.video_count(SMALL_ID) is None


def test_the_count_is_asked_for_once_per_preview(tmp_path: Path) -> None:
    """R-CH-03: looking the same channel up twice asks for one count."""
    world = World(tmp_path)

    world.channels.lookup("@small")
    world.channels.lookup(SMALL_ID)
    world.run_background()

    assert world.gateway.asked.count("count") == 1


# --- adding


def test_adding_a_channel_stores_it_with_what_the_user_chose(tmp_path: Path) -> None:
    """R-CH-05: the folder, the quality and what to mirror are stored with the channel."""
    world = World(tmp_path)

    channel_id = world.add(quality=Quality.P1080, auto_mirror=True, mirror_after=1_700_000_000)

    channel = world.repository.channel(channel_id)
    assert channel is not None
    assert (channel.title, channel.handle) == ("Small Channel", "@small")
    assert channel.url == f"https://www.youtube.com/channel/{SMALL_ID}"
    assert (channel.folder, channel.folder_is_custom) == ("Small Channel", False)
    assert (channel.quality, channel.auto_mirror, channel.mirror_after) == (
        Quality.P1080,
        True,
        1_700_000_000,
    )


def test_by_default_the_user_picks_videos_and_the_default_quality_is_used(tmp_path: Path) -> None:
    """R-CH-05: the defaults are "use default" for the quality and "pick myself"."""
    world = World(tmp_path)

    channel = world.repository.channel(world.add())

    assert channel is not None
    assert (channel.quality, channel.auto_mirror, channel.mirror_after) == (None, False, None)


def test_adding_a_channel_creates_its_folder(tmp_path: Path) -> None:
    """R-FI-01: the channel folder is created when the channel is added."""
    world = World(tmp_path)

    world.add()

    assert world.files.folder_exists(world.library / "Small Channel") is True


def test_a_channel_can_be_saved_in_a_folder_the_user_chose_in_the_dialog(tmp_path: Path) -> None:
    """R-CH-05, R-CH-06: a chosen folder is used as it is, and its video files are counted."""
    world = World(tmp_path)
    chosen = tmp_path / "Elsewhere"
    world.picker.answer = chosen
    world.files.add_files(chosen, ["old.mkv"])

    picked = world.channels.choose_folder()
    channel_id = world.add(folder=str(chosen))

    channel = world.repository.channel(channel_id)
    assert picked is not None
    assert channel is not None
    assert (picked.folder, picked.video_files) == (str(chosen), 1)
    assert world.picker.asked_from == [world.library]
    assert (channel.folder, channel.folder_is_custom) == (str(chosen), True)
    assert world.views.of(channel_id).folder == str(chosen)  # pyright: ignore[reportOptionalMemberAccess]


def test_a_cancelled_folder_dialog_chooses_nothing(tmp_path: Path) -> None:
    """R-CH-05: Cancel in the dialog leaves the folder as it was."""
    assert World(tmp_path).channels.choose_folder() is None


def test_a_folder_that_did_not_come_from_the_dialog_is_refused(tmp_path: Path) -> None:
    """R-PL-04: the app accepts a path from the window only when the folder dialog gave it."""
    world = World(tmp_path)
    looked_up = world.channels.lookup("@small")

    failure = failure_of(
        lambda: world.channels.add(NewChannel(looked_up.facts.channel_id, folder="/etc"))
    )

    assert failure.code is ErrorCode.INVALID_REQUEST
    assert world.repository.channels() == ()


def test_a_channel_that_was_not_looked_up_cannot_be_added(tmp_path: Path) -> None:
    """R-CH-03: a channel is added only after its preview was shown."""
    failure = failure_of(lambda: World(tmp_path).channels.add(NewChannel(SMALL_ID)))

    assert failure.code is ErrorCode.INVALID_REQUEST


def test_adding_a_channel_that_exists_opens_the_existing_one(tmp_path: Path) -> None:
    """R-CH-04: adding a channel twice adds nothing and says that it exists."""
    world = World(tmp_path)
    channel_id = world.add_and_list()
    world.channels.lookup("@small")

    added = world.channels.add(NewChannel(channel_id, auto_mirror=True))

    assert added.existing is True
    assert added.view.channel.auto_mirror is False
    assert len(world.repository.channels()) == 1
    assert world.fixture.listings_started[SMALL_ID] == 1


def test_a_second_channel_with_the_same_name_gets_its_id_in_the_folder_name(
    tmp_path: Path,
) -> None:
    """R-FI-01: when the folder belongs to another channel, the channel ID is appended."""
    twin = channel_file(BIG_ID, title="Small Channel", handle="@twin", prefix="tw")
    world = World(tmp_path, channel_file(), twin)
    world.add_and_list("@small")

    looked_up = world.channels.lookup("@twin")
    world.add("@twin")

    assert looked_up.folder == str(world.library / f"Small Channel [{BIG_ID}]")
    assert world.repository.channel(BIG_ID).folder == f"Small Channel [{BIG_ID}]"  # pyright: ignore[reportOptionalMemberAccess]


def test_channels_are_put_at_the_end_of_the_sidebar(tmp_path: Path) -> None:
    """R-CH-34: a new channel follows the ones that are there."""
    world = World(tmp_path, channel_file(), BIG)

    world.add_and_list("@small")
    world.add_and_list("@big")

    assert [(view.channel.id, view.channel.position) for view in world.views.all()] == [
        (SMALL_ID, 0),
        (BIG_ID, 1),
    ]


@pytest.mark.parametrize(
    ("problem", "code"),
    [("denied", ErrorCode.PERMISSION_DENIED), ("unavailable", ErrorCode.FOLDER_UNAVAILABLE)],
)
def test_a_channel_whose_folder_cannot_be_created_is_not_added(
    tmp_path: Path, problem: str, code: ErrorCode
) -> None:
    """R-FI-01, R-ER-03: without its folder a channel is not added, and the reason is told."""
    world = World(tmp_path)
    getattr(world.files, problem).add(world.library / "Small Channel")
    looked_up = world.channels.lookup("@small")

    failure = failure_of(lambda: world.channels.add(NewChannel(looked_up.facts.channel_id)))

    assert failure.code is code
    assert world.repository.channels() == ()


def test_adding_a_channel_is_logged(tmp_path: Path) -> None:
    """R-LG-06: adding a channel is logged with its folder."""
    world = World(tmp_path)

    with capture_logs() as logs:
        world.add()

    added = log_lines(logs, "channel.added")[0]
    assert added["channel_id"] == SMALL_ID
    assert added["folder"] == str(world.library / "Small Channel")


# --- pause and resume


def test_pausing_a_channel_is_stored_and_shown(tmp_path: Path) -> None:
    """R-CH-30, R-CH-31: a channel can be paused, and its status says so."""
    world = World(tmp_path)
    channel_id = world.add_and_list()
    world.events.clear()

    with capture_logs() as logs:
        view = world.channels.set_paused(channel_id, True)

    assert view.channel.paused is True
    assert view.status is ChannelStatus.PAUSED
    assert world.repository.channel(channel_id).paused is True  # pyright: ignore[reportOptionalMemberAccess]
    assert [event.view.status for event in world.updates()] == [ChannelStatus.PAUSED]
    assert len(log_lines(logs, "channel.paused")) == 1


def test_resuming_a_channel_makes_it_checkable_again(tmp_path: Path) -> None:
    """R-CH-30: a paused channel can be resumed."""
    world = World(tmp_path)
    channel_id = world.add_and_list()
    world.channels.set_paused(channel_id, True)

    with capture_logs() as logs:
        view = world.channels.set_paused(channel_id, False)
    world.check(channel_id)

    assert view.status is ChannelStatus.UP_TO_DATE
    assert len(log_lines(logs, "channel.resumed")) == 1
    assert world.fixture.listings_started[SMALL_ID] == 2


def test_pausing_drops_the_checks_of_the_channel_that_wait(tmp_path: Path) -> None:
    """R-CH-31: a paused channel is not checked, also not by a check that was already asked for."""
    world = World(tmp_path)
    channel_id = world.add_and_list()
    world.catalogue.request_check(channel_id, CheckKind.QUICK)

    world.channels.set_paused(channel_id, True)
    world.work()

    assert world.fixture.listings_started[SMALL_ID] == 1
    assert world.views.is_checking(channel_id) is False


def test_a_channel_paused_during_its_first_listing_is_listed_when_it_is_resumed(
    tmp_path: Path,
) -> None:
    """R-CH-11, R-CH-31: pausing stops the first listing, and resuming starts it again."""
    world = World(tmp_path)
    channel_id = world.add()
    world.channels.set_paused(channel_id, True)
    world.work()
    assert world.ids(channel_id) == []

    world.channels.set_paused(channel_id, False)
    world.work()

    assert len(world.ids(channel_id)) == 5


def test_pausing_a_paused_channel_changes_nothing(tmp_path: Path) -> None:
    """infra: setting what is already set publishes and logs nothing."""
    world = World(tmp_path)
    channel_id = world.add_and_list()
    world.channels.set_paused(channel_id, True)
    world.events.clear()

    with capture_logs() as logs:
        world.channels.set_paused(channel_id, True)

    assert world.events == []
    assert log_lines(logs, "channel.paused") == []


# --- remove


def test_removing_a_channel_deletes_its_catalogue_and_keeps_its_folder(tmp_path: Path) -> None:
    """R-CH-32: the catalogue of the channel is deleted from the database, the files stay."""
    world = World(tmp_path, channel_file(), BIG)
    world.add_and_list("@small")
    world.add_and_list("@big")

    with capture_logs() as logs:
        world.channels.remove(SMALL_ID)

    removed = log_lines(logs, "channel.removed")[0]
    assert [channel.id for channel in world.repository.channels()] == [BIG_ID]
    assert world.repository.videos(SMALL_ID) == ()
    assert len(world.repository.videos(BIG_ID)) == 40
    assert world.files.folder_exists(world.library / "Small Channel") is True
    assert (removed["videos"], removed["folder"]) == (5, str(world.library / "Small Channel"))


def test_removing_a_channel_during_its_first_listing_stops_the_listing(tmp_path: Path) -> None:
    """R-CH-32: a channel can be removed while it is still being listed."""
    world = World(tmp_path)
    channel_id = world.add()

    world.channels.remove(channel_id)
    world.work()

    assert world.repository.channels() == ()
    assert world.repository.video("sm000000001") is None
    assert world.views.is_checking(channel_id) is False


def test_a_removed_channel_can_be_added_again(tmp_path: Path) -> None:
    """R-CH-32, R-ER-03: removing leaves nothing behind that stands in the way of adding again."""
    world = World(tmp_path)
    world.add_and_list()
    world.channels.remove(SMALL_ID)

    channel_id = world.add_and_list()

    assert len(world.ids(channel_id)) == 5


# --- open folder, unknown channels


def test_the_folder_of_a_channel_is_shown_in_finder(tmp_path: Path) -> None:
    """R-CH-30: "Open folder" shows the folder of the channel."""
    world = World(tmp_path)
    channel_id = world.add_and_list()

    world.channels.open_folder(channel_id)

    assert world.files.opened == [world.library / "Small Channel"]


@pytest.mark.parametrize("action", ["remove", "open_folder", "pause"])
def test_an_unknown_channel_is_not_found(tmp_path: Path, action: str) -> None:
    """R-CH-30: every action on a channel needs a channel that was added."""
    channels = World(tmp_path).channels
    calls = {
        "remove": lambda: channels.remove("UCunknown"),
        "open_folder": lambda: channels.open_folder("UCunknown"),
        "pause": lambda: channels.set_paused("UCunknown", True),
    }

    assert failure_of(calls[action]).code is ErrorCode.NOT_FOUND
