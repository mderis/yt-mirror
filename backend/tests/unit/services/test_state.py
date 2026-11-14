"""Tests of ``ytmirror.services.state`` and of the channel views it shows."""

from pathlib import Path

import pytest

from tests.fixtures.world import BIG_ID, SMALL_ID, World, channel_file, new_video
from ytmirror.core.channels import ChannelStatus, CheckKind, TaskKind, TaskProgress
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.models import Settings
from ytmirror.core.status import NEW_FOR_S
from ytmirror.ports.file_system import Disk
from ytmirror.services.state import OPEN_CHANNEL_KEY

BIG = channel_file(BIG_ID, title="Big Channel", handle="@big", videos=40, prefix="big")


def test_a_new_app_has_no_channels_and_no_open_channel(tmp_path: Path) -> None:
    """R-UI-02: with no channels the snapshot is empty, which leads to the welcome screen."""
    state = World(tmp_path).state.snapshot()

    assert state.channels == ()
    assert state.open_channel_id is None
    assert state.youtube_pause is None


def test_the_snapshot_has_every_channel_in_the_order_of_the_sidebar(tmp_path: Path) -> None:
    """R-CH-34: the sidebar gets every channel with its name, status and count of new videos."""
    world = World(tmp_path, channel_file(checks=[{"add": [new_video("smnew000001")]}]), BIG)
    world.add_and_list("@small")
    world.add_and_list("@big")
    world.check(SMALL_ID)

    channels = world.state.snapshot().channels

    assert [(view.channel.title, view.status, view.totals.new) for view in channels] == [
        ("Small Channel", ChannelStatus.NEW_VIDEOS, 1),
        ("Big Channel", ChannelStatus.UP_TO_DATE, 0),
    ]


def test_the_totals_of_a_channel_are_in_its_view(tmp_path: Path) -> None:
    """R-CH-35: the header gets the videos, the synced and excluded ones and the size on disk."""
    world = World(tmp_path)
    channel_id = world.add_and_list()

    view = world.views.of(channel_id)

    assert view is not None
    assert (view.totals.videos, view.totals.synced, view.totals.excluded) == (5, 0, 0)
    assert view.totals.size_bytes == 0
    assert view.folder == str(world.library / "Small Channel")


def test_a_new_video_stops_being_new_after_fourteen_days(tmp_path: Path) -> None:
    """R-CH-15, R-CH-34: the count of new videos of a channel follows the clock."""
    world = World(tmp_path, channel_file(checks=[{"add": [new_video("smnew000001")]}]))
    channel_id = world.add_and_list()
    world.check(channel_id)

    world.clock.advance(NEW_FOR_S - 1)
    still_new = world.views.of(channel_id)
    world.clock.advance(1)
    no_longer = world.views.of(channel_id)

    assert still_new is not None
    assert no_longer is not None
    assert (still_new.totals.new, still_new.status) == (1, ChannelStatus.NEW_VIDEOS)
    assert (no_longer.totals.new, no_longer.status) == (0, ChannelStatus.UP_TO_DATE)


def test_the_channel_that_was_open_last_is_remembered(tmp_path: Path) -> None:
    """R-UI-02: the app opens on the channel that was open last."""
    world = World(tmp_path)
    channel_id = world.add_and_list()

    world.state.open_channel(channel_id)

    assert world.state.snapshot().open_channel_id == channel_id
    assert world.meta.get(OPEN_CHANNEL_KEY) == channel_id


def test_no_open_channel_is_remembered_too(tmp_path: Path) -> None:
    """R-UI-02: leaving every channel is remembered as well."""
    world = World(tmp_path)
    world.state.open_channel(world.add_and_list())

    world.state.open_channel(None)

    assert world.state.snapshot().open_channel_id is None


def test_an_open_channel_that_was_removed_is_forgotten(tmp_path: Path) -> None:
    """R-UI-02: the app never opens on a channel that is gone."""
    world = World(tmp_path)
    channel_id = world.add_and_list()
    world.state.open_channel(channel_id)

    world.channels.remove(channel_id)

    assert world.state.snapshot().open_channel_id is None


def test_an_unknown_channel_cannot_be_the_open_one(tmp_path: Path) -> None:
    """R-UI-02: only a channel that was added can be remembered as open."""
    with pytest.raises(AppError) as failure:
        World(tmp_path).state.open_channel("UCunknown")

    assert failure.value.code is ErrorCode.NOT_FOUND


def test_the_snapshot_names_the_library_and_the_free_space_of_its_disk(tmp_path: Path) -> None:
    """R-UI-01: the sidebar shows the free disk space of the disk the library is on."""
    world = World(tmp_path)
    world.files.disk = Disk("Media", 182_000_000_000)

    state = world.state.snapshot()

    assert state.library_folder == str(world.library)
    assert state.disk == Disk("Media", 182_000_000_000)


def test_the_library_folder_of_the_settings_decides_where_channels_are(tmp_path: Path) -> None:
    """R-FI-04: a channel folder is stored relative to the library, so the library can move."""
    world = World(tmp_path)
    channel_id = world.add_and_list()

    world.settings_repository.save(Settings(library_folder="/Volumes/Media/YouTube"))

    assert world.views.of(channel_id).folder == "/Volumes/Media/YouTube/Small Channel"  # pyright: ignore[reportOptionalMemberAccess]
    assert world.state.snapshot().library_folder == "/Volumes/Media/YouTube"


@pytest.mark.parametrize("has_window", [True, False])
def test_the_snapshot_says_whether_a_folder_can_be_chosen(tmp_path: Path, has_window: bool) -> None:
    """R-CH-05: without a window there is no folder dialog, and the interface offers none."""
    world = World(tmp_path)
    world.picker.has_window = has_window

    assert world.state.snapshot().can_choose_folder is has_window


def test_the_snapshot_carries_the_pause_of_the_app(tmp_path: Path) -> None:
    """R-ER-05, R-FB-04: a window that connects during the pause shows the banner."""
    world = World(tmp_path)
    world.gateway.refuse["lookup"] = ErrorCode.BOT_CHECK
    with pytest.raises(AppError):
        world.channels.lookup("@small")

    pause = world.state.snapshot().youtube_pause

    assert pause is not None
    assert (pause.code, pause.until) == (ErrorCode.BOT_CHECK, world.now() + 900)


def test_a_channel_that_waits_for_its_check_says_checking_at_once(tmp_path: Path) -> None:
    """R-FB-03, R-UI-11: asking for a check shows on the channel before the check starts."""
    world = World(tmp_path)
    channel_id = world.add_and_list()
    world.events.clear()

    world.catalogue.request_check(channel_id, CheckKind.QUICK)

    assert [event.view.status for event in world.updates()] == [ChannelStatus.CHECKING]
    world.work()
    assert world.updates()[-1].view.status is ChannelStatus.UP_TO_DATE


def test_the_progress_of_a_long_check_is_part_of_the_view_while_it_runs(tmp_path: Path) -> None:
    """R-CH-27: a window that connects during a full check sees how far it is."""
    world = World(tmp_path)
    channel_id = world.add_and_list()
    world.views.set_checking(channel_id, True)

    world.views.set_progress(TaskProgress(channel_id, TaskKind.FULL_CHECK, 30, 95))
    during = world.views.of(channel_id)
    world.views.set_checking(channel_id, False)

    assert during is not None
    assert during.progress == TaskProgress(channel_id, TaskKind.FULL_CHECK, 30, 95)
    assert world.views.of(channel_id).progress is None  # pyright: ignore[reportOptionalMemberAccess]


def test_a_channel_that_is_not_stored_has_no_view_and_is_not_published(tmp_path: Path) -> None:
    """R-CH-32: nothing is told about a channel that was removed."""
    world = World(tmp_path)

    world.views.publish("UCunknown")
    world.views.more_pictures("UCunknown")

    assert world.views.of("UCunknown") is None
    assert world.events == []
