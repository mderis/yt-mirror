"""Tests of the view of the queue that the downloads panel shows."""

import threading
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.fixtures.world import World
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.jobs import DownloadProgress, Stage
from ytmirror.core.queue import QueueView

FIRST = "sm000000005"
SECOND = "sm000000004"
THIRD = "sm000000003"


@pytest.fixture
def world(tmp_path: Path) -> World:
    """A world with the small channel added and listed."""
    world = World(tmp_path)
    world.add_and_list()
    return world


def test_the_view_lists_the_waiting_downloads_in_their_order(world: World) -> None:
    """R-QU-02: the panel lists the waiting downloads with their channel, title and quality."""
    world.downloader.mirror([FIRST, SECOND])
    world.downloader.mirror([THIRD], first=True)

    view = world.queue.view()

    assert [entry.video.id for entry in view.waiting] == [THIRD, FIRST, SECOND]
    assert {entry.channel_title for entry in view.waiting} == {"Small Channel"}
    assert view.running == ()
    assert view.summary.waiting == 3


def test_the_view_shows_the_progress_of_a_running_download(world: World) -> None:
    """R-QU-04, R-QU-02: a running download is listed with how far it is."""
    seen: list[QueueView] = []
    world.downloader.mirror([FIRST])

    def look(tell: Callable[[DownloadProgress], None]) -> None:
        tell(DownloadProgress(stage=Stage.VIDEO, fraction=0.4, speed_bps=1e6, left_s=3))
        seen.append(world.queue.view())

    world.download.during_video = look
    world.download_all()

    [view] = seen
    [entry] = view.running
    assert entry.progress is not None
    assert (entry.video.id, entry.progress.fraction) == (FIRST, 0.4)


def test_the_view_lists_failed_videos_with_their_reason(world: World) -> None:
    """R-QU-08: the panel lists the failed videos, each with why it failed."""
    world.download.fail = AppError(ErrorCode.MEMBERS_ONLY, {})
    world.downloader.mirror([FIRST])
    world.download_all()

    [failed] = world.queue.view().failed

    assert (failed.video.id, failed.video.last_error_code) == (FIRST, ErrorCode.MEMBERS_ONLY)


def test_a_view_while_downloads_run_never_lists_a_job_twice(world: World) -> None:
    """R-QU-02: the view is taken from one reading of the jobs, so no download shows twice."""
    held = {FIRST: threading.Event()}
    world.download.held = held
    world.downloader.mirror([FIRST, SECOND])
    worker = threading.Thread(target=world.downloader.work_once, daemon=True)
    worker.start()
    world.download.asked.setdefault(FIRST, threading.Event()).wait(10)

    view = world.queue.view()

    ids = [entry.video.id for entry in (*view.running, *view.waiting)]
    assert sorted(ids) == sorted({FIRST, SECOND})
    held[FIRST].set()
    worker.join(10)
