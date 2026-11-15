"""What is known in memory about the downloads that wait or run.

Shared by the downloader, which changes it, and the views, which read it:
the progress of each running download (R-QU-04), the job of each video that
waits or runs, and how far the downloads of each channel are, for "Mirroring
X of Y" (R-FB-01). Nothing here is stored: the jobs table is the truth after
a restart.

Tests: backend/tests/unit/services/test_download_state.py
"""

import threading
from dataclasses import dataclass

from ytmirror.core.jobs import JobProgress


@dataclass(frozen=True, slots=True)
class Mirroring:
    """How far the downloads of one channel are (R-FB-01).

    Attributes:
        done: How many of them ended, well or not, since the channel last had none.
        total: How many there are in all since then.
    """

    done: int
    total: int


class DownloadState:
    """The downloads that wait or run, by video and by channel."""

    def __init__(self) -> None:
        """Know of no download."""
        self._lock = threading.Lock()
        self._jobs: dict[str, str] = {}
        self._channels: dict[str, str] = {}
        self._progress: dict[str, JobProgress] = {}
        self._batches: dict[str, list[int]] = {}

    def queued(self, video_id: str, channel_id: str, job_id: str) -> None:
        """A download of a video was put in line.

        Args:
            video_id: The video.
            channel_id: Its channel.
            job_id: The job.
        """
        with self._lock:
            self._jobs[video_id] = job_id
            self._channels[video_id] = channel_id
            batch = self._batches.setdefault(channel_id, [0, 0])
            batch[1] += 1

    def progressed(self, progress: JobProgress) -> None:
        """A running download got further.

        Args:
            progress: How far it is.
        """
        with self._lock:
            if self._jobs.get(progress.video_id) == progress.job_id:
                self._progress[progress.video_id] = progress

    def ended(self, video_id: str) -> None:
        """The download of a video ended: done, failed or cancelled.

        Args:
            video_id: The video.
        """
        with self._lock:
            self._jobs.pop(video_id, None)
            self._progress.pop(video_id, None)
            channel_id = self._channels.pop(video_id, None)
            if channel_id is None:
                return
            batch = self._batches[channel_id]
            batch[0] += 1
            if channel_id not in self._channels.values():
                del self._batches[channel_id]

    def job_of(self, video_id: str) -> str | None:
        """Return the job of a video that waits or runs, or None.

        Args:
            video_id: The video.
        """
        with self._lock:
            return self._jobs.get(video_id)

    def progress_of(self, video_id: str) -> JobProgress | None:
        """Return how far the running download of a video is, or None.

        Args:
            video_id: The video.
        """
        with self._lock:
            return self._progress.get(video_id)

    def mirroring(self, channel_id: str) -> Mirroring | None:
        """Return how far the downloads of a channel are, or None when it has none.

        Args:
            channel_id: The channel.
        """
        with self._lock:
            batch = self._batches.get(channel_id)
            return None if batch is None else Mirroring(done=batch[0], total=batch[1])
