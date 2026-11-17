"""Tests of date repair and the rename after a new title (``ytmirror.services.repair``)."""

import dataclasses
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from structlog.testing import capture_logs

from tests.fixtures.world import BIG_ID, SMALL_ID, World, channel_file, log_lines, own_file
from ytmirror.core.catalogue import CheckChanges
from ytmirror.core.channels import ChannelStatus, Video, VideoStatus
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.models import Settings
from ytmirror.services.repair import fits_title

FULLWIDTH_COLON = chr(0xFF1A)
"""How a colon of a title is stored in a file name (R-FN-02)."""

NEWEST = "sm000000005"
PUBLISHED = 1_793_379_761
"""The upload time the fake download gives."""
OWN_COVER = b"twelve bytes"
"""What the fake download writes as the thumbnail, kept in the hidden folder."""


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
    world.repository.mark_rename(NEWEST, old, f"{NEWEST}.mkv")
    world.repository.finish_rename(NEWEST, old, f"{NEWEST}.mkv")

    world.check(SMALL_ID)

    assert video(world).file_name == "Now a real title.mkv"


def test_the_thumbnail_next_to_the_video_is_renamed_with_it(tmp_path: Path) -> None:
    """R-MD-05, R-FN-06: the app's cover next to the video follows its name."""
    world = synced(tmp_path, {"retitle": {NEWEST: "New name"}})
    world.files.add_files(folder(world), ["Video 5.jpg"], data=OWN_COVER)

    world.check(SMALL_ID)

    assert world.files.read_bytes(folder(world) / "New name.jpg") == OWN_COVER
    assert not world.files.exists(folder(world) / "Video 5.jpg")


def test_the_users_own_picture_of_that_name_is_never_renamed(tmp_path: Path) -> None:
    """R-FN-06, R-MD-05: a .jpg that is not the app's copy stays as it is (review of M4)."""
    world = synced(tmp_path, {"retitle": {NEWEST: "New name"}})
    world.files.add_files(folder(world), ["Video 5.jpg"], data=b"my own picture")

    world.check(SMALL_ID)

    assert world.files.read_bytes(folder(world) / "Video 5.jpg") == b"my own picture"
    assert not world.files.exists(folder(world) / "New name.jpg")
    assert video(world).file_name == "New name.mkv"


def interrupted(world: World, new: str) -> None:
    """Mark a rename and move the file, as a rename the app's end stopped before storing."""
    world.repository.mark_rename(NEWEST, "Video 5.mkv", new)
    world.files.move(folder(world) / "Video 5.mkv", folder(world) / new)


def test_an_interrupted_rename_is_completed_and_the_file_never_trashed(tmp_path: Path) -> None:
    """R-QA-06, R-FN-06: the file moved but its name was not stored; the next check stores it."""
    world = synced(tmp_path, {"retitle": {NEWEST: "Moved already"}}, {})
    interrupted(world, "Moved already.mkv")
    spoil(world, "Moved already.mkv")

    world.check(SMALL_ID)

    assert video(world).file_name == "Moved already.mkv"
    assert video(world).rename_to is None
    assert world.files.read_bytes(folder(world) / "Moved already.mkv") == own_file(NEWEST)
    assert dates_of(world, "Moved already.mkv") == (PUBLISHED, PUBLISHED)


def test_an_interrupted_rename_is_settled_whatever_the_title_is_by_then(tmp_path: Path) -> None:
    """R-FN-06, R-QA-06: the marker, not the title, finds the file; then the new title follows.

    Found by the review of M4: with a second new title before the next check, the
    file was looked for under names of the newest title only and was lost track of.
    """
    world = synced(
        tmp_path, {"retitle": {NEWEST: "Second title"}}, {"retitle": {NEWEST: "Third title"}}
    )
    world.check(SMALL_ID)
    world.repository.mark_rename(NEWEST, "Second title.mkv", "Middle name.mkv")
    world.files.move(folder(world) / "Second title.mkv", folder(world) / "Middle name.mkv")

    world.check(SMALL_ID)

    assert video(world).file_name == "Third title.mkv"
    assert world.files.exists(folder(world) / "Third title.mkv")
    assert not world.files.exists(folder(world) / "Middle name.mkv")
    assert video(world).status is VideoStatus.SYNCED


def test_a_rename_that_did_not_move_the_file_is_undone(tmp_path: Path) -> None:
    """R-FN-06: a marker whose file still has its old name is cleared; nothing is lost."""
    world = synced(tmp_path, {})
    world.repository.mark_rename(NEWEST, "Video 5.mkv", "Never moved.mkv")

    world.check(SMALL_ID)

    assert (video(world).file_name, video(world).rename_to) == ("Video 5.mkv", None)
    assert video(world).status is VideoStatus.SYNCED


def test_a_file_of_another_video_under_the_new_name_is_not_taken(tmp_path: Path) -> None:
    """R-QA-06: only a file with this video's ID inside is taken as the moved one."""
    world = synced(tmp_path, {})
    world.repository.mark_rename(NEWEST, "Video 5.mkv", "Someone else.mkv")
    world.files.trash(folder(world) / "Video 5.mkv")
    world.files.add_files(folder(world), ["Someone else.mkv"], data=b"video:other000001")

    world.check(SMALL_ID)

    assert video(world).file_name == "Video 5.mkv"
    assert video(world).rename_to is None
    assert video(world).status is VideoStatus.FILE_MISSING


def test_the_file_goes_back_when_its_new_name_cannot_be_stored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-QA-06, R-FN-06: the video changed meanwhile; the file is where the catalogue says."""
    world = synced(tmp_path, {"retitle": {NEWEST: "New name"}})

    def changed_meanwhile(video_id: str, old: str, new: str) -> bool:
        return False

    monkeypatch.setattr(world.repository, "finish_rename", changed_meanwhile)

    world.check(SMALL_ID)

    assert world.files.exists(folder(world) / "Video 5.mkv")
    assert not world.files.exists(folder(world) / "New name.mkv")
    assert (video(world).file_name, video(world).rename_to) == ("Video 5.mkv", None)


def test_names_of_other_channels_in_a_shared_folder_are_taken(tmp_path: Path) -> None:
    """R-FN-05, R-FI-05: a name another channel tracks in the same folder is never reused."""
    world = synced(tmp_path, {"retitle": {NEWEST: "Shared name"}})
    other = world.repository.channels()[0]
    world.repository.add_channel(
        dataclasses.replace(other, id=BIG_ID, title="Big", handle="@big", position=1)
    )
    world.repository.apply_check(
        dataclasses.replace(other, id=BIG_ID, title="Big", handle="@big", position=1),
        CheckChanges(
            inserted=(
                dataclasses.replace(
                    video(world),
                    id="bg000000001",
                    channel_id=BIG_ID,
                    file_name="Shared name.mkv",
                ),
            ),
            updated=(),
            new=0,
            changed=0,
            removed=0,
            returned=0,
            read=0,
        ),
    )

    world.check(SMALL_ID)

    assert video(world).file_name == f"Shared name [{NEWEST}].mkv"


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


# --- missing files (R-MI-06, R-QU-11, D-087)


def test_a_deleted_file_makes_its_video_missing_at_the_next_check(tmp_path: Path) -> None:
    """R-MI-06, R-LG-03: "File missing", recorded with its reason, never downloaded by itself."""
    world = synced(tmp_path, {})
    world.files.trash(folder(world) / "Video 5.mkv")

    with capture_logs() as logs:
        world.check(SMALL_ID)

    assert video(world).status is VideoStatus.FILE_MISSING
    assert world.statuses(NEWEST)[-1] == ("synced", "file_missing", "file_not_found")
    assert [line["video_id"] for line in log_lines(logs, "file.missing")] == [NEWEST]
    assert world.downloads.job_of(NEWEST) is None


def test_opening_the_channel_finds_a_missing_file_too(tmp_path: Path) -> None:
    """R-MI-06: the files are looked for when the channel is opened."""
    world = synced(tmp_path)
    world.files.trash(folder(world) / "Video 5.mkv")

    world.state.open_channel(SMALL_ID)
    world.run_background()

    assert video(world).status is VideoStatus.FILE_MISSING


def test_a_file_put_back_from_the_trash_is_synced_again(tmp_path: Path) -> None:
    """R-MI-06: "Put Back" brings the same file back under its name; the video is synced again."""
    world = synced(tmp_path, {}, {})
    world.files.trash(folder(world) / "Video 5.mkv")
    world.check(SMALL_ID)

    world.files.add_files(folder(world), ["Video 5.mkv"], data=own_file(NEWEST))
    world.files.set_dates(folder(world) / "Video 5.mkv", PUBLISHED)
    with capture_logs() as logs:
        world.check(SMALL_ID)

    assert video(world).status is VideoStatus.SYNCED
    assert world.statuses(NEWEST)[-1] == ("file_missing", "synced", "file_back")
    assert log_lines(logs, "file.returned")


def test_a_file_put_back_is_synced_again_when_the_channel_is_opened(tmp_path: Path) -> None:
    """R-MI-06: opening the channel finds the file that came back."""
    world = synced(tmp_path)
    world.files.trash(folder(world) / "Video 5.mkv")
    world.state.open_channel(SMALL_ID)
    world.run_background()

    world.files.add_files(folder(world), ["Video 5.mkv"], data=own_file(NEWEST))
    world.state.open_channel(SMALL_ID)
    world.run_background()

    assert video(world).status is VideoStatus.SYNCED


def test_another_file_under_the_name_does_not_make_the_video_synced(tmp_path: Path) -> None:
    """R-MI-06: only a file with this video's ID inside is taken back."""
    world = synced(tmp_path, {}, {})
    world.files.trash(folder(world) / "Video 5.mkv")
    world.check(SMALL_ID)

    world.files.add_files(folder(world), ["Video 5.mkv"], data=b"video:other000001")
    world.check(SMALL_ID)

    assert video(world).status is VideoStatus.FILE_MISSING


def test_a_file_the_user_renamed_in_its_folder_counts_as_missing(tmp_path: Path) -> None:
    """R-MI-06: finding a renamed or moved file is adoption (M8), not a check."""
    world = synced(tmp_path, {})
    world.files.move(folder(world) / "Video 5.mkv", folder(world) / "My favourite.mkv")

    world.check(SMALL_ID)

    assert video(world).status is VideoStatus.FILE_MISSING
    assert world.files.exists(folder(world) / "My favourite.mkv")


def test_a_channel_folder_gone_from_a_connected_drive_is_folder_not_found(
    tmp_path: Path,
) -> None:
    """R-MI-06, D-087: no video is marked; the channel says "Folder not found"."""
    world = synced(tmp_path, {}, {})
    for path in [path for path in world.files.files if path.is_relative_to(folder(world))]:
        del world.files.files[path]
    world.files.folders = {
        path for path in world.files.folders if not path.is_relative_to(folder(world))
    }

    with capture_logs() as logs:
        world.check(SMALL_ID)

    assert video(world).status is VideoStatus.SYNCED
    view = world.views.of(SMALL_ID)
    assert view is not None
    assert view.status is ChannelStatus.FOLDER_NOT_FOUND
    assert log_lines(logs, "channel.folder_missing")
    assert log_lines(logs, "file.missing") == []


def test_a_channel_folder_that_is_there_again_ends_folder_not_found(tmp_path: Path) -> None:
    """R-MI-06: (D-087) the folder back in its place, the channel is as before."""
    world = synced(tmp_path, {}, {})
    world.files.folders.discard(folder(world))
    world.check(SMALL_ID)

    world.files.folders.add(folder(world))
    world.check(SMALL_ID)

    view = world.views.of(SMALL_ID)
    assert view is not None
    assert view.status is not ChannelStatus.FOLDER_NOT_FOUND
    assert video(world).status is VideoStatus.SYNCED


def test_a_drive_that_is_not_connected_marks_nothing(tmp_path: Path) -> None:
    """R-QU-11: an unplugged drive is unavailable, not missing: no status changes."""
    world = synced(tmp_path, {})
    world.files.disconnected.add(world.library)

    with capture_logs() as logs:
        world.check(SMALL_ID)

    assert video(world).status is VideoStatus.SYNCED
    view = world.views.of(SMALL_ID)
    assert view is not None
    assert view.status is not ChannelStatus.FOLDER_NOT_FOUND
    assert log_lines(logs, "file.unchecked")


def test_play_and_show_in_finder_say_the_file_is_missing(tmp_path: Path) -> None:
    """R-MI-06, R-UI-10: a plain FILE_MISSING, not "the folder cannot be used"."""
    world = synced(tmp_path)
    world.files.trash(folder(world) / "Video 5.mkv")

    for action in (world.downloader.play, world.downloader.reveal):
        with pytest.raises(AppError) as failure:
            action(NEWEST)
        assert failure.value.code is ErrorCode.FILE_MISSING


def test_a_missing_video_can_be_mirrored_again(tmp_path: Path) -> None:
    """R-MI-06: "Mirror again" puts it in line; it is synced with a new file."""
    world = synced(tmp_path, {})
    world.files.trash(folder(world) / "Video 5.mkv")
    world.check(SMALL_ID)

    world.downloader.mirror([NEWEST])
    world.download_all()

    assert video(world).status is VideoStatus.SYNCED
    assert world.files.exists(folder(world) / "Video 5.mkv")


def test_a_folder_that_cannot_be_listed_marks_nothing(tmp_path: Path) -> None:
    """R-MI-06, R-QU-11: a failed listing means unavailable, not missing."""
    world = synced(tmp_path, {})
    world.files.unlistable.add(folder(world))

    with capture_logs() as logs:
        world.check(SMALL_ID)

    assert video(world).status is VideoStatus.SYNCED
    assert log_lines(logs, "file.unchecked")


def test_files_are_looked_for_in_one_listing_not_one_by_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-MI-06: a folder that vanishes after its listing marks nothing it listed.

    Every check of a single file now fails, as on a drive that went away during the loop.
    """
    world = synced(tmp_path, {})

    def gone(path: Path) -> bool:
        return False

    monkeypatch.setattr(world.files, "exists", gone)

    world.check(SMALL_ID)

    assert video(world).status is VideoStatus.SYNCED


def test_a_video_whose_file_is_listed_again_but_cannot_be_read_stays_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-MI-06: a file whose own check fails is skipped, not taken back."""
    world = synced(tmp_path, {}, {})
    world.files.trash(folder(world) / "Video 5.mkv")
    world.check(SMALL_ID)
    world.files.add_files(folder(world), ["Video 5.mkv"], data=own_file(NEWEST))

    def unreadable(path: Path) -> None:
        raise OSError("Operation not permitted")

    monkeypatch.setattr(world.media, "probe", unreadable)
    with capture_logs() as logs:
        world.check(SMALL_ID)

    assert video(world).status is VideoStatus.FILE_MISSING
    assert log_lines(logs, "dates.repair.failed") == []


def test_a_file_a_download_is_placing_is_not_looked_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-MI-06, R-QA-06: while a download places its file, the file check leaves the video."""
    world = synced(tmp_path)
    placing = dataclasses.replace(video(world), placing_file="Video 5.mkv")
    world.files.trash(folder(world) / "Video 5.mkv")

    def only(channel_id: str) -> tuple[Video, ...]:
        return (placing,)

    monkeypatch.setattr(world.repository, "videos", only)

    world.repair.verify_files(SMALL_ID)

    assert world.statuses(NEWEST)[-1][1] == "synced"


def test_only_a_synced_video_can_become_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-MI-06, R-QA-08: a video in line for download whose file is gone is not marked."""
    world = synced(tmp_path)
    queued = dataclasses.replace(video(world), status=VideoStatus.QUEUED)
    world.files.trash(folder(world) / "Video 5.mkv")

    def only(channel_id: str) -> tuple[Video, ...]:
        return (queued,)

    monkeypatch.setattr(world.repository, "videos", only)

    world.repair.verify_files(SMALL_ID)

    assert world.statuses(NEWEST)[-1][1] == "synced"
