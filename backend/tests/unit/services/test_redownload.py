"""Tests of a re-download: the old file stays until the new one is in place (R-QL-06, D-093)."""

import dataclasses
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text

from tests.fixtures.world import SMALL_ID, World
from ytmirror.core.channels import Quality, VideoStatus
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.jobs import DownloadProgress, Job, JobKind, JobState, Stage

FIRST = "sm000000005"
PUBLISHED = 1_793_379_761


class Killed(BaseException):
    """Stands in for the end of the process: nothing after it runs."""


@pytest.fixture
def world(tmp_path: Path) -> World:
    """A world whose newest video is synced."""
    world = World(tmp_path)
    world.add_and_list()
    world.downloader.mirror([FIRST])
    world.download_all()
    return world


def file_of(world: World) -> Path:
    """The file of the newest video, under its stored name."""
    return world.downloader.file_of(FIRST)


def visible(world: World) -> list[str]:
    """The names in the channel folder that a user sees."""
    return sorted(name for name in world.files.file_names(file_of(world).parent))


def test_a_redownload_swaps_the_new_file_in_and_the_old_one_to_the_trash(world: World) -> None:
    """R-QL-06, R-DT-10, D-093: same name, new file with the published dates, old one trashed."""
    old = world.files.file_id(file_of(world))
    statuses_before = world.statuses(FIRST)

    [job] = world.downloader.redownload([FIRST])
    assert job.kind is JobKind.REDOWNLOAD
    world.download_all()

    video = world.repository.video(FIRST)
    assert video is not None
    assert (video.status, video.replacing) == (VideoStatus.SYNCED, None)
    assert world.files.file_id(file_of(world)) != old
    dates = world.files.read_dates(file_of(world))
    assert (dates.created, dates.modified) == (PUBLISHED, PUBLISHED)
    [trashed] = world.files.trashed
    assert ".yt-mirror/tmp" in str(trashed)
    assert world.statuses(FIRST) == statuses_before, "the video never left synced"
    assert len(visible(world)) == 1


def test_a_failed_redownload_leaves_the_old_file_and_the_video_synced(world: World) -> None:
    """R-QL-06, D-093: a failure changes nothing of the video or its file."""
    old = world.files.file_id(file_of(world))
    world.download.fail = AppError(ErrorCode.MEMBERS_ONLY, {})

    world.downloader.redownload([FIRST])
    world.download_all()

    video = world.repository.video(FIRST)
    assert video is not None
    assert (video.status, video.last_error_code) == (VideoStatus.SYNCED, None)
    assert world.files.file_id(file_of(world)) == old
    assert world.files.trashed == []
    assert [job.state for job in world.jobs.jobs([JobState.FAILED])] == [JobState.FAILED]


def test_a_cancelled_redownload_leaves_the_old_file(world: World) -> None:
    """R-QL-06, R-QU-02: Cancel of a re-download keeps the old file and the video synced."""
    old = world.files.file_id(file_of(world))
    [job] = world.downloader.redownload([FIRST])
    world.download.cancel_at = Stage.AUDIO
    world.download.on_cancel = lambda: world.downloader.cancel(job.id)

    world.download_all()

    assert world.repository.video(FIRST).status is VideoStatus.SYNCED  # type: ignore[union-attr]
    assert world.files.file_id(file_of(world)) == old
    assert world.files.trashed == []


def test_a_crash_right_after_the_swap_is_undone_at_the_next_start(world: World) -> None:
    """R-QL-06, R-QA-06, D-093: the stored facts and the file always belong together."""
    old = world.files.file_id(file_of(world))
    world.downloader.redownload([FIRST])
    record = world.jobs.record

    def die(job: Job, *args: Any, **kwargs: Any) -> None:
        if job.state is JobState.DONE:
            raise Killed  # the process ends before the new file is stored
        record(job, *args, **kwargs)

    world.jobs.record = die  # type: ignore[method-assign]
    with pytest.raises(Killed):
        world.downloader.work_once()
    world.jobs.record = record  # type: ignore[method-assign]
    assert world.files.file_id(file_of(world)) != old
    assert world.repository.video(FIRST).replacing is not None  # type: ignore[union-attr]

    world.downloader.start()

    assert world.files.file_id(file_of(world)) == old
    assert world.repository.video(FIRST).replacing is None  # type: ignore[union-attr]
    assert world.files.trashed == []


def test_a_rename_during_a_redownload_is_not_undone(world: World) -> None:
    """R-FN-06, D-093: the swap goes to the file's name at its end, under the rename lock."""

    def retitled(_tell: Callable[[DownloadProgress], None]) -> None:
        with world.engine.begin() as connection:
            connection.execute(
                text("UPDATE videos SET title = 'A new title' WHERE id = :id"), {"id": FIRST}
            )
        world.repair.after_check(SMALL_ID)

    world.downloader.redownload([FIRST])
    world.download.during_video = retitled

    world.download_all()

    assert file_of(world).name == "A new title.mkv"
    assert visible(world) == ["A new title.mkv"]
    assert world.repository.video(FIRST).replacing is None  # type: ignore[union-attr]


def test_only_a_synced_video_is_downloaded_again(world: World) -> None:
    """R-QL-06: a video without a file is mirrored, not downloaded again."""
    assert world.downloader.redownload(["sm000000004"]) == []


def test_a_file_lower_than_the_quality_of_its_channel_is_marked(world: World) -> None:
    """R-QL-07: the list marks a synced video whose height is below the target now."""
    channel = world.repository.channel(SMALL_ID)
    assert channel is not None
    view = world.views.video(FIRST)
    assert view is not None
    assert view.below_target is False
    height = view.video.height
    assert height is not None

    target = next(q for q in (Quality.P2160, Quality.P1440, Quality.P1080) if int(q.value) > height)
    world.repository.save_channel(dataclasses.replace(channel, quality=target))

    view = world.views.video(FIRST)
    assert view is not None
    assert view.below_target is True


def test_an_old_file_the_trash_refuses_is_kept_not_deleted(world: World) -> None:
    """R-QL-06, D-093: the old file never goes for good; it waits in the hidden folder."""
    old = world.files.file_id(file_of(world))

    def refuse(path: Path) -> None:
        raise AppError(ErrorCode.PERMISSION_DENIED, {"file": str(path)})

    world.files.trash = refuse  # type: ignore[method-assign]
    world.downloader.redownload([FIRST])
    world.download_all()

    kept = file_of(world).parent / ".yt-mirror" / f"{FIRST}.replaced.mkv"
    assert world.files.file_id(kept) == old
