"""Tests of date repair and the rename after a new title (``ytmirror.services.repair``)."""

from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from structlog.testing import capture_logs

from tests.fixtures.world import SMALL_ID, World, channel_file, log_lines, own_file
from ytmirror.core.channels import Video
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.models import Settings
from ytmirror.services.repair import fits_title

FULLWIDTH_COLON = chr(0xFF1A)
"""How a colon of a title is stored in a file name (R-FN-02)."""

NEWEST = "sm000000005"
PUBLISHED = 1_793_379_761
"""The upload time the fake download gives."""


def synced(tmp_path: Path, *steps: dict[str, Any], **more: Any) -> World:
    """The small channel, listed, with its newest video synced, and the given check steps."""
    world = World(tmp_path, channel_file(checks=list(steps), **more))
    world.add_and_list()
    world.downloader.mirror([NEWEST])
    world.download_all()
    return world


def folder(world: World) -> Path:
    """Return the folder of the small channel."""
    return world.library / "Small Channel"


def video(world: World, video_id: str = NEWEST) -> Video:
    """Return a stored video."""
    found = world.repository.video(video_id)
    assert found is not None
    return found


def dates_of(world: World, name: str) -> tuple[int, int]:
    """Return the creation and modification date of a file of the channel folder."""
    dates = world.files.read_dates(folder(world) / name)
    return dates.created, dates.modified


def spoil(world: World, name: str) -> None:
    """Give a file other dates, as Finder or a copy might."""
    file = world.files.files[folder(world) / name]
    file.created, file.modified = 1_000_000_000, 1_100_000_000


def test_a_check_repairs_the_dates_of_a_synced_file(tmp_path: Path) -> None:
    """R-DT-09, R-CH-28: every check compares the dates and repairs a difference."""
    world = synced(tmp_path, {})
    spoil(world, "Video 5.mkv")

    with capture_logs() as logs:
        world.check(SMALL_ID)

    assert dates_of(world, "Video 5.mkv") == (PUBLISHED, PUBLISHED)
    assert [line["video_id"] for line in log_lines(logs, "dates.repaired")] == [NEWEST]


def test_with_repair_switched_off_a_check_leaves_the_dates(tmp_path: Path) -> None:
    """R-DT-09: "Repair file dates on every check" is a setting."""
    world = synced(tmp_path, {})
    world.settings_repository.save(Settings(repair_dates=False))
    spoil(world, "Video 5.mkv")

    world.check(SMALL_ID)

    assert dates_of(world, "Video 5.mkv") == (1_000_000_000, 1_100_000_000)


def test_repair_dates_on_demand_reports_what_it_did(tmp_path: Path) -> None:
    """R-DT-09: "Repair dates" does the same for a channel, whatever the setting."""
    world = synced(tmp_path)
    world.settings_repository.save(Settings(repair_dates=False))
    spoil(world, "Video 5.mkv")

    result = world.repair.repair_dates(SMALL_ID)

    assert (result.checked, result.repaired, result.failed) == (1, 1, 0)
    assert dates_of(world, "Video 5.mkv") == (PUBLISHED, PUBLISHED)
    assert world.repair.repair_dates(SMALL_ID).repaired == 0


def test_dates_that_do_not_read_back_are_a_failure_not_a_crash(tmp_path: Path) -> None:
    """R-DT-07, R-DT-09: a repair that macOS refuses is counted and logged."""
    world = synced(tmp_path)
    spoil(world, "Video 5.mkv")
    world.files.drift_dates.add(folder(world) / "Video 5.mkv")

    with capture_logs() as logs:
        result = world.repair.repair_dates(SMALL_ID)

    assert result.failed == 1
    assert log_lines(logs, "dates.verify_failed")


def test_a_new_title_renames_the_file_at_the_next_check(tmp_path: Path) -> None:
    """R-FN-06, R-DT-10: the file takes the new title and keeps its dates."""
    world = synced(tmp_path, {"retitle": {NEWEST: "A better: title"}})

    with capture_logs() as logs:
        world.check(SMALL_ID)

    new = f"A better{FULLWIDTH_COLON} title.mkv"
    assert video(world).file_name == new
    assert world.files.exists(folder(world) / new)
    assert not world.files.exists(folder(world) / "Video 5.mkv")
    assert dates_of(world, new) == (PUBLISHED, PUBLISHED)
    [renamed] = log_lines(logs, "file.renamed")
    assert (renamed["old"], renamed["new"]) == ("Video 5.mkv", new)


def test_a_rename_never_overwrites_another_file(tmp_path: Path) -> None:
    """R-FN-05, R-FN-06: a name that is taken gets the video ID."""
    world = synced(tmp_path, {"retitle": {NEWEST: "Taken"}})
    world.files.add_files(folder(world), ["Taken.mkv"], data=b"the user's own file")

    world.check(SMALL_ID)

    assert video(world).file_name == f"Taken [{NEWEST}].mkv"
    assert world.files.read_bytes(folder(world) / "Taken.mkv") == b"the user's own file"


def test_a_file_named_by_its_video_id_gets_its_title_when_it_can(tmp_path: Path) -> None:
    """R-FN-01, R-FN-06: a title that left nothing gave the ID; a storable one renames it."""
    world = World(tmp_path, channel_file(checks=[{"retitle": {NEWEST: "Now a real title"}}]))
    world.add_and_list()
    world.downloader.mirror([NEWEST])
    world.download_all()
    old = video(world).file_name
    assert old is not None
    world.files.move(folder(world) / old, folder(world) / f"{NEWEST}.mkv")
    world.repository.set_file_name(NEWEST, old, f"{NEWEST}.mkv")

    world.check(SMALL_ID)

    assert video(world).file_name == "Now a real title.mkv"


def test_the_thumbnail_next_to_the_video_is_renamed_with_it(tmp_path: Path) -> None:
    """R-MD-05, R-FN-06: the cover next to the video follows its name."""
    world = synced(tmp_path, {"retitle": {NEWEST: "New name"}})
    world.files.add_files(folder(world), ["Video 5.jpg"], data=b"cover")

    world.check(SMALL_ID)

    assert world.files.read_bytes(folder(world) / "New name.jpg") == b"cover"
    assert not world.files.exists(folder(world) / "Video 5.jpg")


def test_an_interrupted_rename_is_completed_and_the_file_never_trashed(tmp_path: Path) -> None:
    """R-QA-06, R-FN-06: the file moved but its name was not stored; the next check stores it."""
    world = synced(tmp_path, {"retitle": {NEWEST: "Moved already"}}, {})
    world.files.move(folder(world) / "Video 5.mkv", folder(world) / "Moved already.mkv")
    spoil(world, "Moved already.mkv")

    world.check(SMALL_ID)

    assert video(world).file_name == "Moved already.mkv"
    assert world.files.read_bytes(folder(world) / "Moved already.mkv") == own_file(NEWEST)
    assert dates_of(world, "Moved already.mkv") == (PUBLISHED, PUBLISHED)


def test_a_file_of_another_video_under_the_new_name_is_not_taken(tmp_path: Path) -> None:
    """R-QA-06: only a file with this video's ID inside is taken as the moved one."""
    world = synced(tmp_path, {"retitle": {NEWEST: "Someone else"}})
    world.files.trash(folder(world) / "Video 5.mkv")
    world.files.add_files(folder(world), ["Someone else.mkv"], data=b"video:other000001")

    world.check(SMALL_ID)

    assert video(world).file_name == "Video 5.mkv"


def test_a_file_whose_name_fits_its_title_is_left_alone(tmp_path: Path) -> None:
    """R-FN-06: no new title, no rename, also for a name with the video ID."""
    world = synced(tmp_path, {})

    with capture_logs() as logs:
        world.check(SMALL_ID)

    assert log_lines(logs, "file.renamed") == []
    assert video(world).file_name == "Video 5.mkv"


@settings(max_examples=60, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.text(min_size=1, max_size=300))
def test_any_title_gives_a_name_that_fits_it(tmp_path: Path, title: str) -> None:
    """R-FN-06: the name the app gives a title always fits that title, so it is stable."""
    from ytmirror.core.naming import video_file_name

    stand_in = video_of(title)

    assert fits_title(video_file_name(title, stand_in.id, ()), stand_in)
    assert fits_title(video_file_name(title, stand_in.id, ("x",)), stand_in)


def video_of(title: str) -> Video:
    """Return a video with a title, for the property."""
    return Video(
        id="abcdefghijk",
        channel_id=SMALL_ID,
        title=title,
        duration_s=1,
        view_count=1,
        published_at=PUBLISHED,
        published_exact=True,
        published_precision=None,
        thumbnail_url=None,
        channel_position=0,
        first_seen_at=0,
        last_seen_at=0,
        seen_in_first_listing=True,
    )


def test_a_video_that_got_its_exact_time_has_its_file_dates_repaired(tmp_path: Path) -> None:
    """R-DT-10: a synced file whose exact time changed gets that time."""
    world = synced(tmp_path)
    spoil(world, "Video 5.mkv")

    world.repair.repair_video(NEWEST)

    assert dates_of(world, "Video 5.mkv") == (PUBLISHED, PUBLISHED)


def test_a_failed_repair_never_fails_or_undoes_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-CH-28, R-CH-25: the check is stored; its renames and repair are tried at the next."""
    world = synced(tmp_path, {})

    def unplugged(channel_id: str) -> int:
        raise AppError(ErrorCode.FOLDER_UNAVAILABLE, {"folder": "gone"})

    monkeypatch.setattr(world.repair, "rename_retitled", unplugged)
    world.clock.advance(60)

    with capture_logs() as logs:
        world.check(SMALL_ID)

    channel = world.repository.channel(SMALL_ID)
    assert channel is not None
    assert channel.last_check_error is None
    assert channel.last_check_at == int(world.clock.now().timestamp())
    assert log_lines(logs, "dates.repair.failed")
