"""Tests of ``ytmirror.services.catalogue``: checks against the fake YouTube."""

import threading
from pathlib import Path

import pytest
from structlog.testing import capture_logs

from tests.fixtures.catalogue import make_channel
from tests.fixtures.world import BIG_ID, SMALL_ID, World, channel_file, log_lines, new_video
from ytmirror.core.channels import ChannelStatus, ChannelUpdated, CheckKind, TaskKind
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.models import AppEvent
from ytmirror.services.catalogue import PROGRESS_EVERY, CatalogueService

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
    """R-CH-03: the catalogue is the source of truth, and a different preview count is logged."""
    world = World(tmp_path, channel_file(count=57))

    with capture_logs() as logs:
        world.add_and_list()

    differs = log_lines(logs, "channel.count_differs")
    assert len(differs) == 1
    assert (differs[0]["preview_count"], differs[0]["listed"]) == (57, 5)


def test_a_preview_count_that_agrees_is_not_logged(tmp_path: Path) -> None:
    """R-CH-03: nothing is said when the preview and the listing agree."""
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
    """R-CH-23: only a channel that was added can be checked."""
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
    """R-CH-23: "Full check" on top of a waiting "Check now" runs one full check."""
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


def test_a_check_that_reads_while_the_app_stops_ends_and_stores_nothing(tmp_path: Path) -> None:
    """R-PL-13: stopping the app ends a running check at the next video, with nothing stored."""
    world = World(tmp_path, BIG)
    channel_id = world.add("@big")
    world.at_progress(30, lambda: world.catalogue.stop())

    world.work()

    assert world.ids(channel_id) == []
