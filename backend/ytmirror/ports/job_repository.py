"""The JobRepository port: jobs, the status history of videos, and the files of videos.

A job, the video it works on and the record of the video's status change are
stored together in one transaction, so that the status of a video and its
history never disagree (R-LG-03, R-QA-06). This port writes only what a
download owns of a video: its status, its file, its exact date and its last
failure. What a check owns (title, views, position) is written by the
CatalogueRepository, so the two never undo each other.

Tests: backend/tests/integration/db/test_job_repository.py
"""

from collections.abc import Collection, Mapping, Sequence
from typing import Protocol

from ytmirror.core.channels import Video
from ytmirror.core.jobs import Job, JobState, PendingSideFile, VideoEvent
from ytmirror.core.status import StatusChange


class JobRepository(Protocol):
    """Stores jobs and what they change."""

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
            video: The video with its new status and file facts, or None when
                the video does not change.
            change: The status change to record, with the job's ID, or None.
            side_files: Side files of the video to keep for writing, as (path
                relative to the channel folder, content). They are stored with
                the synced video, so a crash right after loses none (R-QA-06).
        """
        ...

    def job(self, job_id: str) -> Job | None:
        """Return one job, or None.

        Args:
            job_id: The job ID.
        """
        ...

    def jobs(self, states: Collection[JobState]) -> tuple[Job, ...]:
        """Return the jobs in some states, lowest priority first, then oldest first.

        Args:
            states: The states.
        """
        ...

    def active_job_of(self, video_id: str) -> Job | None:
        """Return the job of a video that waits or runs, or None.

        Args:
            video_id: The video.
        """
        ...

    def next_priority(self) -> int:
        """Return a priority behind every job that waits or runs."""
        ...

    def lowest_priority(self) -> int | None:
        """Return the lowest priority of a job that waits or runs, or None when there is none."""
        ...

    def set_priorities(self, priorities: Mapping[str, int]) -> None:
        """Give waiting jobs new priorities, in one transaction (R-QU-02).

        A job that no longer waits keeps its priority.

        Args:
            priorities: The new priority of each job.
        """
        ...

    def set_formats(self, job_id: str, formats: str) -> None:
        """Keep the formats a running download chose, for when it continues (D-091).

        ``record`` never writes them: only this does, so no other write of the job
        can lose them.

        Args:
            job_id: The job.
            formats: The formats, as yt-dlp names them.
        """
        ...

    def mark_by_hand(self, job_id: str) -> None:
        """Count a waiting job as started by hand from now on (R-DT-06, D-090).

        Args:
            job_id: The job. One that no longer waits is left as it is.
        """
        ...

    def count(self, states: Collection[JobState]) -> int:
        """Return how many jobs are in some states.

        Args:
            states: The states.
        """
        ...

    def events(self, video_id: str) -> tuple[VideoEvent, ...]:
        """Return the status history of a video, oldest first (R-LG-03).

        Args:
            video_id: The video.
        """
        ...

    def add_pending_side_file(self, video_id: str, path: str, data: bytes) -> None:
        """Keep a side file that could not be written, to write it later.

        Args:
            video_id: The video.
            path: Where it goes, relative to the channel folder.
            data: Its content.
        """
        ...

    def clear_placing_file(self, video_id: str) -> None:
        """Forget the marker of a placed file, once its cleanup is done (R-QA-06).

        Args:
            video_id: The video.
        """
        ...

    def pending_side_files(self) -> tuple[PendingSideFile, ...]:
        """Return the side files still to be written, oldest first."""
        ...

    def remove_pending_side_file(self, number: int) -> None:
        """Forget a side file that was written, or is no longer wanted.

        Args:
            number: Its ``id``.
        """
        ...

    def tracked_files(self, channel_id: str) -> tuple[str, ...]:
        """Return the file names the catalogue has for the videos of a channel.

        Args:
            channel_id: The channel.
        """
        ...
