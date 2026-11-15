"""Tests of ``ytmirror.services.catalogue``: checks against the fake YouTube."""

import threading
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from structlog.testing import capture_logs

from tests.fixtures.catalogue import make_channel
from tests.fixtures.world import BIG_ID, SMALL_ID, World, channel_file, log_lines, new_video
from ytmirror.core.channels import (
    ChannelStatus,
    ChannelUpdated,
    CheckKind,
    CheckTrigger,
    TaskKind,
)
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.models import AppEvent
from ytmirror.services.catalogue import PROGRESS_EVERY, CatalogueService
from ytmirror.services.channel_views import ChannelViews

BIG = channel_file(BIG_ID, title="Big Channel", handle="@big", videos=95, prefix="big")


def big_with(*steps: dict[str, object]) -> dict[str, object]:
    """Return a channel of 95 videos with a script of changes."""
    return channel_file(
        BIG_ID, title="Big Channel", handle="@big", videos=95, prefix="big", checks=list(steps)
    )


# --- the first listing


def test_the_first_listing_fills_the_catalogue_in_the_background(tmp_path: Path) -> None:
    """R-CH-11: adding a channel returns at once, and its videos arrive in the background."""
    world = World(tmp_path)

    channel_id = world.add()
    before = world.views.of(channel_id)
    world.work()

    after = world.views.of(channel_id)
    assert before is not None
    assert after is not None
    assert (before.totals.videos, before.status) == (0, ChannelStatus.CHECKING)
    assert (after.totals.videos, after.status) == (5, ChannelStatus.UP_TO_DATE)
    assert world.ids(channel_id)[0] == "sm000000005"


def test_the_first_listing_is_a_full_check_and_sets_all_three_times(tmp_path: Path) -> None:
    """R-CH-26, R-CH-35: the first listing is a full check, and the channel knows when it was."""
    world = World(tmp_path)

    channel_id = world.add_and_list()

    channel = world.repository.channel(channel_id)
    assert channel is not None
    assert channel.first_listed_at == world.now()
    assert channel.last_check_at == world.now()
    assert channel.last_full_check_at == world.now()
    assert channel.last_check_error is None


def test_the_first_listing_tells_how_many_videos_it_found_so_far(tmp_path: Path) -> None:
    """R-CH-11: progress is published after every page: "30 videos found so far"."""
    world = World(tmp_path, BIG)

    channel_id = world.add_and_list("@big")

    steps = [
        (event.progress.kind, event.progress.done, event.progress.total)
        for event in world.progress()
    ]
    assert steps == [
        (TaskKind.FIRST_LISTING, 0, None),
        (TaskKind.FIRST_LISTING, 30, None),
        (TaskKind.FIRST_LISTING, 60, None),
        (TaskKind.FIRST_LISTING, 90, None),
    ]
    assert PROGRESS_EVERY == 30
    assert world.views.of(channel_id) is not None
    assert world.views.of(channel_id).progress is None  # pyright: ignore[reportOptionalMemberAccess]


def test_videos_of_the_first_listing_are_not_new(tmp_path: Path) -> None:
    """R-CH-15: the first listing brings no new videos."""
    world = World(tmp_path)

    channel_id = world.add_and_list()

    view = world.views.of(channel_id)
    assert view is not None
    assert view.totals.new == 0


def test_a_quick_check_of_a_channel_that_was_never_listed_is_its_first_listing(
    tmp_path: Path,
) -> None:
    """R-CH-11: whatever is asked for, a channel without a catalogue gets its first listing."""
    world = World(tmp_path, BIG)
    channel_id = world.add("@big")
    world.catalogue.forget(channel_id)

    world.check(channel_id, CheckKind.QUICK)

    channel = world.repository.channel(channel_id)
    assert channel is not None
    assert channel.first_listed_at is not None
    assert len(world.ids(channel_id)) == 95


def test_an_interrupted_first_listing_starts_again_at_the_next_start(tmp_path: Path) -> None:
    """R-CH-11: a first listing that a quit interrupted is taken up when the app starts."""
    world = World(tmp_path)
    channel_id = world.add()
    world.catalogue.forget(channel_id)
    world.run_background()
    assert world.ids(channel_id) == []

    world.catalogue.start()
    world.background.clear()  # the worker itself: the test lets the checks run by hand
    world.work()

    assert len(world.ids(channel_id)) == 5


def test_a_first_listing_that_failed_is_left_to_the_user(tmp_path: Path) -> None:
    """R-CH-25: a failed first listing waits for "Try again", it does not loop by itself."""
    world = World(tmp_path)
    world.gateway.refuse["listing"] = ErrorCode.NETWORK_UNREACHABLE
    channel_id = world.add_and_list()
    world.gateway.refuse.clear()

    world.catalogue.resume_first_listings()
    world.work()

    view = world.views.of(channel_id)
    assert view is not None
    assert view.status is ChannelStatus.COULD_NOT_CHECK
    assert world.ids(channel_id) == []


def test_the_first_listing_logs_a_count_that_differs_from_the_preview(tmp_path: Path) -> None:
    """R-LG-06: the catalogue is the source of truth, and a different preview count is logged."""
    world = World(tmp_path, channel_file(count=57))

    with capture_logs() as logs:
        world.add_and_list()

    differs = log_lines(logs, "channel.count_differs")
    assert len(differs) == 1
    assert (differs[0]["preview_count"], differs[0]["listed"]) == (57, 5)


def test_a_preview_count_that_agrees_is_not_logged(tmp_path: Path) -> None:
    """R-LG-06: nothing is said when the preview and the listing agree."""
    world = World(tmp_path)

    with capture_logs() as logs:
        world.add_and_list()

    assert log_lines(logs, "channel.count_differs") == []


# --- quick checks


def test_check_now_finds_a_new_video_and_counts_it_as_new(tmp_path: Path) -> None:
    """R-CH-23, R-CH-12, R-CH-15: a quick check adds a new video, and the channel says so."""
    world = World(tmp_path, big_with({"add": [new_video("bignew00001")]}))
    channel_id = world.add_and_list("@big")

    world.check(channel_id)

    view = world.views.of(channel_id)
    assert view is not None
    assert world.ids(channel_id)[0] == "bignew00001"
    assert (view.totals.videos, view.totals.new) == (96, 1)
    assert view.status is ChannelStatus.NEW_VIDEOS


def test_a_quick_check_reads_only_the_top_of_a_large_channel(tmp_path: Path) -> None:
    """R-CH-12: a quick check stops after a full page of known videos."""
    world = World(tmp_path, big_with({"add": [new_video("bignew00001")]}))
    channel_id = world.add_and_list("@big")

    world.check(channel_id)

    assert world.fixture.videos_served[BIG_ID] == 31


def test_a_quick_check_finds_a_new_video_between_two_older_known_ones(tmp_path: Path) -> None:
    """R-CH-12: a new video that appears between known ones near the top is found and placed."""
    world = World(tmp_path, big_with({"add": [new_video("bignew00001", before="big00000090")]}))
    channel_id = world.add_and_list("@big")

    world.check(channel_id)

    ids = world.ids(channel_id)
    assert ids.index("bignew00001") == ids.index("big00000090") - 1 == 5
    assert len(ids) == 96


def test_a_quick_check_misses_a_new_video_far_down_and_the_full_check_finds_it(
    tmp_path: Path,
) -> None:
    """R-CH-12: what lies below a full page of known videos is found by the next full check."""
    world = World(tmp_path, big_with({"add": [new_video("bignew00001", before="big00000010")]}, {}))
    channel_id = world.add_and_list("@big")

    world.check(channel_id, CheckKind.QUICK)
    after_quick = world.ids(channel_id)
    world.check(channel_id, CheckKind.FULL)

    assert "bignew00001" not in after_quick
    assert world.ids(channel_id).index("bignew00001") == 85


def test_a_quick_check_updates_a_title_near_the_top(tmp_path: Path) -> None:
    """R-CH-12: the title of a video that a quick check read is updated."""
    world = World(tmp_path, big_with({"retitle": {"big00000094": "A better title"}}))
    channel_id = world.add_and_list("@big")

    world.check(channel_id)

    assert world.titles(channel_id)[1] == "A better title"


def test_quick_checks_never_mark_a_video_as_removed(tmp_path: Path) -> None:
    """R-CH-13: a video that vanished is not marked by quick checks, however many run."""
    world = World(tmp_path, big_with({"remove": ["big00000093"]}, {}, {}))
    channel_id = world.add_and_list("@big")

    for _ in range(3):
        world.check(channel_id, CheckKind.QUICK)

    video = world.repository.video("big00000093")
    assert video is not None
    assert (video.missing_checks, video.gone) == (0, False)
    assert world.ids(channel_id).index("big00000093") == 2


def test_a_quick_check_sets_the_last_check_and_leaves_the_last_full_check(tmp_path: Path) -> None:
    """R-CH-35: the channel knows its last check and its last full check apart."""
    world = World(tmp_path, BIG)
    channel_id = world.add_and_list("@big")
    listed_at = world.now()
    world.clock.advance(600)

    world.check(channel_id, CheckKind.QUICK)

    channel = world.repository.channel(channel_id)
    assert channel is not None
    assert channel.last_check_at == listed_at + 600
    assert channel.last_full_check_at == listed_at
    assert not world.progress()[4:]


# --- full checks


def test_a_video_is_removed_only_after_two_full_checks_without_it(tmp_path: Path) -> None:
    """R-CH-13, R-CH-14: the second full check in a row marks it, and it stays in the list."""
    world = World(tmp_path, big_with({"remove": ["big00000093"]}, {}, {}, {}))
    channel_id = world.add_and_list("@big")

    world.check(channel_id, CheckKind.FULL)
    after_one = world.repository.video("big00000093")
    world.check(channel_id, CheckKind.QUICK)
    after_a_quick_one = world.repository.video("big00000093")
    world.check(channel_id, CheckKind.FULL)
    after_two = world.repository.video("big00000093")

    assert after_one is not None
    assert after_a_quick_one is not None
    assert after_two is not None
    assert (after_one.missing_checks, after_one.gone) == (1, False)
    assert (after_a_quick_one.missing_checks, after_a_quick_one.gone) == (1, False)
    assert (after_two.missing_checks, after_two.gone) == (2, True)
    assert world.ids(channel_id).index("big00000093") == 2


def test_a_removed_video_that_comes_back_is_no_longer_removed(tmp_path: Path) -> None:
    """R-CH-13: a video that is listed again is no longer removed from YouTube."""
    world = World(tmp_path, big_with({"remove": ["big00000093"]}, {}, {"restore": ["big00000093"]}))
    channel_id = world.add_and_list("@big")
    world.check(channel_id, CheckKind.FULL)
    world.check(channel_id, CheckKind.FULL)

    world.check(channel_id, CheckKind.QUICK)

    video = world.repository.video("big00000093")
    assert video is not None
    assert (video.missing_checks, video.gone) == (0, False)


def test_a_full_check_finds_a_new_title_far_down_the_channel(tmp_path: Path) -> None:
    """R-CH-12: only a full check finds a changed title on an older video."""
    world = World(tmp_path, big_with({"retitle": {"big00000003": "Renamed far down"}}, {}))
    channel_id = world.add_and_list("@big")

    world.check(channel_id, CheckKind.QUICK)
    after_quick = world.titles(channel_id)[92]
    world.check(channel_id, CheckKind.FULL)

    assert after_quick == "Video 3"
    assert world.titles(channel_id)[92] == "Renamed far down"


def test_a_full_check_tells_its_progress_against_the_size_of_the_catalogue(
    tmp_path: Path,
) -> None:
    """R-CH-27: a full check shows "Full check: 30 of about 95"."""
    world = World(tmp_path, BIG)
    channel_id = world.add_and_list("@big")
    world.events.clear()

    world.check(channel_id, CheckKind.FULL)

    steps = [
        (event.progress.kind, event.progress.done, event.progress.total)
        for event in world.progress()
    ]
    assert steps == [(TaskKind.FULL_CHECK, done, 95) for done in (0, 30, 60, 90)]


def test_a_cancelled_full_check_changes_nothing(tmp_path: Path) -> None:
    """R-CH-27: a full check can be cancelled while it reads, and then nothing is stored."""
    world = World(tmp_path, big_with({"add": [new_video("bignew00001")]}))
    channel_id = world.add_and_list("@big")
    before = world.repository.channel(channel_id)
    world.clock.advance(600)
    world.at_progress(30, lambda: world.catalogue.cancel(channel_id))

    with capture_logs() as logs:
        world.check(channel_id, CheckKind.FULL)

    assert world.repository.channel(channel_id) == before
    assert "bignew00001" not in world.ids(channel_id)
    assert len(log_lines(logs, "check.cancelled")) == 1
    assert log_lines(logs, "check.finished") == []
    assert world.views.is_checking(channel_id) is False


def test_a_full_check_that_waits_can_be_cancelled_before_it_starts(tmp_path: Path) -> None:
    """R-CH-27: cancelling a full check that did not start yet takes it out of the line."""
    world = World(tmp_path, BIG)
    channel_id = world.add_and_list("@big")
    world.catalogue.request_check(channel_id, CheckKind.FULL)

    cancelled = world.catalogue.cancel(channel_id)

    assert cancelled is True
    assert world.catalogue.work_once() is False
    assert world.views.is_checking(channel_id) is False
    assert world.catalogue.cancel(channel_id) is False


def test_a_first_listing_cannot_be_cancelled(tmp_path: Path) -> None:
    """R-CH-27: only a full check of a listed channel is cancelled. A first listing goes on."""
    world = World(tmp_path)
    channel_id = world.add()

    assert world.catalogue.cancel(channel_id) is False
    assert world.catalogue.cancel("UCunknown") is False
    world.work()
    assert len(world.ids(channel_id)) == 5


# --- failures


def test_a_failed_check_keeps_the_catalogue_and_marks_the_channel(tmp_path: Path) -> None:
    """R-CH-25, R-CH-13: a failed check changes nothing and leaves its error on the channel."""
    world = World(tmp_path, big_with({"fail": "NETWORK_UNREACHABLE"}, {}))
    channel_id = world.add_and_list("@big")
    before = world.repository.videos(channel_id)

    with capture_logs() as logs:
        world.check(channel_id, CheckKind.FULL)

    view = world.views.of(channel_id)
    failed = log_lines(logs, "check.failed")
    assert view is not None
    assert world.repository.videos(channel_id) == before
    assert view.channel.last_check_error is ErrorCode.NETWORK_UNREACHABLE
    assert view.status is ChannelStatus.COULD_NOT_CHECK
    assert failed[0]["error_code"] == "NETWORK_UNREACHABLE"
    assert failed[0]["kind"] == "full"


def test_a_listing_that_breaks_part_of_the_way_counts_nothing_as_missing(tmp_path: Path) -> None:
    """R-CH-13: a listing that was cut off is a failed check, not a shorter channel."""
    world = World(tmp_path, big_with({"fail": "NETWORK_UNREACHABLE", "fail_after": 40}))
    channel_id = world.add_and_list("@big")

    world.check(channel_id, CheckKind.FULL)

    videos = world.repository.videos(channel_id)
    assert len(videos) == 95
    assert all(video.missing_checks == 0 for video in videos)


def test_try_again_after_a_failed_check_clears_the_error(tmp_path: Path) -> None:
    """R-CH-25: the retry button checks again, and a check that works takes the error away."""
    world = World(tmp_path, big_with({"fail": "RATE_LIMITED"}, {"add": [new_video("bignew00001")]}))
    channel_id = world.add_and_list("@big")
    world.check(channel_id)

    world.check(channel_id)

    view = world.views.of(channel_id)
    assert view is not None
    assert view.channel.last_check_error is None
    assert world.ids(channel_id)[0] == "bignew00001"


def test_an_empty_full_listing_of_a_channel_with_videos_is_a_failed_check(
    tmp_path: Path,
) -> None:
    """R-CH-13: an empty check never marks anything as removed."""
    removed = [f"sm{number:09d}" for number in range(1, 6)]
    world = World(tmp_path, channel_file(checks=[{"remove": removed}]))
    channel_id = world.add_and_list()

    world.check(channel_id, CheckKind.FULL)

    view = world.views.of(channel_id)
    assert view is not None
    assert view.channel.last_check_error is ErrorCode.YOUTUBE_CHANGED
    assert all(
        not video.gone and video.missing_checks == 0
        for video in world.repository.videos(channel_id)
    )


def test_a_channel_without_videos_has_an_empty_catalogue_and_no_error(tmp_path: Path) -> None:
    """R-CH-07: a channel without regular videos is listed as empty, and that is no failure."""
    world = World(tmp_path, channel_file(videos=0))

    channel_id = world.add_and_list()

    view = world.views.of(channel_id)
    assert view is not None
    assert (view.totals.videos, view.status) == (0, ChannelStatus.UP_TO_DATE)
    assert view.channel.first_listed_at is not None


def test_an_unexpected_error_in_a_check_is_logged_and_shown_as_internal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-ER-03: a check that breaks in an unforeseen way leaves a channel that can be retried."""
    world = World(tmp_path)
    channel_id = world.add_and_list()

    def breaks(channel: object, changes: object) -> bool:
        raise RuntimeError("unforeseen")

    monkeypatch.setattr(world.repository, "apply_check", breaks)

    with capture_logs() as logs:
        world.check(channel_id)

    failed = log_lines(logs, "check.failed")
    view = world.views.of(channel_id)
    assert view is not None
    assert failed[0]["error_code"] == "INTERNAL"
    assert failed[0]["log_level"] == "error"
    assert view.channel.last_check_error is ErrorCode.INTERNAL
    assert world.views.is_checking(channel_id) is False


def test_a_check_takes_over_the_new_name_of_a_channel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-CH-12: a successful check takes over the channel's current name, handle and avatar."""
    world = World(tmp_path)
    channel_id = world.add_and_list()
    facts = world.fixture.lookup_channel
    real_listing = world.fixture.list_channel

    def renamed(channel: str) -> object:
        listing = real_listing(channel)
        new_facts = type(listing.facts)(channel, "A New Name", "@newhandle", "fixture://avatar/new")
        return type(listing)(new_facts, listing.videos)

    monkeypatch.setattr(world.fixture, "list_channel", renamed)

    world.check(channel_id)

    channel = world.repository.channel(channel_id)
    assert facts is not None
    assert channel is not None
    assert (channel.title, channel.handle, channel.avatar_url) == (
        "A New Name",
        "@newhandle",
        "fixture://avatar/new",
    )
    assert channel.folder == "Small Channel"


# --- which checks run


def test_a_paused_channel_is_not_checked_by_hand_either(tmp_path: Path) -> None:
    """R-CH-31: a paused channel is not checked, neither automatically nor by hand."""
    world = World(tmp_path)
    channel_id = world.add_and_list()
    world.channels.set_paused(channel_id, True)

    with pytest.raises(AppError) as refused:
        world.catalogue.request_check(channel_id, CheckKind.QUICK)

    assert refused.value.code is ErrorCode.INVALID_REQUEST
    assert refused.value.details["reason"] == "paused"


def test_a_check_of_an_unknown_channel_is_refused(tmp_path: Path) -> None:
    """R-ER-02: only a channel that was added can be checked."""
    with pytest.raises(AppError) as refused:
        World(tmp_path).catalogue.request_check("UCunknown", CheckKind.QUICK)

    assert refused.value.code is ErrorCode.NOT_FOUND


def test_check_all_checks_every_channel_that_is_not_paused_one_after_another(
    tmp_path: Path,
) -> None:
    """R-CH-23, R-CH-24: "Check all channels now" checks them one by one, paused ones not."""
    third = channel_file("UCthirdthirdthirdthird03", title="Third", handle="@third", prefix="th")
    world = World(tmp_path, channel_file(), BIG, third)
    for handle in ("@small", "@big", "@third"):
        world.add_and_list(handle)
    world.channels.set_paused(BIG_ID, True)
    started = dict(world.fixture.listings_started)

    asked = world.catalogue.request_check_all()
    waiting_together = [world.views.is_checking(SMALL_ID), world.views.is_checking(third["id"])]
    ran = [world.catalogue.work_once(), world.catalogue.work_once(), world.catalogue.work_once()]

    assert asked == 2
    assert waiting_together == [True, True]
    assert ran == [True, True, False]
    assert world.fixture.listings_started[SMALL_ID] == started[SMALL_ID] + 1
    assert world.fixture.listings_started[BIG_ID] == started[BIG_ID]


def test_check_all_runs_a_quick_check_of_every_channel_and_no_full_one(tmp_path: Path) -> None:
    """R-CH-23, R-CH-12: "Check all channels now" runs quick checks, never a full check."""
    world = World(tmp_path, channel_file(), BIG)
    for handle in ("@small", "@big"):
        world.add_and_list(handle)
    full_checks_before = {
        channel_id: world.repository.channel(channel_id).last_full_check_at  # pyright: ignore[reportOptionalMemberAccess]
        for channel_id in (SMALL_ID, BIG_ID)
    }
    world.clock.advance(60)

    with capture_logs() as logs:
        world.catalogue.request_check_all()
        world.work()

    started = [
        (line["channel_id"], line["kind"], line["first_listing"])
        for line in log_lines(logs, "check.started")
    ]
    assert sorted(started) == sorted([(SMALL_ID, "quick", False), (BIG_ID, "quick", False)])
    for channel_id, full_check_before in full_checks_before.items():
        channel = world.repository.channel(channel_id)
        assert channel is not None
        assert channel.last_check_at == world.now()
        assert channel.last_full_check_at == full_check_before != world.now()


def test_a_check_that_already_waits_is_not_put_in_line_twice(tmp_path: Path) -> None:
    """R-CH-24: asking twice for the same channel runs one check."""
    world = World(tmp_path, BIG)
    channel_id = world.add_and_list("@big")

    world.catalogue.request_check(channel_id, CheckKind.QUICK)
    world.catalogue.request_check(channel_id, CheckKind.QUICK)

    assert [world.catalogue.work_once(), world.catalogue.work_once()] == [True, False]


def test_a_waiting_quick_check_becomes_a_full_one_when_a_full_one_is_asked_for(
    tmp_path: Path,
) -> None:
    """R-CH-23, R-CH-24: "Full check" on top of a waiting "Check now" runs one full check."""
    world = World(tmp_path, BIG)
    channel_id = world.add_and_list("@big")
    world.clock.advance(60)

    world.catalogue.request_check(channel_id, CheckKind.QUICK)
    world.catalogue.request_check(channel_id, CheckKind.FULL)
    world.catalogue.request_check(channel_id, CheckKind.QUICK)
    world.work()

    channel = world.repository.channel(channel_id)
    assert channel is not None
    assert channel.last_full_check_at == world.now()
    assert world.fixture.listings_started[BIG_ID] == 2


def test_a_check_asked_for_while_one_runs_is_not_put_in_line(tmp_path: Path) -> None:
    """R-CH-24: a channel that is being checked is not checked again right behind it."""
    world = World(tmp_path, BIG)
    channel_id = world.add_and_list("@big")
    world.at_progress(30, lambda: world.catalogue.request_check(channel_id, CheckKind.FULL))

    world.check(channel_id, CheckKind.FULL)

    assert world.fixture.listings_started[BIG_ID] == 2


def test_a_check_of_a_channel_that_was_removed_meanwhile_does_nothing(tmp_path: Path) -> None:
    """R-CH-32: a check that waits for a removed channel is dropped."""
    world = World(tmp_path)
    channel_id = world.add_and_list()
    world.catalogue.request_check(channel_id, CheckKind.QUICK)

    world.repository.remove_channel(channel_id)
    ran = world.catalogue.work_once()

    assert ran is True
    assert world.fixture.listings_started[SMALL_ID] == 1


def test_a_check_whose_channel_is_removed_while_it_reads_stores_nothing(tmp_path: Path) -> None:
    """R-CH-32: a check that ends after its channel was removed leaves no catalogue behind."""
    world = World(tmp_path, BIG)
    channel_id = world.add("@big")
    world.at_progress(30, lambda: world.repository.remove_channel(channel_id))

    with capture_logs() as logs:
        world.work()

    assert world.repository.video("big00000095") is None
    assert log_lines(logs, "check.finished") == []


def test_every_check_logs_its_start_and_its_end_with_the_counts(tmp_path: Path) -> None:
    """R-LG-06: a check logs when it starts and when it ends, with what it found."""
    world = World(tmp_path, big_with({"add": [new_video("bignew00001")]}))
    channel_id = world.add_and_list("@big")
    world.clock.advance(2)

    with capture_logs() as logs:
        world.check(channel_id)

    started, finished = log_lines(logs, "check.started")[0], log_lines(logs, "check.finished")[0]
    assert (started["channel_id"], started["kind"], started["first_listing"]) == (
        BIG_ID,
        "quick",
        False,
    )
    assert (finished["new"], finished["read"], finished["gone"]) == (1, 31, 0)
    assert finished["duration_ms"] == 0


# --- the worker


def test_the_worker_runs_checks_in_a_thread_until_it_is_stopped(tmp_path: Path) -> None:
    """R-PL-13, R-CH-11: the worker takes checks while the app runs and ends when it stops."""
    world = World(tmp_path)
    threads: list[threading.Thread] = []

    def in_a_thread(work: object) -> None:
        thread = threading.Thread(target=work)  # pyright: ignore[reportArgumentType]
        threads.append(thread)
        thread.start()

    catalogue = CatalogueService(
        world.repository, world.youtube, world.views, world.clock, in_a_thread
    )
    listed = threading.Event()

    def when_listed(event: AppEvent | None) -> None:
        if isinstance(event, ChannelUpdated) and event.view.channel.first_listed_at is not None:
            listed.set()

    world.bus.subscribe(when_listed)
    looked_up = world.channels.lookup("@small")
    world.run_background()
    world.repository.add_channel(
        make_channel(
            looked_up.facts.channel_id,
            first_listed_at=None,
            last_check_at=None,
            last_full_check_at=None,
        )
    )

    catalogue.start()
    assert listed.wait(10)
    catalogue.stop()
    threads[0].join(10)

    assert not threads[0].is_alive()
    assert len(world.ids(SMALL_ID)) == 5


def test_every_successful_check_tells_the_interface_that_the_catalogue_was_read_again(
    tmp_path: Path,
) -> None:
    """R-FB-03: the list is told to load again after every check, also two in one second."""
    world = World(tmp_path, channel_file(checks=[{}, {"fail": "RATE_LIMITED"}]))
    channel_id = world.add_and_list()

    def version() -> int:
        view = world.views.of(channel_id)
        assert view is not None
        return view.catalogue_version

    versions = [version()]
    for kind in (CheckKind.QUICK, CheckKind.QUICK, CheckKind.FULL):
        world.check(channel_id, kind)
        versions.append(version())

    assert versions[1] == versions[0] + 1
    assert versions[2] == versions[1]
    assert versions[3] == versions[2] + 1


class _LateToSayChecking:
    """Channel views that say "checking" only after the worker had time to end the check."""

    def __init__(self, views: ChannelViews) -> None:
        self._views = views
        self.ended = threading.Event()

    def set_checking(self, channel_id: str, checking: bool) -> None:
        if checking:
            self.ended.wait(0.3)
        self._views.set_checking(channel_id, checking)
        if not checking:
            self.ended.set()

    def __getattr__(self, name: str) -> object:
        return getattr(self._views, name)


def test_a_check_that_ends_at_once_does_not_leave_the_channel_checking(tmp_path: Path) -> None:
    """R-FB-01: a channel says "Checking" only while its check waits or runs, however fast it is."""
    world = World(tmp_path)
    channel_id = world.add_and_list()
    views = _LateToSayChecking(world.views)
    threads: list[threading.Thread] = []

    def in_a_thread(work: object) -> None:
        thread = threading.Thread(target=work)  # pyright: ignore[reportArgumentType]
        threads.append(thread)
        thread.start()

    catalogue = CatalogueService(
        world.repository,
        world.youtube,
        views,  # pyright: ignore[reportArgumentType]
        world.clock,
        in_a_thread,
    )
    catalogue.start()

    catalogue.request_check(channel_id, CheckKind.QUICK)
    ended = views.ended.wait(10)
    catalogue.stop()
    threads[0].join(10)

    view = world.views.of(channel_id)
    assert ended
    assert not world.views.is_checking(channel_id)
    assert view is not None and view.status is ChannelStatus.UP_TO_DATE


def test_a_check_that_reads_while_the_app_stops_ends_and_stores_nothing(tmp_path: Path) -> None:
    """R-PL-13: stopping the app ends a running check at the next video, with nothing stored."""
    world = World(tmp_path, BIG)
    channel_id = world.add("@big")
    world.at_progress(30, lambda: world.catalogue.stop())

    world.work()

    assert world.ids(channel_id) == []


def test_a_retry_after_a_failed_check_shows_as_checking_and_a_success_clears_the_failure(
    tmp_path: Path,
) -> None:
    """R-FB-01, R-CH-25: a retry is shown while it waits and runs, and success ends the failure."""
    world = World(tmp_path, big_with({"fail": "NETWORK_UNREACHABLE"}, {}))
    channel_id = world.add_and_list("@big")
    world.check(channel_id)
    failed = world.views.of(channel_id)

    world.catalogue.request_check(channel_id, CheckKind.QUICK)
    retrying = world.views.of(channel_id)
    world.work()
    after = world.views.of(channel_id)

    assert failed is not None and retrying is not None and after is not None
    assert failed.status is ChannelStatus.COULD_NOT_CHECK
    assert retrying.status is ChannelStatus.CHECKING
    assert retrying.channel.last_check_error is ErrorCode.NETWORK_UNREACHABLE
    assert after.status is ChannelStatus.UP_TO_DATE
    assert (after.channel.last_check_error, after.channel.last_check_error_at) == (None, None)


def test_a_failed_check_stores_when_it_failed_and_a_new_failure_its_own_time(
    tmp_path: Path,
) -> None:
    """R-CH-25: the banner of a failed check can say when the check failed, also the second time."""
    world = World(tmp_path, big_with({"fail": "NETWORK_UNREACHABLE"}, {"fail": "RATE_LIMITED"}, {}))
    channel_id = world.add_and_list("@big")
    first_time = int(world.clock.now().timestamp())

    world.check(channel_id)
    first = world.repository.channel(channel_id)
    world.clock.advance(120)
    world.check(channel_id)
    second = world.repository.channel(channel_id)

    assert first is not None and second is not None
    assert (first.last_check_error, first.last_check_error_at) == (
        ErrorCode.NETWORK_UNREACHABLE,
        first_time,
    )
    assert (second.last_check_error, second.last_check_error_at) == (
        ErrorCode.RATE_LIMITED,
        first_time + 120,
    )


def test_a_first_listing_that_failed_and_is_tried_again_tells_its_progress(
    tmp_path: Path,
) -> None:
    """R-CH-11, R-CH-25: the retry of a failed first listing is a first listing, with its count."""
    world = World(tmp_path, {**BIG, "listing_failures": {"0": "NETWORK_UNREACHABLE"}})
    channel_id = world.add_and_list("@big")
    failed = world.views.of(channel_id)
    world.events.clear()

    world.check(channel_id)

    progress = [event.progress for event in world.progress()]
    assert failed is not None and failed.status is ChannelStatus.COULD_NOT_CHECK
    assert {step.kind for step in progress} == {TaskKind.FIRST_LISTING}
    assert [step.done for step in progress][:3] == [0, 30, 60]
    assert len(world.ids(channel_id)) == 95


def test_check_all_waits_between_two_channels_and_not_before_the_first(tmp_path: Path) -> None:
    """R-CH-24: between two channels of "Check all channels now" the worker waits a short time."""
    third = channel_file("UCthirdthirdthirdthird03", title="Third", handle="@third", prefix="th")
    world = World(tmp_path, channel_file(), BIG, third)
    for handle in ("@small", "@big", "@third"):
        world.add_and_list(handle)

    world.catalogue.request_check_all()
    world.work()
    after_all = list(world.waited)
    world.check(SMALL_ID)

    assert after_all == [2.0, 2.0]
    assert world.waited == after_all


def test_the_wait_between_two_channels_is_chosen_between_one_and_three_seconds(
    tmp_path: Path,
) -> None:
    """R-CH-24: the delay is a random time of 1 to 3 seconds."""
    world = World(tmp_path, channel_file(), BIG)
    world.add_and_list("@small")
    world.add_and_list("@big")
    asked: list[tuple[float, float]] = []

    def choose(least: float, most: float) -> float:
        asked.append((least, most))
        return 1.5

    catalogue = CatalogueService(
        world.repository,
        world.youtube,
        world.views,
        world.clock,
        world.background.append,
        choose_delay=choose,
        wait=world.waited.append,
    )
    catalogue.request_check_all()
    while catalogue.work_once():
        pass

    assert asked == [(1.0, 3.0)]
    assert world.waited == [1.5]


def test_a_channel_that_is_paused_while_its_check_waits_its_turn_is_not_checked(
    tmp_path: Path,
) -> None:
    """R-CH-24, R-CH-31: a check that is dropped during the wait before it does not run."""
    world = World(tmp_path, channel_file(), BIG)
    world.add_and_list("@small")
    world.add_and_list("@big")
    started = dict(world.fixture.listings_started)

    def pause_the_big_one() -> None:
        world.channels.set_paused(BIG_ID, True)

    world.during_wait = pause_the_big_one

    world.catalogue.request_check_all()
    world.work()

    assert world.waited == [2.0]
    assert world.fixture.listings_started[SMALL_ID] == started[SMALL_ID] + 1
    assert world.fixture.listings_started[BIG_ID] == started[BIG_ID]
    assert not world.views.is_checking(BIG_ID)


def test_the_wait_between_two_channels_ends_when_the_app_stops(tmp_path: Path) -> None:
    """R-PL-13, R-CH-24: stopping the app does not wait for the delay between two channels."""
    world = World(tmp_path, channel_file(), BIG)
    world.add_and_list("@small")
    world.add_and_list("@big")
    started = dict(world.fixture.listings_started)
    threads: list[threading.Thread] = []

    def in_a_thread(work: object) -> None:
        thread = threading.Thread(target=work)  # pyright: ignore[reportArgumentType]
        threads.append(thread)
        thread.start()

    first_checked = threading.Event()
    catalogue = CatalogueService(
        world.repository,
        world.youtube,
        world.views,
        world.clock,
        in_a_thread,
        after_check=lambda _channel_id, _kind: first_checked.set(),
        choose_delay=lambda _least, _most: 600.0,
    )
    catalogue.start()

    catalogue.request_check_all()
    assert first_checked.wait(10)
    catalogue.stop()
    threads[0].join(10)

    assert not threads[0].is_alive()
    assert world.fixture.listings_started[BIG_ID] == started[BIG_ID]


SHARED = {"id": "sm000000005", "title": "Made together", "point": "2026-11-05"}
"""A video that the small channel has and that another channel lists as well."""


def test_a_video_that_another_channel_has_stays_there_and_is_logged(tmp_path: Path) -> None:
    """R-CH-17: a video belongs to the first channel that listed it. The other check logs it."""
    other = channel_file(
        "UCotherotherotherother03", title="Other", handle="@other", prefix="ot", videos=3
    )
    world = World(tmp_path, channel_file(), {**other, "videos": [SHARED]})
    world.add_and_list("@small")

    with capture_logs() as logs:
        world.add_and_list("@other")

    lines = log_lines(logs, "check.video_of_other_channel")
    finished = log_lines(logs, "check.finished")[-1]
    assert "sm000000005" in world.ids(SMALL_ID)
    assert "sm000000005" not in world.ids(other["id"])
    assert len(world.ids(other["id"])) == 3
    assert [(line["video_id"], line["owner_channel_id"]) for line in lines] == [
        ("sm000000005", SMALL_ID)
    ]
    assert finished["inserted"] == 3


def test_a_video_of_another_channel_is_never_counted_as_new(tmp_path: Path) -> None:
    """R-CH-17, R-CH-15: every later check leaves the video where it is, and finds nothing new."""
    other = channel_file(
        "UCotherotherotherother03", title="Other", handle="@other", prefix="ot", videos=3
    )
    world = World(tmp_path, channel_file(), {**other, "videos": [SHARED]})
    world.add_and_list("@small")
    world.add_and_list("@other")

    with capture_logs() as logs:
        world.check(other["id"], CheckKind.QUICK)
        world.check(other["id"], CheckKind.FULL)

    view = world.views.of(other["id"])
    assert view is not None
    assert [line["new"] for line in log_lines(logs, "check.finished")] == [0, 0]
    assert view.totals.new == 0
    assert view.totals.videos == 3


def test_when_the_first_channel_is_removed_the_other_takes_the_video(tmp_path: Path) -> None:
    """R-CH-17: once the channel that had the video is gone, the other one takes it."""
    other = channel_file(
        "UCotherotherotherother03", title="Other", handle="@other", prefix="ot", videos=3
    )
    world = World(tmp_path, channel_file(), {**other, "videos": [SHARED]})
    world.add_and_list("@small")
    world.add_and_list("@other")

    world.channels.remove(SMALL_ID)
    world.check(other["id"], CheckKind.QUICK)

    assert "sm000000005" in world.ids(other["id"])
    assert len(world.ids(other["id"])) == 4


# --- what started a check, in its log line


def triggers(logs: Sequence[Mapping[str, Any]]) -> list[tuple[Any, Any]]:
    """Return the kind and the trigger of every check that started."""
    return [(line["kind"], line["trigger"]) for line in log_lines(logs, "check.started")]


def test_the_first_listing_of_a_new_channel_says_it_came_from_adding(tmp_path: Path) -> None:
    """R-CH-11, R-LG-01: the log tells that adding a channel started its first listing."""
    world = World(tmp_path)

    with capture_logs() as logs:
        world.add_and_list()

    assert triggers(logs) == [("full", "add")]


def test_a_first_listing_taken_up_at_start_says_so(tmp_path: Path) -> None:
    """R-CH-11, R-LG-01: a first listing a quit interrupted is logged as started by the app."""
    world = World(tmp_path)
    channel_id = world.add()
    world.catalogue.forget(channel_id)
    world.run_background()

    with capture_logs() as logs:
        world.catalogue.start()
        world.background.clear()
        world.work()

    assert triggers(logs) == [("full", "app_start")]


def test_a_first_listing_taken_up_after_the_pause_of_youtube_is_a_retry(tmp_path: Path) -> None:
    """R-ER-05, R-LG-01: work that waited for YouTube is logged as a retry when it goes on."""
    world = World(tmp_path)
    world.catalogue.start()
    world.background.clear()
    world.gateway.refuse["listing"] = ErrorCode.BOT_CHECK
    world.add()
    world.work()
    world.gateway.refuse.clear()

    with capture_logs() as logs:
        world.youtube.try_now()
        world.work()

    assert triggers(logs) == [("full", "retry")]


def test_resuming_a_channel_that_was_never_listed_says_so(tmp_path: Path) -> None:
    """R-CH-31, R-LG-01: the first listing after a resume is logged as started by the resume."""
    world = World(tmp_path)
    channel_id = world.add()
    world.channels.set_paused(channel_id, True)
    world.work()

    with capture_logs() as logs:
        world.channels.set_paused(channel_id, False)
        world.work()

    assert triggers(logs) == [("full", "resume")]


def test_check_all_and_a_full_check_that_takes_its_place_keep_their_own_triggers(
    tmp_path: Path,
) -> None:
    """R-CH-24, R-LG-01: a full check that replaces a waiting quick one keeps its trigger."""
    world = World(tmp_path, channel_file(), BIG)
    world.add_and_list()
    world.add_and_list("@big")

    with capture_logs() as logs:
        world.catalogue.request_check_all()
        world.catalogue.request_check(BIG_ID, CheckKind.FULL, trigger=CheckTrigger.MENU)
        world.work()

    assert sorted(triggers(logs)) == [("full", "menu"), ("quick", "check_all")]
