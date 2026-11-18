"""Writers that read a row earlier never write back what another writer changed since.

The review of M5 found a check that stored its whole copy of the channel and
undid auto-mirror off, "Leave them missing" and "Only new videos from now
on". Each test here lets a writer read, another writer change its own field,
the first writer store, and checks that the other's field survived.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

from tests.fixtures.world import SMALL_ID, World
from ytmirror.core.auto_mirror import AutoMirrorAnswer
from ytmirror.core.channels import ChannelListing, VideoStatus
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.jobs import DownloadProgress


@pytest.fixture
def world(tmp_path: Path) -> World:
    """A world with the small channel added and listed."""
    world = World(tmp_path)
    world.add_and_list()
    return world


def while_listing(
    world: World, monkeypatch: pytest.MonkeyPatch, change: Callable[[], object], *, fail: bool
) -> None:
    """Run a check whose listing lets another writer change the channel meanwhile."""
    listing = world.gateway.list_channel

    def changed_meanwhile(channel_id: str) -> ChannelListing:
        change()
        if fail:
            raise AppError(ErrorCode.NETWORK_UNREACHABLE, {})
        return listing(channel_id)

    monkeypatch.setattr(world.gateway, "list_channel", changed_meanwhile)
    world.check(SMALL_ID)


@pytest.mark.parametrize("fail", [False, True], ids=["check stored", "check failed"])
def test_auto_mirror_turned_off_during_a_check_stays_off(
    world: World, monkeypatch: pytest.MonkeyPatch, fail: bool
) -> None:
    """R-MI-02, R-CH-12: the check stores only what it owns."""
    world.auto_mirror.set_auto_mirror(SMALL_ID, on=True)

    while_listing(
        world,
        monkeypatch,
        lambda: world.auto_mirror.set_auto_mirror(SMALL_ID, on=False),
        fail=fail,
    )

    assert world.repository.channel(SMALL_ID).auto_mirror is False  # type: ignore[union-attr]


@pytest.mark.parametrize("fail", [False, True], ids=["check stored", "check failed"])
def test_only_new_videos_chosen_during_a_check_keeps_its_date(
    world: World, monkeypatch: pytest.MonkeyPatch, fail: bool
) -> None:
    """R-MI-02, R-MI-03, D-095: "Only new videos from now on" is not undone by a check."""
    world.auto_mirror.set_auto_mirror(SMALL_ID, on=True)

    while_listing(
        world,
        monkeypatch,
        lambda: world.auto_mirror.answer(SMALL_ID, AutoMirrorAnswer.ONLY_NEW),
        fail=fail,
    )

    channel = world.repository.channel(SMALL_ID)
    assert channel is not None
    assert (channel.mirror_after, channel.auto_mirror_asked) != (None, False)
    assert channel.mirror_after is not None


@pytest.mark.parametrize("fail", [False, True], ids=["check stored", "check failed"])
def test_a_pause_during_a_check_stays(
    world: World, monkeypatch: pytest.MonkeyPatch, fail: bool
) -> None:
    """R-CH-31: pausing a channel while it is checked is kept."""
    while_listing(world, monkeypatch, lambda: world.channels.set_paused(SMALL_ID, True), fail=fail)

    assert world.repository.channel(SMALL_ID).paused is True  # type: ignore[union-attr]


def test_a_download_that_fails_never_takes_back_an_exact_date_found_meanwhile(
    world: World,
) -> None:
    """R-DT-05, R-QU-08: the exact-date fetch stores the date; the download's end keeps it."""
    video = world.repository.videos(SMALL_ID)[0]
    assert video.published_exact is False

    def date_found(_tell: Callable[[DownloadProgress], None]) -> None:
        assert world.date_repository.set_exact(video.id, 1_790_000_000)
        raise AppError(ErrorCode.MEMBERS_ONLY, {})

    world.downloader.mirror([video.id])
    world.download.during_video = date_found
    world.download_all()

    stored = world.repository.video(video.id)
    assert stored is not None
    assert stored.status is VideoStatus.FAILED
    assert (stored.published_at, stored.published_exact) == (1_790_000_000, True)
