"""Tests of the downloader service: from "Mirror" to a synced file, and every way it can end."""

import dataclasses
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from structlog.testing import capture_logs

from tests.fixtures.fakes.media_tools import GOOD
from tests.fixtures.world import SMALL_ID, World, job_id, log_lines, own_file
from ytmirror.core.channels import ChannelStatus, Quality, VideoStatus
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.jobs import (
    Job,
    JobKind,
    JobProgressed,
    JobState,
    Stage,
    SubtitlesFailedError,
    VideoUpdated,
)
from ytmirror.core.models import Settings

PUBLISHED = 1_793_379_761
FIRST = "sm000000005"
"""The newest video of the small channel."""
SECOND = "sm000000004"
JOB1 = job_id(1)
"""The first job a test puts in line."""
CRASHED = job_id(98)
"""A job that a crash left running."""


@pytest.fixture
def world(tmp_path: Path) -> World:
    """The services with the small channel listed."""
    world = World(tmp_path)
    world.add_and_list()
    return world


def folder_of(world: World) -> Path:
    """Return the folder of the small channel."""
    return world.library / "Small Channel"


def title_of(world: World, video_id: str) -> str:
    """Return the title of a video in the catalogue."""
    video = world.repository.video(video_id)
    assert video is not None
    return video.title


def visible(world: World) -> list[str]:
    """Return the visible names in the channel folder."""
    return world.files.file_names(folder_of(world))


def everything(world: World) -> list[str]:
    """Return every file under the channel folder, hidden ones too, relative to it.

    The channel file belongs to the channel, not to a download (R-FI-05), so it is left out.
    """
    folder = folder_of(world)
    return sorted(
        str(path.relative_to(folder))
        for path in world.files.files
        if path.is_relative_to(folder) and path != folder / ".yt-mirror" / "channel.json"
    )


def status_of(world: World, video_id: str) -> VideoStatus:
    """Return the stored status of a video."""
    video = world.repository.video(video_id)
    assert video is not None
    return video.status


# --- putting videos in line


def test_mirror_puts_a_video_in_line(world: World) -> None:
    """R-MI-01, R-LG-03: Mirror queues the video, and the change is recorded with its job."""
    jobs = world.downloader.mirror([FIRST])

    assert [job.video_id for job in jobs] == [FIRST]
    assert status_of(world, FIRST) is VideoStatus.QUEUED
    assert world.statuses(FIRST) == [("not_downloaded", "queued", "mirror")]
    assert world.jobs.events(FIRST)[0].job_id == jobs[0].id
    assert world.video_updates()[-1].view.video.status is VideoStatus.QUEUED
    assert world.video_updates()[-1].view.job_id == jobs[0].id


def test_several_presses_of_mirror_download_one_after_another_in_that_order(
    world: World,
) -> None:
    """R-MI-01: Mirror on several rows gives several jobs, taken in the order of the presses."""
    for video_id in (SECOND, FIRST, "sm000000001"):
        world.downloader.mirror([video_id])

    world.download_all()

    assert [request.video_id for request in world.download.calls] == [SECOND, FIRST, "sm000000001"]
    assert {status_of(world, video_id) for video_id in (SECOND, FIRST)} == {VideoStatus.SYNCED}


def test_a_video_in_line_or_synced_is_not_put_in_line_again(world: World) -> None:
    """R-MI-01: pressing Mirror twice gives one job."""
    first = world.downloader.mirror([FIRST])
    again = world.downloader.mirror([FIRST])
    world.download_all()
    after = world.downloader.mirror([FIRST])

    assert (len(first), again, after) == (1, [], [])


def test_an_unknown_video_cannot_be_mirrored(world: World) -> None:
    """R-ER-02: only a video of a catalogue can be mirrored."""
    with pytest.raises(AppError) as failure:
        world.downloader.mirror(["nosuchvideo"])

    assert failure.value.code is ErrorCode.NOT_FOUND


def test_the_quality_of_the_channel_or_else_the_default_is_used(tmp_path: Path) -> None:
    """R-QL-02: a channel's own quality wins, the default quality applies otherwise."""
    world = World(tmp_path)
    world.add_and_list(quality=Quality.P720)
    world.settings_repository.save(Settings(default_quality=Quality.P1080))

    job = world.downloader.mirror([FIRST])[0]

    assert job.quality is Quality.P720


def test_without_a_channel_quality_the_default_quality_is_used(world: World) -> None:
    """R-QL-02: the default quality of the settings."""
    world.settings_repository.save(Settings(default_quality=Quality.P1080))

    job = world.downloader.mirror([FIRST])[0]
    world.download_all()

    assert job.quality is Quality.P1080
    assert world.download.calls[0].quality is Quality.P1080


# --- a download that works


def test_a_downloaded_video_is_synced_with_its_name_metadata_and_dates(world: World) -> None:
    """R-FN-01, R-MD-02, R-MD-05, R-DT-01, R-DT-07, R-LG-03: the whole flow of ARCHITECTURE 7.2."""
    world.downloader.mirror([FIRST])

    world.download_all()

    video = world.repository.video(FIRST)
    assert video is not None
    name = f"{title_of(world, FIRST)}.mkv"
    folder = folder_of(world)
    assert video.status is VideoStatus.SYNCED
    assert (video.file_name, video.height, video.vcodec, video.acodec) == (name, 270, "av1", "opus")
    assert video.has_subtitles == "manual"
    assert (video.published_at, video.published_exact, video.published_precision) == (
        PUBLISHED,
        True,
        None,
    )
    assert video.downloaded_at == world.now()
    assert video.file_size == len(own_file(FIRST))
    dates = world.files.read_dates(folder / name)
    assert (dates.created, dates.modified) == (PUBLISHED, PUBLISHED)
    assert everything(world) == sorted(
        [name, f".yt-mirror/{FIRST}.info.json", f".yt-mirror/{FIRST}.jpg"]
    )
    assert world.statuses(FIRST) == [
        ("not_downloaded", "queued", "mirror"),
        ("queued", "downloading", "started"),
        ("downloading", "processing", "streams done"),
        ("processing", "synced", "verified"),
    ]
    assert world.jobs.jobs([JobState.DONE])[0].video_id == FIRST


def test_the_file_is_named_after_the_title_in_the_catalogue(world: World) -> None:
    """R-FN-01, R-FN-07: the name comes from the title; the file is tracked by video ID."""
    world.downloader.mirror([FIRST])

    world.download_all()

    assert visible(world) == [f"{title_of(world, FIRST)}.mkv"]


def test_a_file_that_belongs_to_no_video_is_never_overwritten(world: World) -> None:
    """R-FN-05: a file of the same name gets the video ID in the new name, and stays as it was."""
    taken = f"{title_of(world, FIRST).upper()}.MKV"
    world.files.add_files(folder_of(world), [taken], data=b"the user's own")
    world.downloader.mirror([FIRST])

    world.download_all()

    assert f"{title_of(world, FIRST)} [{FIRST}].mkv" in visible(world)
    assert world.files.read_bytes(folder_of(world) / taken) == b"the user's own"


def test_a_premiere_gets_its_release_time_as_the_file_date(world: World) -> None:
    """R-DT-03, R-DT-07: the dates of a premiere's file are its release time."""
    world.download.release = PUBLISHED + 7200
    world.downloader.mirror([FIRST])

    world.download_all()

    dates = world.files.read_dates(folder_of(world) / f"{title_of(world, FIRST)}.mkv")
    assert (dates.created, dates.modified) == (PUBLISHED + 7200, PUBLISHED + 7200)


def test_the_thumbnail_is_saved_next_to_the_video_when_the_setting_asks(world: World) -> None:
    """R-MD-05: with the setting on, the thumbnail is also next to the video, with its dates."""
    world.settings_repository.save(Settings(thumbnail_next_to_video=True))
    world.downloader.mirror([FIRST])

    world.download_all()

    cover = folder_of(world) / f"{title_of(world, FIRST)}.jpg"
    assert world.files.read_bytes(cover) == b"twelve bytes"
    assert world.files.read_dates(cover).modified == PUBLISHED


def test_the_thumbnail_is_not_next_to_the_video_by_default(world: World) -> None:
    """R-MD-05: the visible thumbnail is off by default."""
    world.downloader.mirror([FIRST])

    world.download_all()

    assert visible(world) == [f"{title_of(world, FIRST)}.mkv"]


def test_subtitles_that_fail_never_fail_the_video(world: World) -> None:
    """R-MD-04: a subtitle failure gives one more try without subtitles, and it is logged."""
    world.download.subtitles_fail_once = True
    world.downloader.mirror([FIRST])

    with capture_logs() as logs:
        world.download_all()

    video = world.repository.video(FIRST)
    assert video is not None
    assert video.status is VideoStatus.SYNCED
    assert video.has_subtitles is None
    assert [request.manual_subtitles for request in world.download.calls] == [True, False]
    assert log_lines(logs, "download.retry")[0]["job_id"] == JOB1


def test_the_subtitle_settings_are_passed_on(world: World) -> None:
    """R-MD-03: both subtitle settings reach the download."""
    world.settings_repository.save(Settings(embed_subtitles=True, auto_subtitles=False))
    world.downloader.mirror([FIRST])

    world.download_all()

    request = world.download.calls[0]
    assert (request.manual_subtitles, request.auto_subtitles) == (True, False)


def test_every_log_line_of_a_download_has_its_job_id(world: World) -> None:
    """R-LG-02: the lines of a download carry its job ID, and yt-dlp writes to the job's log."""
    world.downloader.mirror([FIRST])

    with capture_logs() as logs:
        world.download_all()

    lines = [line for line in logs if str(line["event"]).startswith(("download.", "dates."))]
    assert {line["event"] for line in lines} >= {
        "download.started",
        "download.finished",
        "dates.applied",
    }
    assert {line["job_id"] for line in lines} == {JOB1}
    assert world.download.calls[0].log_file.name == f"{JOB1}.log"


def test_progress_is_told_and_the_channel_says_mirroring(world: World) -> None:
    """R-QU-04, R-FB-01: progress reaches the interface; the channel says "Mirroring X of Y"."""
    world.downloader.mirror([FIRST, SECOND])
    during = world.views.of(SMALL_ID)

    world.download_all()

    after = world.views.of(SMALL_ID)
    told = [event.progress for event in world.events if isinstance(event, JobProgressed)]
    assert during is not None
    assert after is not None
    assert (during.status, during.mirroring) == (ChannelStatus.MIRRORING, (0, 2))
    assert (after.status, after.mirroring) == (ChannelStatus.UP_TO_DATE, None)
    assert {progress.stage for progress in told} == {Stage.VIDEO, Stage.AUDIO, Stage.PROCESSING}


# --- a download that fails


def test_a_failed_download_says_why_and_leaves_nothing_behind(world: World) -> None:
    """R-QU-08, R-FI-03, R-LG-03: Failed with its code, no temp file, and the change recorded."""
    world.download.fail = AppError(ErrorCode.MEMBERS_ONLY, {"message": "members only"})
    world.downloader.mirror([FIRST])

    world.download_all()

    video = world.repository.video(FIRST)
    assert video is not None
    assert (video.status, video.last_error_code) == (VideoStatus.FAILED, ErrorCode.MEMBERS_ONLY)
    assert world.jobs.jobs([JobState.FAILED])[0].error_code is ErrorCode.MEMBERS_ONLY
    assert world.statuses(FIRST)[-1] == ("downloading", "failed", "MEMBERS_ONLY")
    assert everything(world) == []


def test_a_failed_video_can_be_retried(world: World) -> None:
    """R-QU-08, R-ER-03: Retry puts a failed video in line again, and it can then sync."""
    world.download.fail = AppError(ErrorCode.NETWORK_UNREACHABLE)
    world.downloader.mirror([FIRST])
    world.download_all()
    world.download.fail = None

    world.downloader.retry(FIRST)
    world.download_all()

    assert status_of(world, FIRST) is VideoStatus.SYNCED
    assert ("failed", "queued", "retry") in world.statuses(FIRST)


def test_only_a_failed_video_can_be_retried(world: World) -> None:
    """R-ER-02: Retry is for failed videos."""
    with pytest.raises(AppError) as failure:
        world.downloader.retry(FIRST)

    assert failure.value.code is ErrorCode.INVALID_REQUEST


def test_a_file_that_fails_verification_is_never_put_in_place(world: World) -> None:
    """R-QA-06: a file without audio fails verification and never looks finished."""
    work = folder_of(world) / ".yt-mirror" / "tmp" / JOB1 / f"{FIRST}.mkv"
    world.media.facts[work] = dataclasses.replace(GOOD, acodec=None)
    world.downloader.mirror([FIRST])

    world.download_all()

    assert status_of(world, FIRST) is VideoStatus.FAILED
    assert world.repository.video(FIRST).last_error_code is ErrorCode.VERIFY_FAILED  # pyright: ignore[reportOptionalMemberAccess]
    assert visible(world) == []


def test_a_file_whose_dates_cannot_be_set_never_reaches_the_folder(world: World) -> None:
    """R-DT-07, R-QA-06: the dates are set in the temp folder; a refusal fails the job there."""
    work = folder_of(world) / ".yt-mirror" / "tmp" / JOB1 / f"{FIRST}.mkv"
    world.files.refuse_dates.add(work)
    world.downloader.mirror([FIRST])

    world.download_all()

    video = world.repository.video(FIRST)
    assert video is not None
    assert (video.last_error_code, video.file_name) == (ErrorCode.DATES_NOT_APPLIED, None)
    assert everything(world) == []


def test_dates_that_read_back_different_fail_the_job(world: World) -> None:
    """R-DT-07: the dates are read back; a mismatch fails with DATES_NOT_APPLIED."""
    world.files.drift_dates.add(folder_of(world) / f"{title_of(world, FIRST)}.mkv")
    world.downloader.mirror([FIRST])

    with capture_logs() as logs:
        world.download_all()

    assert world.repository.video(FIRST).last_error_code is ErrorCode.DATES_NOT_APPLIED  # pyright: ignore[reportOptionalMemberAccess]
    assert visible(world) == []
    assert log_lines(logs, "dates.verify_failed")[0]["expected"] == PUBLISHED


def test_without_an_exact_time_no_date_is_made_up(world: World) -> None:
    """R-DT-04: a video whose metadata has no exact time fails instead of getting a guessed date."""
    world.download.published = None
    world.downloader.mirror([FIRST])

    world.download_all()

    assert world.repository.video(FIRST).last_error_code is ErrorCode.DATES_NOT_APPLIED  # pyright: ignore[reportOptionalMemberAccess]
    assert visible(world) == []


def test_an_unexpected_error_fails_the_video_as_internal(world: World) -> None:
    """R-ER-03: even an unexpected error leaves the video Failed, with Retry."""
    world.download.fail = RuntimeError("something nobody expected")
    world.downloader.mirror([FIRST])

    with capture_logs() as logs:
        world.download_all()

    assert world.repository.video(FIRST).last_error_code is ErrorCode.INTERNAL  # pyright: ignore[reportOptionalMemberAccess]
    assert log_lines(logs, "download.failed")[0]["error_code"] == "INTERNAL"


def test_youtubes_bot_check_puts_the_video_back_in_line_and_waits(world: World) -> None:
    """R-ER-05: not one error per video: the download waits until YouTube is asked again."""
    world.download.fail = AppError(ErrorCode.BOT_CHECK)
    world.downloader.mirror([FIRST])

    world.download_all()

    assert status_of(world, FIRST) is VideoStatus.QUEUED
    assert world.jobs.jobs([JobState.WAITING])[0].video_id == FIRST
    assert world.downloader.work_once() is False


# --- cancel


def test_cancel_of_a_waiting_video_takes_it_out_of_line(world: World) -> None:
    """R-QU-02, R-ER-03: Cancel of a queued video makes it "not downloaded" again."""
    job = world.downloader.mirror([FIRST])[0]

    cancelled = world.downloader.cancel(job.id)
    world.download_all()

    assert cancelled is True
    assert status_of(world, FIRST) is VideoStatus.NOT_DOWNLOADED
    assert world.download.calls == []
    assert world.statuses(FIRST)[-1] == ("queued", "not_downloaded", "cancelled")
    assert world.downloader.cancel(job.id) is False


@pytest.mark.parametrize("stage", [Stage.VIDEO, Stage.AUDIO, Stage.PROCESSING])
def test_cancel_while_downloading_or_merging_leaves_nothing_and_mirror_works_again(
    world: World, stage: Stage
) -> None:
    """R-QU-02, R-FI-03: a cancel at any stage leaves no file, and Mirror works again."""
    world.files.add_files(folder_of(world), ["Another video.mkv"], data=b"keep me")
    before = everything(world)
    job = world.downloader.mirror([FIRST])[0]
    world.download.cancel_at = stage
    world.download.on_cancel = lambda: world.downloader.cancel(job.id)

    world.download_all()

    assert status_of(world, FIRST) is VideoStatus.NOT_DOWNLOADED
    assert everything(world) == before
    assert world.files.read_bytes(folder_of(world) / "Another video.mkv") == b"keep me"
    world.download.cancel_at = None
    world.downloader.mirror([FIRST])
    world.download_all()
    assert status_of(world, FIRST) is VideoStatus.SYNCED


def test_cancel_after_the_merge_and_before_the_move_leaves_nothing(world: World) -> None:
    """R-QU-02: a cancel during the last steps, before the file is moved, still ends it clean."""
    job = world.downloader.mirror([FIRST])[0]
    probe = world.media.probe

    def probe_and_cancel(path: Path) -> object:
        world.downloader.cancel(job.id)
        return probe(path)

    world.files.add_files(folder_of(world), ["Another video.mkv"], data=b"keep me")
    before = everything(world)
    world.media.probe = probe_and_cancel  # type: ignore[method-assign]
    world.download_all()

    assert status_of(world, FIRST) is VideoStatus.NOT_DOWNLOADED
    assert everything(world) == before


def test_quitting_during_a_download_leaves_the_same_clean_state(world: World) -> None:
    """R-PL-13, R-QA-06: a quit cancels the running download and deletes its temp files."""
    world.downloader.mirror([FIRST])
    world.download.cancel_at = Stage.AUDIO
    world.download.on_cancel = lambda: world.downloader.stop(wait_s=0)

    world.download_all()

    assert status_of(world, FIRST) is VideoStatus.NOT_DOWNLOADED
    assert everything(world) == []


def test_a_start_cleans_up_what_a_crash_left(world: World) -> None:
    """R-QA-06: jobs a crash left running or waiting are cleaned up at the next start."""
    video = world.repository.video(FIRST)
    assert video is not None
    job = Job(CRASHED, FIRST, JobKind.DOWNLOAD, JobState.RUNNING, 1, Quality.BEST, world.now())
    world.jobs.record(job, dataclasses.replace(video, status=VideoStatus.DOWNLOADING))
    work = folder_of(world) / ".yt-mirror" / "tmp" / CRASHED
    world.files.add_files(work, [f"{FIRST}.f397.mp4.part"])

    world.downloader.start()

    assert status_of(world, FIRST) is VideoStatus.NOT_DOWNLOADED
    assert world.jobs.job(CRASHED).state is JobState.CANCELLED  # pyright: ignore[reportOptionalMemberAccess]
    assert world.files.exists(work) is False


def test_removing_a_channel_cancels_its_downloads_first(world: World) -> None:
    """R-CH-32: a channel that is removed has no download left in line."""
    world.downloader.mirror([FIRST, SECOND])

    world.channels.remove(SMALL_ID, keep_files=False)

    assert world.jobs.jobs([JobState.WAITING, JobState.RUNNING]) == ()
    assert world.download.calls == []


# --- play and show in Finder


def test_play_and_show_in_finder_use_the_file_of_the_video(world: World) -> None:
    """R-UI-10: Play opens the file, Show in Finder reveals it."""
    world.downloader.mirror([FIRST])
    world.download_all()
    file = folder_of(world) / f"{title_of(world, FIRST)}.mkv"

    world.downloader.play(FIRST)
    world.downloader.reveal(FIRST)

    assert world.files.played == [file]
    assert world.files.revealed == [file]


def test_a_video_without_a_file_can_be_neither_played_nor_shown(world: World) -> None:
    """R-UI-10, R-ER-02: a video that was never downloaded has no file to open."""
    with pytest.raises(AppError) as failure:
        world.downloader.play(FIRST)

    assert failure.value.code is ErrorCode.NOT_FOUND


# --- what a crash or a broken job leaves


class Killed(BaseException):
    """Stands for the end of the process: nothing after it runs in the job."""


def test_a_crash_between_the_move_and_the_end_of_the_job_leaves_no_unknown_file(
    world: World,
) -> None:
    """R-QA-06, R-FN-05: the next start trashes the moved file; Mirror gets the name again."""
    world.downloader.mirror([FIRST])
    name = f"{title_of(world, FIRST)}.mkv"
    read_dates = world.files.read_dates

    def die(path: Path) -> object:
        raise Killed

    ours(world, name)
    world.files.read_dates = die  # type: ignore[method-assign]
    with pytest.raises(Killed):
        world.downloader.work_once()
    world.files.read_dates = read_dates  # type: ignore[method-assign]

    world.downloader.start()

    assert world.files.trashed == [folder_of(world) / name]
    video = world.repository.video(FIRST)
    assert video is not None
    assert (video.status, video.file_name) == (VideoStatus.NOT_DOWNLOADED, None)
    world.downloader.mirror([FIRST])
    world.download_all()
    assert visible(world) == [name]


def test_two_jobs_for_one_video_do_not_stop_the_queue(world: World) -> None:
    """R-ER-03: a job that cannot run ends, and the jobs behind it still run."""
    first = world.downloader.mirror([FIRST])[0]
    duplicate = dataclasses.replace(first, id=job_id(99), priority=first.priority + 1)
    world.jobs.record(duplicate)
    world.downloader.mirror([SECOND])

    world.download_all()

    assert status_of(world, FIRST) is VideoStatus.SYNCED
    assert status_of(world, SECOND) is VideoStatus.SYNCED
    assert world.jobs.jobs([JobState.WAITING, JobState.RUNNING]) == ()


def test_a_second_press_of_mirror_or_retry_gives_no_second_job(world: World) -> None:
    """R-MI-01, R-QU-08: a job per video, however often it is pressed."""
    world.download.fail = AppError(ErrorCode.NETWORK_UNREACHABLE)
    world.downloader.mirror([FIRST])
    world.download_all()

    world.downloader.retry(FIRST)
    with pytest.raises(AppError):
        world.downloader.retry(FIRST)

    assert len(world.jobs.jobs([JobState.WAITING])) == 1


def test_a_channel_removed_while_its_video_downloads_breaks_nothing(world: World) -> None:
    """R-CH-32, R-ER-03: the job ends with its video, and the worker goes on."""
    world.downloader.mirror([FIRST])
    world.download.cancel_at = Stage.AUDIO
    world.download.on_cancel = lambda: world.repository.remove_channel(SMALL_ID)

    world.download_all()

    assert world.repository.video(FIRST) is None
    assert world.downloader.work_once() is False


# --- after the file is in its place (review of M3, H1 and H2)


def ours(world: World, name: str) -> None:
    """Make the fake media tools read a file in the channel folder as the app's own download."""
    world.media.facts[folder_of(world) / name] = dataclasses.replace(GOOD, tags={"video_id": FIRST})


def test_a_side_file_that_fails_leaves_the_video_synced_and_is_written_later(world: World) -> None:
    """R-QA-06, R-MD-02: a full disk at the info JSON keeps the synced video; it is retried."""
    write = world.files.write_file
    full = {"disk": True}

    def write_unless_full(path: Path, data: bytes, *, overwrite: bool, inside: Path) -> bool:
        if full["disk"] and path.name == f"{FIRST}.info.json":
            raise AppError(ErrorCode.DISK_FULL, {"file": str(path)})
        return write(path, data, overwrite=overwrite, inside=inside)

    world.files.write_file = write_unless_full  # type: ignore[method-assign]
    world.downloader.mirror([FIRST])

    with capture_logs() as logs:
        world.download_all()

    video = world.repository.video(FIRST)
    assert video is not None
    name = f"{title_of(world, FIRST)}.mkv"
    assert (video.status, video.file_name, video.placing_file) == (VideoStatus.SYNCED, name, None)
    assert visible(world) == [name]
    assert log_lines(logs, "download.side_file_failed")[0]["file"].endswith(".info.json")
    assert not world.files.exists(folder_of(world) / ".yt-mirror" / f"{FIRST}.info.json")
    full["disk"] = False
    world.downloader.retry_side_files()
    assert world.files.exists(folder_of(world) / ".yt-mirror" / f"{FIRST}.info.json")
    assert world.jobs.pending_side_files() == ()


def test_a_thumbnail_next_to_the_video_that_fails_leaves_nothing_and_the_video_synced(
    world: World,
) -> None:
    """R-MD-05, R-QA-06: the visible thumbnail never stands in the folder with wrong dates."""
    world.settings_repository.save(Settings(thumbnail_next_to_video=True))
    set_dates = world.files.set_dates

    def refuse_pictures(path: Path, moment: int) -> None:
        if path.suffix == ".jpg":
            raise AppError(ErrorCode.DATES_NOT_APPLIED, {"file": str(path)})
        set_dates(path, moment)

    world.files.set_dates = refuse_pictures  # type: ignore[method-assign]
    world.downloader.mirror([FIRST])
    world.download_all()

    assert status_of(world, FIRST) is VideoStatus.SYNCED
    assert visible(world) == [f"{title_of(world, FIRST)}.mkv"]
    world.files.set_dates = set_dates  # type: ignore[method-assign]
    world.downloader.retry_side_files()
    assert visible(world) == sorted(
        [f"{title_of(world, FIRST)}.mkv", f"{title_of(world, FIRST)}.jpg"]
    )


def test_dates_that_cannot_even_be_read_take_the_file_out_again(world: World) -> None:
    """R-DT-07, R-QA-06: an OSError while reading the dates back also moves the file out."""

    def unreadable(path: Path) -> object:
        raise OSError(5, "Input/output error", str(path))

    world.files.read_dates = unreadable  # type: ignore[method-assign]
    world.downloader.mirror([FIRST])
    world.download_all()

    video = world.repository.video(FIRST)
    assert video is not None
    assert (video.status, video.file_name, video.placing_file) == (VideoStatus.FAILED, None, None)
    assert video.last_error_code is ErrorCode.DATES_NOT_APPLIED
    assert visible(world) == []


def test_a_failure_while_the_video_is_stored_as_synced_takes_the_file_out_again(
    world: World,
) -> None:
    """R-QA-06: any failure after the move but the side files leaves no file in the folder."""
    record = world.jobs.record

    def refuse_synced(
        job: Job, video: object = None, change: object = None, side_files: object = ()
    ) -> None:
        if getattr(change, "to_status", None) is VideoStatus.SYNCED:
            raise RuntimeError("the database is locked")
        record(job, video, change, side_files)  # type: ignore[arg-type]

    world.jobs.record = refuse_synced  # type: ignore[method-assign]
    world.downloader.mirror([FIRST])
    world.download_all()

    assert status_of(world, FIRST) is VideoStatus.FAILED
    assert visible(world) == []


def test_a_trash_that_refuses_at_start_never_stops_the_app(world: World) -> None:
    """R-QA-06, R-ER-03: the start goes on, logs it, and ends the job anyway."""
    world.downloader.mirror([FIRST])
    name = f"{title_of(world, FIRST)}.mkv"
    ours(world, name)
    read_dates = world.files.read_dates

    def die(path: Path) -> object:
        raise Killed

    world.files.read_dates = die  # type: ignore[method-assign]
    with pytest.raises(Killed):
        world.downloader.work_once()
    world.files.read_dates = read_dates  # type: ignore[method-assign]

    def refuse(path: Path) -> None:
        raise AppError(ErrorCode.PERMISSION_DENIED, {"file": str(path)})

    world.files.trash = refuse  # type: ignore[method-assign]
    with capture_logs() as logs:
        world.downloader.start()
        world.downloader.start()

    assert log_lines(logs, "file.trash_failed")[0]["error_code"] == "PERMISSION_DENIED"
    assert world.jobs.jobs([JobState.WAITING, JobState.RUNNING]) == ()
    assert status_of(world, FIRST) is VideoStatus.NOT_DOWNLOADED


def test_a_start_trashes_only_a_file_the_app_was_placing_and_that_is_its_own(
    world: World,
) -> None:
    """R-QA-06: the marker says what the app moved; a file that is not this video stays."""
    world.downloader.mirror([FIRST])
    name = f"{title_of(world, FIRST)}.mkv"
    world.media.facts[folder_of(world) / name] = dataclasses.replace(
        GOOD, tags={"video_id": "someoneelse"}
    )
    read_dates = world.files.read_dates

    def die(path: Path) -> object:
        raise Killed

    world.files.read_dates = die  # type: ignore[method-assign]
    with pytest.raises(Killed):
        world.downloader.work_once()
    world.files.read_dates = read_dates  # type: ignore[method-assign]
    assert world.repository.video(FIRST).placing_file == name  # pyright: ignore[reportOptionalMemberAccess]

    world.downloader.start()

    assert world.files.trashed == []
    assert world.files.exists(folder_of(world) / name)
    assert world.repository.video(FIRST).placing_file is None  # pyright: ignore[reportOptionalMemberAccess]


# --- threads: the worker, and a removal during a download (review of M3)


def in_a_thread(work: Callable[[], object]) -> threading.Thread:
    """Start work in a thread of its own."""
    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    return thread


def held_at_audio(world: World) -> tuple[threading.Event, threading.Event]:
    """Make the download stop at the audio stage until the test lets it go on.

    Returns the event that says it is held, and the one that lets it go.
    """
    held, go = threading.Event(), threading.Event()

    def hold() -> None:
        held.set()
        go.wait(10)

    world.download.cancel_at = Stage.AUDIO
    world.download.on_cancel = hold
    return held, go


def test_cancel_channel_returns_only_when_the_download_has_ended(world: World) -> None:
    """R-CH-32, R-QU-02: the removal can rely on no download of the channel running any more."""
    world.downloader.mirror([FIRST])
    held, go = held_at_audio(world)
    worker = in_a_thread(world.downloader.work_once)
    assert held.wait(10)

    cancelling = in_a_thread(lambda: world.downloader.cancel_channel(SMALL_ID))
    cancelling.join(0.3)
    still_waiting = cancelling.is_alive()
    go.set()
    cancelling.join(10)
    worker.join(10)

    assert still_waiting
    assert [job.state for job in world.jobs.jobs(list(JobState))] == [JobState.CANCELLED]
    assert world.repository.video(FIRST).status is VideoStatus.NOT_DOWNLOADED  # type: ignore[union-attr]


def test_removing_a_channel_while_its_video_downloads_leaves_nothing(world: World) -> None:
    """R-CH-32, R-QA-06: the download ends first, then the files and the folder go for good."""
    world.downloader.mirror([FIRST])
    held, go = held_at_audio(world)
    worker = in_a_thread(world.downloader.work_once)
    assert held.wait(10)

    removing = in_a_thread(lambda: world.channels.remove(SMALL_ID, keep_files=False))
    removing.join(0.3)
    trashed_while_running = list(world.files.trashed)
    go.set()
    removing.join(10)
    worker.join(10)

    assert trashed_while_running == []
    assert not removing.is_alive()
    assert world.files.folder_exists(folder_of(world)) is False
    assert world.repository.channels() == ()
    assert world.jobs.jobs(list(JobState)) == ()


def test_the_worker_downloads_what_is_put_in_line_and_ends_when_the_app_stops(
    world: World,
) -> None:
    """R-MI-01, R-PL-13: the worker thread takes jobs as they come, and stops with the app."""
    world.downloader.start()
    worker = in_a_thread(world.background.pop())

    world.downloader.mirror([FIRST])
    deadline = time.monotonic() + 10
    while world.repository.video(FIRST).status is not VideoStatus.SYNCED:  # type: ignore[union-attr]
        assert time.monotonic() < deadline, "the worker did not download the video"
        time.sleep(0.01)
    world.downloader.stop()
    worker.join(10)

    assert not worker.is_alive()


def test_the_worker_goes_on_after_an_unexpected_error(world: World) -> None:
    """R-ER-03: an error the worker did not expect is logged, and the next job still runs."""
    work_once = world.downloader.work_once
    calls: list[int] = []

    def broken_once() -> bool:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("unexpected")
        return work_once()

    world.downloader.work_once = broken_once  # type: ignore[method-assign]
    world.downloader.start()
    worker = in_a_thread(world.background.pop())

    with capture_logs() as logs:
        world.downloader.mirror([FIRST])
        deadline = time.monotonic() + 10
        while world.repository.video(FIRST).status is not VideoStatus.SYNCED:  # type: ignore[union-attr]
            assert time.monotonic() < deadline, "the worker stopped after the error"
            time.sleep(0.01)
    world.downloader.stop()
    worker.join(10)

    assert log_lines(logs, "download.failed")[0]["error_code"] == "INTERNAL"
    assert not worker.is_alive()


def test_quitting_stops_the_tools_so_a_running_download_ends_at_once(world: World) -> None:
    """R-PL-13, R-QA-06: the ffmpeg of a running job is stopped, and the job is cleaned up."""
    world.downloader.mirror([FIRST])
    held, go = held_at_audio(world)
    world.stop_tools = go.set
    worker = in_a_thread(world.downloader.work_once)
    assert held.wait(10)

    world.downloader.stop(wait_s=10)
    worker.join(10)

    assert go.is_set()
    assert [job.state for job in world.jobs.jobs(list(JobState))] == [JobState.CANCELLED]
    assert world.files.file_names(folder_of(world)) == []


# --- the synced commit is the point of no return (second review of M3, H1 and L3)


def test_a_listener_that_fails_after_the_synced_commit_never_touches_the_file(
    world: World,
) -> None:
    """R-QA-06, AGENTS rule 7: once stored as synced, the file stays, whatever fails next."""

    def fail_on_synced(event: object) -> None:
        if isinstance(event, VideoUpdated) and event.view.video.status is VideoStatus.SYNCED:
            raise RuntimeError("a listener failed")

    world.bus.subscribe(fail_on_synced)
    world.downloader.mirror([FIRST])

    with capture_logs() as logs:
        world.download_all()

    name = f"{title_of(world, FIRST)}.mkv"
    video = world.repository.video(FIRST)
    assert video is not None
    assert (video.status, video.file_name) == (VideoStatus.SYNCED, name)
    assert world.files.exists(folder_of(world) / name)
    assert world.files.trashed == []
    assert [job.state for job in world.jobs.jobs(list(JobState))] == [JobState.DONE]
    assert log_lines(logs, "download.tell_failed")[0]["video_id"] == FIRST


def test_a_crash_right_after_the_synced_commit_keeps_the_side_files_to_write(
    world: World,
) -> None:
    """R-QA-06, R-MD-02: the side files are stored with the synced video, in one transaction."""
    write = world.files.write_file

    def crash_at_the_side_files(path: Path, data: bytes, *, overwrite: bool, inside: Path) -> bool:
        if path.name.endswith(".info.json"):
            raise Killed
        return write(path, data, overwrite=overwrite, inside=inside)

    world.files.write_file = crash_at_the_side_files  # type: ignore[method-assign]
    world.downloader.mirror([FIRST])
    with pytest.raises(Killed):
        world.downloader.work_once()

    waiting = {pending.path for pending in world.jobs.pending_side_files()}
    assert world.repository.video(FIRST).status is VideoStatus.SYNCED  # type: ignore[union-attr]
    assert waiting == {f".yt-mirror/{FIRST}.info.json", f".yt-mirror/{FIRST}.jpg"}

    world.files.write_file = write  # type: ignore[method-assign]
    world.downloader.retry_side_files()

    assert world.jobs.pending_side_files() == ()
    assert world.files.exists(folder_of(world) / ".yt-mirror" / f"{FIRST}.info.json")


# --- a quit is a cancel (second review of M3, M2)


def killed_at(world: World, stage: Stage, error: Exception) -> threading.Event:
    """Hold the download at a stage; stopping the tools makes that step fail like a killed ffmpeg.

    Returns the event that says the download is held.
    """
    held, killed = threading.Event(), threading.Event()

    def hold() -> None:
        held.set()
        killed.wait(10)
        raise error

    world.download.cancel_at = stage
    world.download.on_cancel = hold
    world.stop_tools = killed.set
    return held


@pytest.mark.parametrize(
    "error",
    [
        AppError(ErrorCode.FFMPEG_FAILED, {"message": "Conversion failed!"}),
        SubtitlesFailedError("ERROR: Postprocessing: Conversion failed!"),
    ],
    ids=["merge", "subtitles"],
)
def test_quitting_while_ffmpeg_runs_cancels_and_never_fails_or_retries(
    world: World, error: Exception
) -> None:
    """R-PL-13, R-QU-02: the error of the stopped ffmpeg is a cancel, never FAILED nor a retry."""
    world.downloader.mirror([FIRST])
    held = killed_at(world, Stage.PROCESSING, error)
    worker = in_a_thread(world.downloader.work_once)
    assert held.wait(10)

    world.downloader.stop(wait_s=10)
    worker.join(10)

    video = world.repository.video(FIRST)
    assert video is not None
    assert (video.status, video.last_error_code) == (VideoStatus.NOT_DOWNLOADED, None)
    assert [job.state for job in world.jobs.jobs(list(JobState))] == [JobState.CANCELLED]
    assert len(world.download.calls) == 1


# --- Cancel stops the ffmpeg of its job (second review of M3, M3)


def test_cancel_stops_the_ffmpeg_of_its_own_job(world: World) -> None:
    """R-QU-02, R-CH-32: a step that copies a large file is not left writing after a cancel."""
    [job] = world.downloader.mirror([FIRST])
    held, go = held_at_audio(world)
    worker = in_a_thread(world.downloader.work_once)
    assert held.wait(10)

    world.downloader.cancel(job.id)
    go.set()
    worker.join(10)

    work = folder_of(world) / ".yt-mirror" / "tmp" / job.id
    assert world.stopped_job_tools == [work]


# --- the start cleans up what a quit left (second review of M3, L1 and L2)


def test_a_marker_stays_until_its_folder_can_be_reached(world: World) -> None:
    """R-QA-06: a drive that is not connected at start keeps the marker; a later start cleans up."""
    world.downloader.mirror([FIRST])
    name = f"{title_of(world, FIRST)}.mkv"
    ours(world, name)
    read_dates = world.files.read_dates

    def die(path: Path) -> object:
        raise Killed

    world.files.read_dates = die  # type: ignore[method-assign]
    with pytest.raises(Killed):
        world.downloader.work_once()
    world.files.read_dates = read_dates  # type: ignore[method-assign]
    folder = folder_of(world)
    exists = world.files.folder_exists
    world.files.folder_exists = lambda path: path != folder and exists(path)  # type: ignore[method-assign]

    world.downloader.start()

    assert world.repository.video(FIRST).placing_file == name  # type: ignore[union-attr]
    assert world.files.trashed == []

    world.files.folder_exists = exists  # type: ignore[method-assign]
    world.downloader.start()

    assert world.repository.video(FIRST).placing_file is None  # type: ignore[union-attr]
    assert world.files.trashed == [folder / name]


def test_a_start_sweeps_the_temp_folders_of_jobs_that_ended(world: World) -> None:
    """R-FI-03, R-QA-06: a temp folder a quit left behind goes; anything else there stays."""
    temp = folder_of(world) / ".yt-mirror" / "tmp"
    stale = job_id(90)
    world.files.add_files(temp / stale, ["part.mkv"])
    world.files.add_files(temp / "not a job", ["mine.txt"])

    with capture_logs() as logs:
        world.downloader.start()

    assert not world.files.exists(temp / stale)
    assert world.files.exists(temp / "not a job" / "mine.txt")
    assert log_lines(logs, "download.temp_swept")[0]["job_id"] == stale
