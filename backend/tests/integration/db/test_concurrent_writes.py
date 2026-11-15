"""A check and a download write at the same time, from two threads, with the real SQLite.

Both read before they write in one transaction: the check reads its channel,
the download reads its job. With a plain ``BEGIN`` such a transaction works
from a snapshot, and SQLite refuses its write at once ("database is locked")
when the other thread wrote in between; the busy timeout does not help. Every
transaction that may write starts with ``BEGIN IMMEDIATE`` and waits instead
(D-081).
"""

import dataclasses
import threading
from collections.abc import Callable
from pathlib import Path

from tests.fixtures.catalogue import make_channel, make_video
from tests.fixtures.fakes.clock import FakeClock
from tests.migrations.helpers import new_database, upgrade_to
from tests.migrations.test_no_data_lost import revisions
from ytmirror.adapters.db.catalogue_repository import SqlCatalogueRepository
from ytmirror.adapters.db.job_repository import SqlJobRepository
from ytmirror.core.catalogue import CheckChanges
from ytmirror.core.channels import Quality, VideoStatus
from ytmirror.core.jobs import Job, JobKind, JobState

ROUNDS = 200


def test_a_check_and_a_download_that_write_together_never_fail_with_locked(
    tmp_path: Path,
) -> None:
    """R-QA-06, R-ER-03: two writers wait for each other; none fails with "database is locked"."""
    engine = new_database(tmp_path)
    upgrade_to(engine, revisions()[-1])
    clock = FakeClock()
    catalogue = SqlCatalogueRepository(engine, clock)
    jobs = SqlJobRepository(engine, clock)
    channel = make_channel()
    catalogue.add_channel(channel)
    videos = [make_video(number) for number in (1, 2)]
    assert catalogue.apply_check(channel, CheckChanges(tuple(videos), (), 0, 0, 0, 0, 0))
    job = Job(
        id="01JD0000000000000000000001",
        video_id=videos[0].id,
        kind=JobKind.DOWNLOAD,
        state=JobState.RUNNING,
        priority=1,
        quality=Quality.BEST,
        created_at=1,
    )
    start = threading.Barrier(2)
    errors: list[BaseException] = []

    def check() -> None:
        for number in range(ROUNDS):
            seen = dataclasses.replace(videos[1], view_count=number)
            catalogue.apply_check(channel, CheckChanges((), (seen,), 0, 1, 0, 0, 1))

    def download() -> None:
        for number in range(ROUNDS):
            status = VideoStatus.DOWNLOADING if number % 2 else VideoStatus.QUEUED
            jobs.record(job, dataclasses.replace(videos[0], status=status))

    def run(work: Callable[[], None]) -> None:
        start.wait()
        try:
            work()
        except BaseException as error:  # noqa: BLE001  (the test reports every failure)
            errors.append(error)

    threads = [threading.Thread(target=run, args=(work,)) for work in (check, download)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(120)

    assert errors == []
    stored = catalogue.video(videos[1].id)
    assert stored is not None and stored.view_count == ROUNDS - 1
