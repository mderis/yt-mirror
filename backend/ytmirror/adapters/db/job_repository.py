"""Stores jobs and the status history of videos in ``jobs`` and ``video_events``.

Implements the JobRepository port. It writes only the columns of a video that
a download owns, so that a check that runs at the same time never undoes a
download, and a download never undoes a check (docs/ARCHITECTURE.md
section 7.7).

Tests: backend/tests/integration/db/test_job_repository.py
"""

from collections.abc import Collection, Mapping, Sequence
from typing import Any

from sqlalchemy import Engine, delete, func, select, update
from sqlalchemy.orm import Session

from ytmirror.adapters.db.engine import for_reading
from ytmirror.adapters.db.tables import JobRow, PendingSideFileRow, VideoEventRow, VideoRow
from ytmirror.core.channels import Quality, Video
from ytmirror.core.errors import ErrorCode
from ytmirror.core.jobs import (
    ACTIVE_STATES,
    Job,
    JobKind,
    JobState,
    PendingSideFile,
    Stage,
    VideoEvent,
)
from ytmirror.core.status import StatusChange
from ytmirror.ports.clock import Clock

DOWNLOAD_FIELDS = (
    "status",
    "file_name",
    "file_size",
    "height",
    "vcodec",
    "acodec",
    "has_subtitles",
    "downloaded_at",
    "last_error_code",
    "last_error_at",
    "attempts",
    "published_at",
    "published_exact",
    "published_precision",
    "placing_file",
    "replacing",
)
"""The columns of a video that a download writes. A check writes the others."""


_CHUNK = 500
"""How many IDs one query names at most, below the limit of SQLite."""


class SqlJobRepository:
    """Reads and writes ``jobs`` and ``video_events``, and the download columns of videos."""

    def __init__(self, engine: Engine, clock: Clock) -> None:
        """Create the repository.

        Args:
            engine: The database engine.
            clock: The source of the ``created_at`` and ``updated_at`` times.
        """
        self._engine = engine
        self._reader = for_reading(engine)
        self._clock = clock

    def record(
        self,
        job: Job,
        video: Video | None = None,
        change: StatusChange | None = None,
        side_files: Sequence[tuple[str, bytes]] = (),
    ) -> None:
        """Store a job, and with it what it changed of its video, in one transaction.

        Args:
            job: The job as it is now. It is added when it is new.
            video: The video with its new status and file facts, or None.
            change: The status change to record, with the job's ID, or None.
            side_files: Side files of the video to keep for writing, as (path, content).
        """
        now = self._now()
        with Session(self._engine) as session, session.begin():
            for path, data in side_files:
                assert video is not None, "side files belong to a video"
                session.add(
                    PendingSideFileRow(
                        video_id=video.id, path=path, data=data, created_at=now, updated_at=now
                    )
                )
            row = session.get(JobRow, job.id)
            values = _job_values(job)
            if row is None:
                session.add(JobRow(**values, created_at=job.created_at, updated_at=now))
            else:
                for name, value in values.items():
                    setattr(row, name, value)
                row.updated_at = now
            if video is not None:
                session.execute(
                    update(VideoRow)
                    .where(VideoRow.id == video.id)
                    .values(**_download_values(video), updated_at=now)
                )
            if change is not None:
                session.add(
                    VideoEventRow(
                        video_id=change.video_id,
                        at=now,
                        from_status=change.from_status.value,
                        to_status=change.to_status.value,
                        reason=change.reason,
                        job_id=job.id,
                        created_at=now,
                        updated_at=now,
                    )
                )

    def job(self, job_id: str) -> Job | None:
        """Return one job, or None.

        Args:
            job_id: The job ID.
        """
        with Session(self._reader) as session:
            row = session.get(JobRow, job_id)
            return None if row is None else _job_of(row)

    def jobs(self, states: Collection[JobState]) -> tuple[Job, ...]:
        """Return the jobs in some states, lowest priority first, then oldest first.

        Args:
            states: The states.
        """
        with Session(self._reader) as session:
            rows = session.scalars(
                select(JobRow)
                .where(JobRow.state.in_([state.value for state in states]))
                .order_by(JobRow.priority, JobRow.created_at, JobRow.id)
            )
            return tuple(_job_of(row) for row in rows)

    def active_job_of(self, video_id: str) -> Job | None:
        """Return the job of a video that waits or runs, or None.

        Args:
            video_id: The video.
        """
        with Session(self._reader) as session:
            row = session.scalars(
                select(JobRow).where(
                    JobRow.video_id == video_id,
                    JobRow.state.in_([state.value for state in ACTIVE_STATES]),
                )
            ).first()
            return None if row is None else _job_of(row)

    def next_priority(self) -> int:
        """Return a priority behind every job that waits or runs."""
        with Session(self._reader) as session:
            highest = session.scalar(
                select(func.max(JobRow.priority)).where(
                    JobRow.state.in_([state.value for state in ACTIVE_STATES])
                )
            )
            return 1 if highest is None else highest + 1

    def lowest_priority(self) -> int | None:
        """Return the lowest priority of a job that waits or runs, or None when there is none."""
        with Session(self._reader) as session:
            return session.scalar(
                select(func.min(JobRow.priority)).where(
                    JobRow.state.in_([state.value for state in ACTIVE_STATES])
                )
            )

    def set_priorities(self, priorities: Mapping[str, int]) -> None:
        """Give waiting jobs new priorities, in one transaction (R-QU-02).

        Args:
            priorities: The new priority of each job. A job that no longer waits keeps its own.
        """
        now = self._now()
        with Session(self._engine) as session, session.begin():
            for job_id, priority in priorities.items():
                session.execute(
                    update(JobRow)
                    .where(JobRow.id == job_id, JobRow.state == JobState.WAITING.value)
                    .values(priority=priority, updated_at=now)
                )

    def set_formats(self, job_id: str, formats: str) -> None:
        """Keep the formats a running download chose, for when it continues (D-091).

        Args:
            job_id: The job.
            formats: The formats, as yt-dlp names them.
        """
        with Session(self._engine) as session, session.begin():
            session.execute(
                update(JobRow)
                .where(JobRow.id == job_id)
                .values(formats=formats, updated_at=self._now())
            )

    def promote(self, job_ids: Sequence[str]) -> None:
        """Count waiting jobs as started by hand, and let a retry start now (D-090).

        Args:
            job_ids: The jobs. One that no longer waits is left as it is.
        """
        with Session(self._engine) as session, session.begin():
            for start in range(0, len(job_ids), _CHUNK):
                session.execute(
                    update(JobRow)
                    .where(
                        JobRow.id.in_(job_ids[start : start + _CHUNK]),
                        JobRow.state == JobState.WAITING.value,
                    )
                    .values(by_hand=True, not_before=None, updated_at=self._now())
                )

    def active_jobs_of(self, video_ids: Sequence[str]) -> Mapping[str, Job]:
        """Return the jobs that wait or run for some videos, by video.

        Args:
            video_ids: The videos.
        """
        found: dict[str, Job] = {}
        with Session(self._reader) as session:
            for start in range(0, len(video_ids), _CHUNK):
                rows = session.scalars(
                    select(JobRow).where(
                        JobRow.video_id.in_(video_ids[start : start + _CHUNK]),
                        JobRow.state.in_([state.value for state in ACTIVE_STATES]),
                    )
                )
                found.update((row.video_id, _job_of(row)) for row in rows)
        return found

    def record_many(self, entries: Sequence[tuple[Job, Video | None, StatusChange | None]]) -> None:
        """Store many new jobs with what they change of their videos, in one transaction.

        Args:
            entries: The jobs, with their videos and status changes.
        """
        now = self._now()
        with Session(self._engine) as session, session.begin():
            for job, video, change in entries:
                session.add(JobRow(**_job_values(job), created_at=job.created_at, updated_at=now))
                if video is not None:
                    session.execute(
                        update(VideoRow)
                        .where(VideoRow.id == video.id)
                        .values(**_download_values(video), updated_at=now)
                    )
                if change is not None:
                    session.add(
                        VideoEventRow(
                            video_id=change.video_id,
                            at=now,
                            from_status=change.from_status.value,
                            to_status=change.to_status.value,
                            reason=change.reason,
                            job_id=job.id,
                            created_at=now,
                            updated_at=now,
                        )
                    )

    def count(self, states: Collection[JobState]) -> int:
        """Return how many jobs are in some states.

        Args:
            states: The states.
        """
        with Session(self._reader) as session:
            return (
                session.scalar(
                    select(func.count())
                    .select_from(JobRow)
                    .where(JobRow.state.in_([state.value for state in states]))
                )
                or 0
            )

    def events(self, video_id: str) -> tuple[VideoEvent, ...]:
        """Return the status history of a video, oldest first (R-LG-03).

        Args:
            video_id: The video.
        """
        with Session(self._reader) as session:
            rows = session.scalars(
                select(VideoEventRow)
                .where(VideoEventRow.video_id == video_id)
                .order_by(VideoEventRow.at, VideoEventRow.id)
            )
            return tuple(
                VideoEvent(
                    video_id=row.video_id,
                    at=row.at,
                    from_status=row.from_status,
                    to_status=row.to_status,
                    reason=row.reason,
                    job_id=row.job_id,
                )
                for row in rows
            )

    def add_pending_side_file(self, video_id: str, path: str, data: bytes) -> None:
        """Keep a side file that could not be written, to write it later.

        Args:
            video_id: The video.
            path: Where it goes, relative to the channel folder.
            data: Its content.
        """
        now = self._now()
        with Session(self._engine) as session, session.begin():
            session.add(
                PendingSideFileRow(
                    video_id=video_id, path=path, data=data, created_at=now, updated_at=now
                )
            )

    def pending_side_files(self) -> tuple[PendingSideFile, ...]:
        """Return the side files still to be written, oldest first."""
        with Session(self._reader) as session:
            rows = session.scalars(select(PendingSideFileRow).order_by(PendingSideFileRow.id))
            return tuple(
                PendingSideFile(id=row.id, video_id=row.video_id, path=row.path, data=row.data)
                for row in rows
            )

    def clear_placing_file(self, video_id: str) -> None:
        """Forget the marker of a placed file, once its cleanup is done (R-QA-06).

        Args:
            video_id: The video.
        """
        with Session(self._engine) as session, session.begin():
            session.execute(
                update(VideoRow)
                .where(VideoRow.id == video_id)
                .values(placing_file=None, updated_at=self._now())
            )

    def clear_replacing(self, video_id: str) -> None:
        """Forget the marker of a re-download's swap, once it is settled (D-093).

        Args:
            video_id: The video.
        """
        with Session(self._engine) as session, session.begin():
            session.execute(
                update(VideoRow)
                .where(VideoRow.id == video_id)
                .values(replacing=None, updated_at=self._now())
            )

    def remove_pending_side_file(self, number: int) -> None:
        """Forget a side file that was written, or is no longer wanted.

        Args:
            number: Its ``id``.
        """
        with Session(self._engine) as session, session.begin():
            session.execute(delete(PendingSideFileRow).where(PendingSideFileRow.id == number))

    def tracked_files(self, channel_id: str) -> tuple[str, ...]:
        """Return the file names the catalogue has for the videos of a channel.

        Args:
            channel_id: The channel.
        """
        with Session(self._reader) as session:
            names = session.scalars(
                select(VideoRow.file_name).where(
                    VideoRow.channel_id == channel_id, VideoRow.file_name.is_not(None)
                )
            )
            return tuple(name for name in names if name)

    def _now(self) -> int:
        return int(self._clock.now().timestamp())


def _job_values(job: Job) -> dict[str, Any]:
    """Return the columns ``record`` writes.

    The formats are left out: only ``set_formats`` writes them, so no other write
    of the job loses them (D-091).
    """
    return {
        "id": job.id,
        "video_id": job.video_id,
        "kind": job.kind.value,
        "state": job.state.value,
        "priority": job.priority,
        "quality": job.quality.value,
        "stage": None if job.stage is None else job.stage.value,
        "error_code": None if job.error_code is None else job.error_code.value,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "by_hand": job.by_hand,
        "not_before": job.not_before,
    }


_DATE_FIELDS = ("published_at", "published_exact", "published_precision")
"""A download writes these only with the exact date it found. Otherwise its copy of them is
the one it read at its start, and the exact-date fetch may have stored a better one since."""


def _download_values(video: Video) -> dict[str, Any]:
    return {
        name: getattr(value, "value", value)
        for name in DOWNLOAD_FIELDS
        if video.published_exact or name not in _DATE_FIELDS
        for value in (getattr(video, name),)
    }


def _job_of(row: JobRow) -> Job:
    return Job(
        id=row.id,
        video_id=row.video_id,
        kind=JobKind(row.kind),
        state=JobState(row.state),
        priority=row.priority,
        quality=Quality(row.quality),
        created_at=row.created_at,
        stage=None if row.stage is None else Stage(row.stage),
        error_code=None if row.error_code is None else ErrorCode(row.error_code),
        started_at=row.started_at,
        finished_at=row.finished_at,
        by_hand=row.by_hand,
        not_before=row.not_before,
        formats=row.formats,
    )
