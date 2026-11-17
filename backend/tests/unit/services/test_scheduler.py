"""Tests of the scheduler (``ytmirror.services.scheduler``), with a fake clock."""

from pathlib import Path

import pytest
from structlog.testing import capture_logs

from tests.fixtures.world import BIG_ID, SMALL_ID, World, channel_file, log_lines
from ytmirror.core.channels import ChecksProgressed
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.models import Settings

MINUTE = 60
DAY = 24 * 60 * MINUTE


def two_channels(tmp_path: Path) -> World:
    """The services with two channels added and listed, and the scheduler opened."""
    world = World(
        tmp_path,
        channel_file(),
        channel_file(BIG_ID, title="Big", handle="@big", prefix="bg"),
    )
    world.add_and_list("@small")
    world.add_and_list("@big")
    world.settings_repository.save(Settings(fetch_exact_dates=False))
    return world


def listings(world: World) -> int:
    """Return how many listings reached the fake YouTube."""
    return world.gateway.asked.count("listing")


def ticked(world: World) -> float:
    """Let the scheduler start what is due, and the checks it started run."""
    wait = world.scheduler.tick()
    world.work()
    return wait


def test_when_the_app_opens_every_listed_channel_is_checked(tmp_path: Path) -> None:
    """R-CH-20: all non-paused channels, one after another, counted "Checking channels: X of Y"."""
    world = two_channels(tmp_path)
    world.channels.set_paused(BIG_ID, True)
    before = listings(world)

    world.scheduler.tick()
    progress = world.views.checking_all()
    world.work()

    assert progress == (0, 1)
    assert listings(world) == before + 1
    told = [event.progress for event in world.events if isinstance(event, ChecksProgressed)]
    assert told[-2:] == [(0, 1), None]
    assert world.views.checking_all() is None


def test_checks_on_open_can_be_switched_off(tmp_path: Path) -> None:
    """R-CH-20: the setting "Check all channels on open"."""
    world = two_channels(tmp_path)
    world.settings_repository.save(Settings(check_on_open=False, fetch_exact_dates=False))
    before = listings(world)

    ticked(world)

    assert listings(world) == before


def test_all_channels_are_checked_again_on_the_interval(tmp_path: Path) -> None:
    """R-CH-22: every 30 minutes by default."""
    world = two_channels(tmp_path)
    ticked(world)
    after_open = listings(world)

    world.clock.advance(29 * MINUTE)
    ticked(world)
    assert listings(world) == after_open
    world.clock.advance(MINUTE)
    ticked(world)

    assert listings(world) == after_open + 2


def test_an_interval_of_never_checks_only_on_open(tmp_path: Path) -> None:
    """R-CH-22: "never" is a choice of the interval."""
    world = two_channels(tmp_path)
    world.settings_repository.save(Settings(recheck_interval_min=0, fetch_exact_dates=False))
    ticked(world)
    after_open = listings(world)

    world.clock.advance(DAY)
    ticked(world)

    assert listings(world) == after_open


def test_a_channel_selected_after_more_than_five_minutes_is_checked(tmp_path: Path) -> None:
    """R-CH-21: selecting a channel triggers a quick check when it is stale."""
    world = two_channels(tmp_path)
    before = listings(world)

    world.state.open_channel(SMALL_ID)
    world.work()
    assert listings(world) == before
    world.clock.advance(5 * MINUTE + 1)
    world.state.open_channel(SMALL_ID)
    world.work()

    assert listings(world) == before + 1


def test_a_failed_check_is_retried_after_5_15_and_60_minutes(tmp_path: Path) -> None:
    """R-CH-25: automatic retries with backoff, counted on the channel, until it works."""
    world = two_channels(tmp_path)
    world.settings_repository.save(
        Settings(check_on_open=False, recheck_interval_min=0, fetch_exact_dates=False)
    )
    world.gateway.refuse["listing"] = ErrorCode.NETWORK_UNREACHABLE
    world.check(SMALL_ID)
    retried: list[int] = []

    with capture_logs() as logs:
        for minutes in (5, 15, 60, 60):
            world.clock.advance(minutes * MINUTE - 1)
            ticked(world)
            world.clock.advance(1)
            ticked(world)
            channel = world.repository.channel(SMALL_ID)
            assert channel is not None
            retried.append(channel.check_retries)
        world.gateway.refuse.clear()
        world.clock.advance(60 * MINUTE)
        ticked(world)

    assert retried == [1, 2, 3, 4]
    assert len(log_lines(logs, "scheduler.retry")) == 5
    channel = world.repository.channel(SMALL_ID)
    assert channel is not None
    assert (channel.last_check_error, channel.check_retries) == (None, 0)


def test_the_time_of_the_next_retry_is_what_the_scheduler_waits_for(tmp_path: Path) -> None:
    """R-CH-25: the scheduler wakes when the retry is due."""
    world = two_channels(tmp_path)
    world.settings_repository.save(
        Settings(check_on_open=False, recheck_interval_min=0, fetch_exact_dates=False)
    )
    world.gateway.refuse["listing"] = ErrorCode.NETWORK_UNREACHABLE
    world.check(SMALL_ID)

    assert world.scheduler.tick() == 5 * MINUTE


def test_nothing_is_started_by_itself_while_youtube_pauses_the_app(tmp_path: Path) -> None:
    """R-ER-05: checks the app starts by itself wait for the end of the pause."""
    world = two_channels(tmp_path)
    world.gateway.refuse["lookup"] = ErrorCode.BOT_CHECK
    with pytest.raises(AppError):
        world.channels.lookup("@small")
    assert world.youtube.pause() is not None
    before = listings(world)

    ticked(world)

    assert listings(world) == before
    assert world.views.checking_all() is None


def test_a_full_check_runs_by_itself_after_seven_days_one_channel_at_a_time(
    tmp_path: Path,
) -> None:
    """R-CH-26: "Full check at least every" 7 days, at most one channel at a time."""
    world = two_channels(tmp_path)
    world.settings_repository.save(
        Settings(check_on_open=False, recheck_interval_min=0, fetch_exact_dates=False)
    )
    world.clock.advance(7 * DAY)

    with capture_logs() as logs:
        world.scheduler.tick()
        first = [line["channel_id"] for line in log_lines(logs, "scheduler.full_check")]
        world.scheduler.tick()
        still_one = len(log_lines(logs, "scheduler.full_check"))
        world.work()
        ticked(world)

    assert len(first) == still_one == 1
    started = [line["channel_id"] for line in log_lines(logs, "scheduler.full_check")]
    assert sorted(started) == sorted([SMALL_ID, BIG_ID])


def test_a_full_check_waits_while_downloads_of_its_channel_wait_or_run(tmp_path: Path) -> None:
    """R-CH-26: never while downloads of that channel are running."""
    world = two_channels(tmp_path)
    world.settings_repository.save(
        Settings(check_on_open=False, recheck_interval_min=0, fetch_exact_dates=False)
    )
    world.downloader.mirror(["sm000000005"])
    world.downloader.mirror(["bg000000005"])
    world.clock.advance(7 * DAY)

    with capture_logs() as logs:
        world.scheduler.tick()

    assert log_lines(logs, "scheduler.full_check") == []


def test_the_scheduler_runs_the_exact_date_fetch(tmp_path: Path) -> None:
    """R-DT-05: the fetch is background work of the one scheduler."""
    world = World(tmp_path)
    world.add_and_list()
    world.settings_repository.save(Settings(check_on_open=False))

    world.scheduler.tick()
    first = world.gateway.asked.count("exact_date")
    world.scheduler.tick()
    held = world.gateway.asked.count("exact_date")
    world.clock.advance(12)
    world.scheduler.tick()

    assert (first, held, world.gateway.asked.count("exact_date")) == (1, 1, 2)
