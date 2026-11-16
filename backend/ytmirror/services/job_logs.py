"""Keeps the logs of jobs for as long as docs/LOGGING.md section 3 says, and no longer.

Implements the job log part of R-LG-01. Kept: the log of the latest failed
attempt of a video that is still failed, however old; any other failed
job's log for 14 days after its video stopped being failed; the logs of the
50 newest other jobs. Only files of the job log folder whose names are a
ULID and ``.log`` are ever deleted.

Tests: backend/tests/unit/services/test_job_logs.py
"""

from collections import defaultdict
from pathlib import Path

import structlog
from structlog.typing import FilteringBoundLogger

from ytmirror.core.channels import VideoStatus
from ytmirror.core.jobs import Job, JobState, job_logs_to_delete
from ytmirror.ports.catalogue_repository import CatalogueRepository
from ytmirror.ports.clock import Clock
from ytmirror.ports.file_system import JOB_LOG_NAME, FileSystem
from ytmirror.ports.job_repository import JobRepository

_log: FilteringBoundLogger = structlog.get_logger(__name__)

_ENDED = (JobState.DONE, JobState.FAILED, JobState.CANCELLED)


class JobLogsService:
    """Deletes the logs of jobs that are no longer needed."""

    def __init__(
        self,
        folder: Path,
        repository: CatalogueRepository,
        jobs: JobRepository,
        files: FileSystem,
        clock: Clock,
    ) -> None:
        """Create the service.

        Args:
            folder: The folder of the logs of jobs.
            repository: The stored videos, for which ones are failed now.
            jobs: The stored jobs and the status history.
            files: Files on this Mac.
            clock: The source of time.
        """
        self._folder = folder
        self._repository = repository
        self._jobs = jobs
        self._files = files
        self._clock = clock

    def clean(self) -> int:
        """Delete the logs that are no longer kept. Returns how many were deleted."""
        names = [
            name for name in self._files.file_names(self._folder) if JOB_LOG_NAME.fullmatch(name)
        ]
        known = {job.id: job for job in self._jobs.jobs(_ENDED)}
        ended = {
            name.removesuffix(".log"): self._ended_at(known.get(name.removesuffix(".log")))
            for name in names
        }
        kept, failed = self._failed_jobs(known)
        doomed = job_logs_to_delete(ended, kept, failed, int(self._clock.now().timestamp()))
        for job_id in doomed:
            self._files.remove_job_log(self._folder / f"{job_id}.log")
        if doomed:
            _log.info("log.jobs_deleted", msg="Old logs of jobs were deleted", count=len(doomed))
        return len(doomed)

    def _ended_at(self, job: Job | None) -> int:
        # A log without its job belongs to a removed channel: it is the oldest of all.
        if job is None:
            return 0
        return job.finished_at or job.started_at or job.created_at

    def _failed_jobs(self, known: dict[str, Job]) -> tuple[frozenset[str], dict[str, int]]:
        """Return the failed jobs kept while failed, and when the 14 days of the others start."""
        by_video: dict[str, list[Job]] = defaultdict(list)
        for job in known.values():
            if job.state is JobState.FAILED:
                by_video[job.video_id].append(job)
        kept: set[str] = set()
        failed: dict[str, int] = {}
        for video_id, attempts in by_video.items():
            attempts.sort(key=self._ended_at)
            latest = attempts[-1]
            video = self._repository.video(video_id)
            still_failed = video is not None and video.status is VideoStatus.FAILED
            if still_failed:
                kept.add(latest.id)
            else:
                failed[latest.id] = self._left_failed_at(video_id, latest)
            for earlier in attempts[:-1]:
                failed[earlier.id] = self._ended_at(earlier)
        return frozenset(kept), failed

    def _left_failed_at(self, video_id: str, job: Job) -> int:
        """Return when a video stopped being failed after a failed job, by its history."""
        for event in self._jobs.events(video_id):
            if event.from_status == VideoStatus.FAILED.value and event.at >= self._ended_at(job):
                return event.at
        return self._ended_at(job)
