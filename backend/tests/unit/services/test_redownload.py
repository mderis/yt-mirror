"""Tests of a re-download: the old file stays until the new one is in place (R-QL-06, D-093)."""

import threading
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
    before = world.repository.video(FIRST)
    assert before is not None
    world.downloader.redownload([FIRST])
    world.clock.advance(60)
    record = world.jobs.record

    def die(job: Job, *args: Any, **kwargs: Any) -> None:
        video = args[0] if args else None
        if video is not None and video.downloaded_at != before.downloaded_at:
            raise Killed  # the process ends before the new file is stored
        record(job, *args, **kwargs)

    world.jobs.record = die  # type: ignore[method-assign]
    with pytest.raises(Killed):
        world.downloader.work_once()
    world.jobs.record = record  # type: ignore[method-assign]
    assert world.files.file_id(file_of(world)) != old
    assert world.repository.video(FIRST).replacing is not None  # type: ignore[union-attr]

    world.new_downloader().start()

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
    world.repository.update_channel(channel.id, quality=target)

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

    [kept] = [name for name in world.files.file_names(hidden(world)) if "replaced" in name]
    assert world.files.file_id(hidden(world) / kept) == old
    assert world.repository.video(FIRST).replacing is None  # type: ignore[union-attr]


# --- the old file is never deleted for good (review of M5: High 1 and 2)


def hidden(world: World) -> Path:
    """The hidden folder of the channel."""
    return file_of(world).parent / ".yt-mirror"


def no_active_job(world: World) -> bool:
    """Whether the newest video has no job that waits or runs."""
    return world.jobs.active_job_of(FIRST) is None


def test_a_quit_after_the_new_file_was_stored_is_finished_at_the_next_start(world: World) -> None:
    """R-QL-06, D-093: the old file still in the temp folder goes to the Trash, never away."""
    old = world.files.file_id(file_of(world))
    trash = world.files.trash

    def die(_path: Path) -> None:
        raise Killed  # the process ends while the old file is on its way to the Trash

    world.downloader.redownload([FIRST])
    world.files.trash = die  # type: ignore[method-assign]
    with pytest.raises(Killed):
        world.downloader.work_once()
    world.files.trash = trash  # type: ignore[method-assign]

    world.new_downloader().start()

    assert world.files.destroyed == []
    assert len(world.files.trashed) == 1
    assert world.files.file_id(file_of(world)) != old
    assert world.repository.video(FIRST).replacing is None  # type: ignore[union-attr]
    assert no_active_job(world)


def test_a_check_while_the_old_file_goes_to_the_trash_never_deletes_it(world: World) -> None:
    """R-QL-06, D-093: the cleanup of a check waits for the files lock of the re-download."""
    trash = world.files.trash
    checks: list[threading.Thread] = []

    def slow(path: Path) -> None:
        check = threading.Thread(target=world.downloader.tidy, args=(SMALL_ID,))
        check.start()
        check.join(0.5)
        checks.append(check)
        trash(path)

    world.downloader.redownload([FIRST])
    world.files.trash = slow  # type: ignore[method-assign]
    world.download_all()
    for check in checks:
        check.join(10)

    assert world.files.destroyed == []
    assert len(world.files.trashed) == 1
    assert world.repository.video(FIRST).replacing is None  # type: ignore[union-attr]
    assert no_active_job(world)


def test_an_old_file_neither_the_trash_nor_the_hidden_folder_takes_waits_and_is_kept(
    world: World,
) -> None:
    """R-QL-06, D-093: it stays where it is, through starts and checks, until it can go."""
    trash, move = world.files.trash, world.files.move

    def refuse_trash(path: Path) -> None:
        raise AppError(ErrorCode.PERMISSION_DENIED, {"file": str(path)})

    def refuse_keeping(source: Path, target: Path) -> bool:
        if "replaced" in target.name:
            raise AppError(ErrorCode.PERMISSION_DENIED, {"file": str(target)})
        return move(source, target)

    world.files.trash = refuse_trash  # type: ignore[method-assign]
    world.files.move = refuse_keeping  # type: ignore[method-assign]
    world.downloader.redownload([FIRST])
    world.download_all()
    fresh = world.new_downloader()
    fresh.start()
    fresh.tidy(SMALL_ID)

    assert world.files.destroyed == []
    assert world.repository.video(FIRST).replacing is not None  # type: ignore[union-attr]

    world.files.trash, world.files.move = trash, move  # type: ignore[method-assign]
    fresh.tidy(SMALL_ID)

    assert world.files.destroyed == []
    assert len(world.files.trashed) == 1
    assert world.repository.video(FIRST).replacing is None  # type: ignore[union-attr]
    assert no_active_job(world)


def test_two_old_files_kept_in_the_hidden_folder_get_names_of_their_own(world: World) -> None:
    """R-QL-06, D-093: a second re-download never finds its kept name taken."""

    def refuse_trash(path: Path) -> None:
        raise AppError(ErrorCode.PERMISSION_DENIED, {"file": str(path)})

    world.files.trash = refuse_trash  # type: ignore[method-assign]
    world.downloader.redownload([FIRST])
    world.download_all()
    world.downloader.redownload([FIRST])
    world.download_all()

    kept = [name for name in world.files.file_names(hidden(world)) if "replaced" in name]
    assert len(kept) == 2
    assert world.files.destroyed == []
    assert world.repository.video(FIRST).replacing is None  # type: ignore[union-attr]


def test_a_store_that_fails_after_the_swap_puts_the_old_file_back(world: World) -> None:
    """R-QL-06, D-093: the old file returns under its name; the video keeps its old facts."""
    old = world.files.file_id(file_of(world))
    before = world.repository.video(FIRST)
    assert before is not None
    record = world.jobs.record

    def refuse_new_facts(job: Job, *args: Any, **kwargs: Any) -> None:
        video = args[0] if args else None
        if video is not None and video.downloaded_at != before.downloaded_at:
            raise AppError(ErrorCode.INTERNAL, {"reason": "the database refused"})
        record(job, *args, **kwargs)

    world.downloader.redownload([FIRST])
    world.clock.advance(60)
    world.jobs.record = refuse_new_facts  # type: ignore[method-assign]
    world.download_all()
    world.jobs.record = record  # type: ignore[method-assign]

    after = world.repository.video(FIRST)
    assert after is not None
    assert world.files.file_id(file_of(world)) == old
    assert (after.status, after.replacing, after.downloaded_at) == (
        VideoStatus.SYNCED,
        None,
        before.downloaded_at,
    )
    assert world.files.trashed == []


def test_a_swap_that_fails_clears_its_marker_and_leaves_the_old_file(world: World) -> None:
    """R-QL-06, D-093: a failed re-download always clears its marker; nothing loops."""
    old = world.files.file_id(file_of(world))

    def broken(first: Path, second: Path) -> None:
        raise AppError(ErrorCode.PERMISSION_DENIED, {"file": str(second)})

    world.files.swap = broken  # type: ignore[method-assign]
    world.downloader.redownload([FIRST])
    world.download_all()

    video = world.repository.video(FIRST)
    assert video is not None
    assert (video.status, video.replacing) == (VideoStatus.SYNCED, None)
    assert world.files.file_id(file_of(world)) == old
    assert no_active_job(world)


def test_a_file_whose_swap_is_under_way_is_not_marked_missing(world: World) -> None:
    """R-MI-06, D-093: the check of files leaves out a video whose old file is moving."""
    with world.engine.begin() as connection:
        connection.execute(
            text("UPDATE videos SET replacing = :marker WHERE id = :id"),
            {"marker": '{"job": "J", "old": 1, "way": "move", "step": "moving"}', "id": FIRST},
        )
    world.files.trash(file_of(world))

    world.check(SMALL_ID)

    assert world.repository.video(FIRST).status is VideoStatus.SYNCED  # type: ignore[union-attr]


# --- a volume that cannot swap, as exFAT (review of M5: High 2)


def test_on_a_volume_that_cannot_swap_the_files_change_places_by_two_moves(world: World) -> None:
    """R-QL-06, R-DT-10, D-093: the new file under the name, the old one in the Trash."""
    old = world.files.file_id(file_of(world))
    world.files.no_swap.add(world.library)

    world.downloader.redownload([FIRST])
    world.download_all()

    video = world.repository.video(FIRST)
    assert video is not None
    assert (video.status, video.replacing) == (VideoStatus.SYNCED, None)
    assert world.files.file_id(file_of(world)) != old
    dates = world.files.read_dates(file_of(world))
    assert (dates.created, dates.modified) == (PUBLISHED, PUBLISHED)
    assert len(world.files.trashed) == 1
    assert visible(world) == [file_of(world).name]
    assert world.files.file_names(file_of(world).parent, hidden=True) == [
        ".yt-mirror",
        file_of(world).name,
    ]
    assert no_active_job(world)


def crash_on_move(world: World, number: int) -> None:
    """End the process at the given move of a file (1 = the first one) during the next job."""
    move = world.files.move
    count = {"moves": 0}

    def counted(source: Path, target: Path) -> bool:
        count["moves"] += 1
        if count["moves"] == number:
            raise Killed
        return move(source, target)

    world.files.move = counted  # type: ignore[method-assign]
    with pytest.raises(Killed):
        world.downloader.work_once()
    world.files.move = move  # type: ignore[method-assign]


@pytest.mark.parametrize("step", [1, 2], ids=["before the old file moved", "before the new one"])
def test_a_crash_while_the_files_change_places_is_undone_at_the_next_start(
    world: World, step: int
) -> None:
    """R-QL-06, R-QA-06, D-093: the old file is back under its name; nothing is lost."""
    old = world.files.file_id(file_of(world))
    world.files.no_swap.add(world.library)
    world.downloader.redownload([FIRST])

    crash_on_move(world, step)
    world.new_downloader().start()

    assert world.files.file_id(file_of(world)) == old
    assert world.repository.video(FIRST).replacing is None  # type: ignore[union-attr]
    assert visible(world) == [file_of(world).name]
    assert len(world.files.file_names(file_of(world).parent, hidden=True)) == 2
    assert world.files.destroyed == []


def test_a_crash_after_the_new_file_is_in_place_but_not_stored_is_undone(world: World) -> None:
    """R-QL-06, R-QA-06, D-093: the stored facts and the file under the name belong together."""
    old = world.files.file_id(file_of(world))
    world.files.no_swap.add(world.library)
    world.downloader.redownload([FIRST])
    record = world.jobs.record
    before = world.repository.video(FIRST)
    assert before is not None

    def die(job: Job, *args: Any, **kwargs: Any) -> None:
        video = args[0] if args else None
        if video is not None and video.downloaded_at != before.downloaded_at:
            raise Killed
        record(job, *args, **kwargs)

    world.clock.advance(60)
    world.jobs.record = die  # type: ignore[method-assign]
    with pytest.raises(Killed):
        world.downloader.work_once()
    world.jobs.record = record  # type: ignore[method-assign]
    world.new_downloader().start()

    assert world.files.file_id(file_of(world)) == old
    assert world.repository.video(FIRST).replacing is None  # type: ignore[union-attr]
    assert visible(world) == [file_of(world).name]
    assert world.files.destroyed == []


def test_a_cancel_of_the_waiting_job_never_takes_the_old_file_with_it(world: World) -> None:
    """R-QL-06, R-QU-02, D-093: the job may end; the old file still goes to the Trash."""

    def refuse_trash(path: Path) -> None:
        raise AppError(ErrorCode.PERMISSION_DENIED, {"file": str(path)})

    trash, move = world.files.trash, world.files.move

    def refuse_keeping(source: Path, target: Path) -> bool:
        if "replaced" in target.name:
            raise AppError(ErrorCode.PERMISSION_DENIED, {"file": str(target)})
        return move(source, target)

    world.files.trash = refuse_trash  # type: ignore[method-assign]
    world.files.move = refuse_keeping  # type: ignore[method-assign]
    [job] = world.downloader.redownload([FIRST])
    world.download_all()

    assert world.downloader.cancel(job.id) is True
    world.new_downloader().tidy(SMALL_ID)
    assert world.files.destroyed == []

    world.files.trash, world.files.move = trash, move  # type: ignore[method-assign]
    world.downloader.tidy(SMALL_ID)
    assert world.files.destroyed == []
    assert len(world.files.trashed) == 1
    assert world.repository.video(FIRST).replacing is None  # type: ignore[union-attr]


def test_the_cleanup_of_a_channel_waits_for_the_files_lock(world: World) -> None:
    """R-QL-06, R-FN-06, D-093: never in the middle of a change of places or a rename."""
    done = threading.Event()

    def tidy() -> None:
        world.downloader.tidy(SMALL_ID)
        done.set()

    with world.files_lock:
        cleanup = threading.Thread(target=tidy)
        cleanup.start()
        assert not done.wait(0.5), "the cleanup ran while the files lock was held"
    cleanup.join(10)
    assert done.is_set()
