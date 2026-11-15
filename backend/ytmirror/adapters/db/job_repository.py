"""Stores jobs and the status history of videos in ``jobs`` and ``video_events``.

Implements the JobRepository port. It writes only the columns of a video that
a download owns, so that a check that runs at the same time never undoes a
download, and a download never undoes a check (docs/ARCHITECTURE.md
section 7.7).

Tests: backend/tests/integration/db/test_job_repository.py
"""

from collections.abc import Collection
from typing import Any

from sqlalchemy import Engine, delete, func, select, update
from sqlalchemy.orm import Session

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
)
"""The columns of a video that a download writes. A check writes the others."""


class SqlJobRepository:
    """Reads and writes ``jobs`` and ``video_events``, and the download columns of videos."""

    def __init__(self, engine: Engine, clock: Clock) -> None:
        """Create the repository.

        Args:
            engine: The database engine.
            clock: The source of the ``created_at`` and ``updated_at`` times.
        """
        self._engine = engine
        self._clock = clock

    def record(
        self, job: Job, video: Video | None = None, change: StatusChange | None = None
    ) -> None:
        """Store a job, and with it what it changed of its video, in one transaction.

        Args:
            job: The job as it is now. It is added when it is new.
            video: The video with its new status and file facts, or None.
            change: The status change to record, with the job's ID, or None.
        """
        now = self._now()
        with Session(self._engine) as session, session.begin():
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
        with Session(self._engine) as session:
            row = session.get(JobRow, job_id)
            return None if row is None else _job_of(row)

    def jobs(self, states: Collection[JobState]) -> tuple[Job, ...]:
        """Return the jobs in some states, lowest priority first, then oldest first.

        Args:
            states: The states.
        """
        with Session(self._engine) as session:
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
        with Session(self._engine) as session:
            row = session.scalars(
                select(JobRow).where(
                    JobRow.video_id == video_id,
                    JobRow.state.in_([state.value for state in ACTIVE_STATES]),
                )
            ).first()
            return None if row is None else _job_of(row)

    def next_priority(self) -> int:
        """Return a priority behind every job that waits or runs."""
        with Session(self._engine) as session:
            highest = session.scalar(
                select(func.max(JobRow.priority)).where(
                    JobRow.state.in_([state.value for state in ACTIVE_STATES])
                )
            )
            return 1 if highest is None else highest + 1

    def events(self, video_id: str) -> tuple[VideoEvent, ...]:
        """Return the status history of a video, oldest first (R-LG-03).

        Args:
            video_id: The video.
        """
        with Session(self._engine) as session:
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
        with Session(self._engine) as session:
            rows = session.scalars(select(PendingSideFileRow).order_by(PendingSideFileRow.id))
            return tuple(
                PendingSideFile(id=row.id, video_id=row.video_id, path=row.path, data=row.data)
                for row in rows
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
        with Session(self._engine) as session:
            names = session.scalars(
                select(VideoRow.file_name).where(
                    VideoRow.channel_id == channel_id, VideoRow.file_name.is_not(None)
                )
            )
            return tuple(name for name in names if name)

    def _now(self) -> int:
        return int(self._clock.now().timestamp())


def _job_values(job: Job) -> dict[str, Any]:
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
    }


def _download_values(video: Video) -> dict[str, Any]:
    return {
        name: getattr(value, "value", value)
        for name in DOWNLOAD_FIELDS
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
    )
