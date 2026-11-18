"""The queue as the downloads panel shows it (R-QU-01, R-QU-02, R-QU-08).

It reads the jobs that wait or run, their videos and channels, and the
progress kept in memory. The commands that change the queue are the
downloader's. This module only reads.

Tests: backend/tests/unit/services/test_queue.py
"""

from collections.abc import Callable

from ytmirror.core.channels import VideoStatus
from ytmirror.core.jobs import Job, JobState
from ytmirror.core.queue import FailedEntry, QueueEntry, QueueSummary, QueueView
from ytmirror.ports.catalogue_repository import CatalogueRepository
from ytmirror.ports.job_repository import JobRepository
from ytmirror.services.download_state import DownloadState


class QueueService:
    """Builds the view of the whole queue."""

    def __init__(
        self,
        repository: CatalogueRepository,
        jobs: JobRepository,
        state: DownloadState,
        summary: Callable[[], QueueSummary],
    ) -> None:
        """Create the service.

        Args:
            repository: The stored channels and videos.
            jobs: The stored jobs.
            state: The progress of the running downloads.
            summary: Says how the queue stands.
        """
        self._repository = repository
        self._jobs = jobs
        self._state = state
        self._summary = summary

    def view(self) -> QueueView:
        """Return every download that runs or waits, in its order, and the failed videos."""
        running = self._jobs.jobs([JobState.RUNNING])
        waiting = self._jobs.jobs([JobState.WAITING])
        videos = self._repository.videos_by_id([job.video_id for job in (*running, *waiting)])
        titles = {channel.id: channel.title for channel in self._repository.channels()}

        def entries(jobs: tuple[Job, ...]) -> tuple[QueueEntry, ...]:
            found: list[QueueEntry] = []
            for job in jobs:
                video = videos.get(job.video_id)
                if video is None:
                    continue
                progress = self._state.progress_of(video.id)
                found.append(
                    QueueEntry(
                        job=job,
                        video=video,
                        channel_title=titles.get(video.channel_id, ""),
                        progress=progress if progress and progress.job_id == job.id else None,
                        paced_until=self._state.paced_until(video.id),
                    )
                )
            return tuple(found)

        failed = tuple(
            FailedEntry(video=video, channel_title=titles.get(video.channel_id, ""))
            for video in self._repository.videos_with_status(VideoStatus.FAILED)
        )
        return QueueView(
            summary=self._summary(),
            running=entries(running),
            waiting=entries(waiting),
            failed=failed,
        )
