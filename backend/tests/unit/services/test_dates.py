"""Tests of the exact-date fetch (``ytmirror.services.dates``) with the fake YouTube and its API."""

from pathlib import Path
from typing import Any

import pytest
from structlog.testing import capture_logs

from tests.fixtures.world import SMALL_ID, World, channel_file, log_lines
from ytmirror.adapters.api_key_file import FILE_NAME, ApiKeyFile
from ytmirror.core.channels import ChannelStatus
from ytmirror.core.errors import ErrorCode
from ytmirror.core.exact_dates import DateState, KeyStateChanged, KeyStatus
from ytmirror.core.models import Settings
from ytmirror.core.pacing import LookupBudget
from ytmirror.services.dates import IDLE_S, URGENT_RETRY_S, DatesService, next_quota_reset

NEWEST, SECOND, THIRD = "sm000000005", "sm000000004", "sm000000003"
KEY = "fixture-good-key-0001"
HOUR = 3600


def listed(tmp_path: Path, *channels: dict[str, Any]) -> World:
    """The services with the small channel (or the given ones) added and listed."""
    world = World(tmp_path, *channels)
    world.add_and_list()
    world.events.clear()
    return world


def exact(world: World, video_id: str) -> bool:
    """Return whether a video has an exact date."""
    video = world.repository.video(video_id)
    assert video is not None
    return video.published_exact


def asked(world: World, kind: str = "exact_date") -> int:
    """Return how many requests of a kind reached the fake YouTube."""
    return world.gateway.asked.count(kind)


def date_of(world: World, video_id: str) -> Any:
    """Return what the date of a video shows in a list."""
    view = world.views.video(video_id)
    assert view is not None
    return view.date


def status_of(world: World) -> ChannelStatus:
    """Return the status line of the small channel."""
    view = world.views.of(SMALL_ID)
    assert view is not None
    return view.status


def without_lookups(world: World) -> None:
    """Switch the background lookups without a key off."""
    world.settings_repository.save(Settings(fetch_exact_dates=False))


# --- without a key (R-DT-05, R-DT-06)


def test_the_newest_video_is_looked_up_first_and_gets_its_exact_date(tmp_path: Path) -> None:
    """R-DT-05: the background fetch takes the newest video first and stores its exact time."""
    world = listed(tmp_path)

    assert world.dates.step() == 0

    assert exact(world, NEWEST)
    assert not exact(world, SECOND)
    assert world.found_exact == [NEWEST]
    assert asked(world) == 1


def test_lookups_keep_to_the_budget_one_at_a_time(tmp_path: Path) -> None:
    """R-DT-06: the next lookup waits its share of the hour, 12 seconds at 300 an hour."""
    world = listed(tmp_path)
    world.dates.step()

    assert world.dates.step() == 12
    assert asked(world) == 1
    world.clock.advance(12)
    assert world.dates.step() == 0
    assert exact(world, SECOND)


def test_the_fetch_yields_to_a_download_and_goes_on_when_none_is_left(tmp_path: Path) -> None:
    """R-DT-06: no lookup while a download waits or runs."""
    world = listed(tmp_path)
    world.downloader.mirror([THIRD])

    assert world.dates.step() is None
    assert asked(world) == 0

    world.download_all()
    assert world.dates.step() == 0
    assert asked(world) == 1


def test_a_date_a_decision_waits_for_is_looked_up_while_downloads_run(tmp_path: Path) -> None:
    """R-MI-03, R-DT-06, D-090: auto-mirror's decision is not held up until downloads end."""
    world = listed(tmp_path)
    world.downloader.mirror([NEWEST])
    world.dates.prioritize([SECOND])

    assert world.dates.step() == 0

    assert exact(world, SECOND)
    assert asked(world) == 1


def test_an_urgent_date_still_waits_for_room_in_the_budget(tmp_path: Path) -> None:
    """R-MI-03, D-090: while downloads run, it waits for the budget only."""
    world = World(tmp_path, budget=LookupBudget(per_hour=1))
    world.add_and_list()
    world.downloader.mirror([NEWEST])
    world.download_all()
    world.downloader.mirror([THIRD])
    world.dates.prioritize([SECOND])

    assert world.dates.step() == URGENT_RETRY_S
    assert asked(world) == 0


def test_the_pause_of_youtube_holds_the_fetch_and_the_channel_waits_for_youtube(
    tmp_path: Path,
) -> None:
    """R-ER-05, R-FB-01, R-DT-13: held-up work waits; its dates say why, not an error each."""
    world = listed(tmp_path)
    world.gateway.refuse["exact_date"] = ErrorCode.BOT_CHECK

    assert world.dates.step() is None

    pause = world.youtube.pause()
    assert pause is not None
    assert status_of(world) is ChannelStatus.WAITING_FOR_YOUTUBE
    view = world.views.of(SMALL_ID)
    assert view is not None
    assert view.waiting_until == pause.until
    shown = date_of(world, SECOND)
    assert (shown.state, shown.reason) == (DateState.UNAVAILABLE, ErrorCode.BOT_CHECK)
    assert world.dates.step() is None
    assert asked(world) == 1


def test_a_slow_down_from_youtube_starts_the_fetchs_own_back_off(tmp_path: Path) -> None:
    """R-DT-06, R-FB-01: after RATE_LIMITED the fetch waits 15 minutes, then twice as long."""
    world = listed(tmp_path)
    world.gateway.refuse["exact_date"] = ErrorCode.RATE_LIMITED

    with capture_logs() as logs:
        first = world.dates.step()
        world.clock.advance(15 * 60)
        second = world.dates.step()

    assert (first, second) == (15 * 60, 30 * 60)
    assert status_of(world) is ChannelStatus.WAITING_FOR_YOUTUBE
    assert world.youtube.pause() is None
    assert [line["pause_s"] for line in log_lines(logs, "dates.fetch.backoff")] == [900, 1800]
    world.gateway.refuse.clear()
    world.clock.advance(30 * 60)
    assert world.dates.step() == 0
    assert status_of(world) is ChannelStatus.EXACT_DATES


def test_a_video_whose_lookup_fails_is_unavailable_and_tried_again_later(tmp_path: Path) -> None:
    """R-DT-13: the date says why and when it is tried again; the fetch goes on."""
    world = listed(tmp_path)
    world.gateway.refuse["exact_date"] = ErrorCode.VIDEO_PRIVATE
    now = int(world.clock.now().timestamp())

    assert world.dates.step() == 0
    world.gateway.refuse.clear()
    world.clock.advance(12)
    world.dates.step()

    shown = date_of(world, NEWEST)
    assert shown.state is DateState.UNAVAILABLE
    assert (shown.reason, shown.retry_at) == (ErrorCode.VIDEO_PRIVATE, now + HOUR)
    assert exact(world, SECOND)


def test_a_video_not_released_yet_gets_no_exact_date(tmp_path: Path) -> None:
    """R-DT-03: a premiere that has not started has no exact date; it is tried again."""
    channel = channel_file(videos=1)
    channel["videos"] = [
        {"id": "up000000001", "title": "Soon", "point": "2026-11-13", "upcoming": True}
    ]
    world = listed(tmp_path, channel)

    world.dates.step()

    assert not exact(world, "up000000001")
    shown = date_of(world, "up000000001")
    assert (shown.state, shown.reason) == (DateState.UNAVAILABLE, ErrorCode.NOT_YET_AVAILABLE)


def test_without_a_key_and_with_lookups_switched_off_nothing_is_asked(tmp_path: Path) -> None:
    """R-DT-05: the background fetch without a key is a setting."""
    world = listed(tmp_path)
    without_lookups(world)

    assert world.dates.step() is None
    assert asked(world) == 0
    assert status_of(world) is not ChannelStatus.EXACT_DATES


def test_a_decision_waiting_for_a_date_goes_first(tmp_path: Path) -> None:
    """R-DT-05, R-MI-03: videos whose exact date a decision waits for go to the front."""
    world = listed(tmp_path)

    world.dates.prioritize([THIRD])
    world.dates.step()

    assert exact(world, THIRD)
    assert not exact(world, NEWEST)


def test_nothing_waiting_means_nothing_asked_and_the_key_not_read(tmp_path: Path) -> None:
    """R-DT-05, D-085: the key is read only when the fetch first needs it."""
    world = World(tmp_path)
    world.keys.key = KEY

    assert world.dates.step() == IDLE_S
    assert world.keys.reads == 0


# --- progress, time left and the key offer (R-FB-01, R-DT-14, R-DT-15)


def test_a_channel_shows_exact_dates_x_of_y_while_its_dates_are_fetched(tmp_path: Path) -> None:
    """R-FB-01: "Exact dates X of Y" is running work."""
    world = listed(tmp_path)

    world.dates.step()

    view = world.views.of(SMALL_ID)
    assert view is not None
    assert view.status is ChannelStatus.EXACT_DATES
    assert view.exact_dates is not None
    assert (view.exact_dates.done, view.exact_dates.total) == (1, 5)
    assert view.exact_dates.left_s is None


def test_the_time_left_comes_from_the_measured_rate_and_the_key_is_offered(tmp_path: Path) -> None:
    """R-DT-14, R-DT-15: after enough lookups the time left is measured; over 10 min, a key."""
    world = listed(tmp_path, channel_file(videos=80))
    for _ in range(6):
        world.dates.step()
        world.clock.advance(12)

    view = world.views.of(SMALL_ID)
    assert view is not None
    assert view.exact_dates is not None
    assert view.exact_dates.left_s == 74 * 12
    assert view.exact_dates.offer_key


def test_the_progress_ends_when_no_date_of_the_channel_waits(tmp_path: Path) -> None:
    """R-FB-01: the channel is up to date again when all its dates are exact."""
    world = listed(tmp_path)
    for _ in range(5):
        world.dates.step()
        world.clock.advance(12)

    world.dates.step()

    view = world.views.of(SMALL_ID)
    assert view is not None
    assert view.exact_dates is None
    assert view.status is not ChannelStatus.EXACT_DATES


# --- with a key (R-DT-05, R-DT-12, D-082, D-083)


def test_with_a_key_the_dates_come_from_the_api_fifty_at_a_time(tmp_path: Path) -> None:
    """R-DT-05, D-082: one request of the API for up to 50 videos, no lookups."""
    world = listed(tmp_path, channel_file(videos=60))
    world.keys.key = KEY

    world.dates.step()
    world.dates.step()

    assert world.api.requests == 2
    assert asked(world) == 0
    assert all(exact(world, video_id) for video_id in world.ids(SMALL_ID))
    assert world.secrets == [KEY]


def test_a_video_the_api_leaves_out_keeps_its_date_until_the_next_check(tmp_path: Path) -> None:
    """R-DT-05, D-083: no exact date, no change of status, asked again after the next check."""
    channel = channel_file(videos=1)
    channel["videos"] = [
        {"id": "gone0000001", "title": "Private", "point": "2026-11-12", "api_missing": True}
    ]
    world = listed(tmp_path, channel)
    world.keys.key = KEY

    world.dates.step()
    requests = world.api.requests
    assert world.dates.step() is None

    video = world.repository.video("gone0000001")
    assert video is not None
    assert (video.published_exact, video.gone) == (False, False)
    assert world.api.requests == requests
    assert asked(world) == 0
    world.clock.advance(60)
    world.check(SMALL_ID)
    world.dates.step()
    assert world.api.requests == requests + 1


def test_an_invalid_key_falls_back_to_lookups_without_an_error(tmp_path: Path) -> None:
    """R-DT-12: no error dialog; the key setting says so, and a notice stands by the progress."""
    world = listed(tmp_path)
    world.keys.key = "fixture-invalid-key"

    with capture_logs() as logs:
        world.dates.step()
        world.dates.step()

    assert world.dates.key_state().status is KeyStatus.INVALID
    assert world.dates.key_state().until is None
    assert exact(world, NEWEST)
    assert asked(world) == 1
    assert [line["error_code"] for line in log_lines(logs, "dates.source_fell_back")] == [
        "API_KEY_INVALID"
    ]
    assert any(isinstance(event, KeyStateChanged) for event in world.events)
    view = world.views.of(SMALL_ID)
    assert view is not None
    assert view.key_notice


def test_a_used_up_quota_waits_until_midnight_pacific_time(tmp_path: Path) -> None:
    """R-DT-12: the app does without the key until its quota starts anew."""
    world = listed(tmp_path)
    world.keys.key = "fixture-quota-key"
    now = int(world.clock.now().timestamp())

    world.dates.step()

    state = world.dates.key_state()
    assert state.status is KeyStatus.QUOTA_EXCEEDED
    assert state.until == next_quota_reset(now)


def test_the_quota_starts_anew_at_midnight_pacific_time() -> None:
    """R-DT-12: 17 Nov 2026 10:00 UTC is 02:00 in California; the quota resets 08:00 UTC next."""
    assert next_quota_reset(1_794_909_600) == 1_794_988_800


def test_an_unreadable_key_is_done_without_and_logged_once(tmp_path: Path) -> None:
    """R-DT-12: never silently: one warning, "Key saved but cannot be read", lookups go on."""
    world = listed(tmp_path)
    world.keys.key = KEY
    world.keys.unreadable = True

    with capture_logs() as logs:
        world.dates.step()
        world.clock.advance(12)
        world.dates.step()

    assert world.dates.key_state().status is KeyStatus.UNREADABLE
    assert len(log_lines(logs, "apikey.unreadable")) == 1
    assert asked(world) == 2
    world.dates.save_key(KEY)
    assert world.dates.key_state().status is KeyStatus.SAVED


# --- the key setting (R-DT-12, R-LG-07)


def test_a_saved_key_is_used_at_once_and_is_a_secret_of_the_logs(tmp_path: Path) -> None:
    """R-DT-12, R-LG-07: saving a key makes it a secret and the fetch uses it."""
    world = listed(tmp_path)

    with capture_logs() as logs:
        state = world.dates.save_key(f"  {KEY}\n")
        world.dates.step()

    assert state.status is KeyStatus.SAVED
    assert world.keys.key == KEY
    assert world.secrets == [KEY]
    assert world.api.requests == 1
    assert all(KEY not in str(line) for line in logs)


@pytest.mark.parametrize("key", ["", "   ", "two words"])
def test_what_is_no_key_is_refused(tmp_path: Path, key: str) -> None:
    """R-DT-12: an empty key or one with spaces inside is not saved."""
    world = World(tmp_path)

    with pytest.raises(Exception, match="INVALID_REQUEST"):
        world.dates.save_key(key)

    assert world.keys.key is None


def test_testing_a_key_says_whether_it_works(tmp_path: Path) -> None:
    """R-DT-12: "Test key" asks the API once, with the pasted or the saved key."""
    world = World(tmp_path)

    good = world.dates.test_key(KEY)
    bad = world.dates.test_key("fixture-invalid-key")

    assert (good.works, good.code) == (True, None)
    assert (bad.works, bad.code) == (False, ErrorCode.API_KEY_INVALID)
    assert world.secrets == [KEY, "fixture-invalid-key"]


def test_a_saved_key_that_passes_its_test_is_used_again(tmp_path: Path) -> None:
    """R-DT-12: after a failure, a test of the saved key that passes ends the failure."""
    world = listed(tmp_path)
    world.keys.key = "fixture-quota-key"
    world.dates.step()

    world.keys.key = KEY
    world.dates.save_key(KEY)
    result = world.dates.test_key()

    assert result.works
    assert world.dates.key_state().status is KeyStatus.SAVED


def test_removing_the_key_changes_nothing_but_speed(tmp_path: Path) -> None:
    """R-DT-12: without the key the dates are looked up again."""
    world = listed(tmp_path)
    world.dates.save_key(KEY)

    state = world.dates.remove_key()
    world.dates.step()

    assert state.status is KeyStatus.NONE
    assert world.keys.key is None
    assert world.api.requests == 0
    assert asked(world) == 1


def test_the_app_works_without_a_google_account_or_a_key(tmp_path: Path) -> None:
    """R-PL-07: listing, exact dates and downloads, with no key saved and no account."""
    world = listed(tmp_path)

    world.dates.step()
    world.downloader.mirror([SECOND])
    world.download_all()

    assert world.dates.key_state().status is KeyStatus.NONE
    assert world.keys.reads == 1
    assert world.api.requests == 0
    assert exact(world, NEWEST)
    assert exact(world, SECOND)


def test_every_date_found_tells_the_interface_how_far_the_channel_is(tmp_path: Path) -> None:
    """R-FB-01, R-FB-03: the interface hears "Exact dates 1 of 5", then "2 of 5"."""
    world = listed(tmp_path)

    world.dates.step()
    world.clock.advance(12)
    world.dates.step()

    told = [
        event.view.exact_dates.done
        for event in world.updates()
        if event.view.channel.id == SMALL_ID and event.view.exact_dates is not None
    ]
    assert told[-1] == 2
    assert 1 in told


def test_an_app_told_not_to_look_up_asks_nothing_without_a_key(tmp_path: Path) -> None:
    """infra: the end-to-end apps on the fake YouTube can switch the lookups without a key off."""
    world = listed(tmp_path)
    quiet = DatesService(
        dates=world.date_repository,
        youtube=world.youtube,
        api=world.api,
        keys=world.keys,
        settings=world.settings,
        downloads=world.downloads,
        state=world.date_state,
        clock=world.clock,
        events=world.bus,
        register_secret=world.secrets.append,
        tell_video=world.views.tell_video,
        tell_channel=world.views.publish,
        look_up=False,
    )

    assert quiet.step() is None
    assert asked(world) == 0


def test_the_key_works_again_and_says_so_when_its_quota_starts_anew(tmp_path: Path) -> None:
    """R-DT-12: at midnight Pacific time the key is used again, and the interface hears it."""
    world = listed(tmp_path, channel_file(videos=3))
    world.keys.key = "fixture-quota-key"
    world.dates.step()
    until = world.dates.key_state().until
    assert until is not None
    world.events.clear()
    requests = world.api.requests

    world.clock.advance(until - int(world.clock.now().timestamp()))
    world.dates.step()

    told = [event.key.status for event in world.events if isinstance(event, KeyStateChanged)]
    assert told[0] is KeyStatus.SAVED
    assert world.api.requests == requests + 1
    later = world.dates.key_state().until
    assert later is not None
    assert later > until


def test_a_fault_while_storing_never_leaves_a_video_updating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-DT-13: an unexpected fault ends the "updating" state of the video."""
    world = listed(tmp_path)

    def broken(video_id: str, published_at: int) -> bool:
        raise RuntimeError("the database went away")

    monkeypatch.setattr(world.date_repository, "set_exact", broken)

    with pytest.raises(RuntimeError):
        world.dates.step()

    assert not world.date_state.updating(NEWEST)


def test_no_progress_is_told_while_the_fetch_does_not_run(tmp_path: Path) -> None:
    """R-FB-01, R-DT-05: lookups switched off and no key: no "Exact dates" anywhere."""
    world = listed(tmp_path)
    without_lookups(world)

    world.dates.step()

    view = world.views.of(SMALL_ID)
    assert view is not None
    assert view.exact_dates is None


def test_removing_the_key_forgets_it_even_when_a_left_copy_cannot_be_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-DT-12, D-085: "Remove key" always takes the key out of memory (review of M4)."""
    keys = ApiKeyFile(tmp_path / "keys")
    world = World(tmp_path, keys=keys)
    world.add_and_list()
    world.dates.save_key(KEY)
    (tmp_path / "keys" / f".{FILE_NAME}.0123456789abcdef.tmp").write_text(KEY, encoding="utf-8")
    unlink = Path.unlink

    def refused_for_copies(path: Path, missing_ok: bool = False) -> None:
        if path.name.endswith(".tmp"):
            raise PermissionError("Operation not permitted")
        unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", refused_for_copies)
    with capture_logs() as logs:
        state = world.dates.remove_key()

    assert state.status is KeyStatus.NONE
    assert world.dates.key_state().status is KeyStatus.NONE
    assert not keys.path.exists()
    assert log_lines(logs, "apikey.leftover_kept")
