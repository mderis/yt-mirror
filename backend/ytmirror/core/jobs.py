"""Jobs: one piece of work on one video, and what the app tells about it.

A job has an ID that ties together every log line, the status history and
the output of yt-dlp and ffmpeg of one download (R-LG-02). Jobs wait in one
line in the order of their priority, lower first (R-MI-01). Milestone M3
has the kind ``download`` only, and one worker takes the jobs one after
another. The progress of a running job is kept in memory and told to the
window (R-QU-04).

This module must not read a clock or store anything.

Tests: backend/tests/unit/core/test_jobs.py
"""

from dataclasses import dataclass
from enum import StrEnum

from ytmirror.core.channels import Quality, Video
from ytmirror.core.errors import ErrorCode

JOB_LOGS_KEPT = 50
"""How many logs of jobs that ended well are kept (docs/LOGGING.md section 3)."""

FAILED_JOB_LOG_DAYS = 14
"""How long the log of a failed job is kept, in days, once its video is no longer failed."""


class JobKind(StrEnum):
    """What a job does. Re-download, repair and adoption arrive in later milestones."""

    DOWNLOAD = "download"


class JobState(StrEnum):
    """Where a job is in its life."""

    WAITING = "waiting"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


ACTIVE_STATES = frozenset({JobState.WAITING, JobState.RUNNING})
"""The states of a job that is not over yet."""


class Stage(StrEnum):
    """What a running download does now (R-QU-04)."""

    VIDEO = "video"
    AUDIO = "audio"
    PROCESSING = "processing"


@dataclass(frozen=True, slots=True)
class Job:
    """One piece of work on one video (docs/ARCHITECTURE.md section 5, ``jobs``).

    Attributes:
        id: A ULID. It is the job ID of every log line of the job.
        video_id: The video.
        kind: What the job does.
        state: Where the job is in its life.
        priority: Lower runs first.
        quality: The quality, resolved when the job was put in line.
        created_at: When the job was put in line.
        stage: What a running job does now, or None.
        error_code: Why a failed job failed, or None.
        started_at: When a worker took it, or None.
        finished_at: When it ended, or None.
    """

    id: str
    video_id: str
    kind: JobKind
    state: JobState
    priority: int
    quality: Quality
    created_at: int
    stage: Stage | None = None
    error_code: ErrorCode | None = None
    started_at: int | None = None
    finished_at: int | None = None


@dataclass(frozen=True, slots=True)
class JobProgress:
    """How far a running download is (R-QU-04). Kept in memory only.

    Attributes:
        job_id: The job.
        video_id: The video.
        channel_id: The channel of the video.
        stage: What the download does now.
        fraction: How much of the stage is done, from 0 to 1, or None when unknown.
        speed_bps: Bytes per second, or None.
        left_s: Seconds left, or None.
        height: The height that is being downloaded, or None.
    """

    job_id: str
    video_id: str
    channel_id: str
    stage: Stage
    fraction: float | None = None
    speed_bps: float | None = None
    left_s: int | None = None
    height: int | None = None


@dataclass(frozen=True, slots=True)
class VideoEvent:
    """One recorded status change of a video (R-LG-03).

    Attributes:
        video_id: The video.
        at: When it changed.
        from_status: The status before, by its value.
        to_status: The status after, by its value.
        reason: Why, as a short stable word.
        job_id: The job that changed it, or None.
    """

    video_id: str
    at: int
    from_status: str
    to_status: str
    reason: str
    job_id: str | None


@dataclass(frozen=True, slots=True)
class VideoUpdated:
    """One video changed: its status, its file or its date (R-FB-03).

    Attributes:
        video: The video as it is stored now.
    """

    video: Video


@dataclass(frozen=True, slots=True)
class JobProgressed:
    """A running download got further (R-QU-04).

    Attributes:
        progress: How far it is.
    """

    progress: JobProgress


def job_logs_to_delete(
    logs: dict[str, int],
    kept_for_failed_videos: frozenset[str],
    failed: dict[str, int],
    now: int,
) -> list[str]:
    """Return the jobs whose log files may be deleted (R-LG-01, docs/LOGGING.md section 3).

    Kept: the log of the latest failed attempt of a video that is still
    failed, however old; any other failed job until 14 days after its video
    stopped being failed; the 50 newest jobs that did not fail.

    Args:
        logs: The job ID of every log file, with the time the job ended.
        kept_for_failed_videos: The jobs of the latest failed attempt of every
            video that is still failed.
        failed: Every other failed job, with the time its 14 days count from:
            when its video stopped being failed, or when the job ended if a
            later attempt of the video failed too.
        now: The time now.

    Returns:
        The job IDs whose logs may be deleted, oldest first.
    """
    limit = now - FAILED_JOB_LOG_DAYS * 24 * 60 * 60
    others = sorted(
        (ended, job_id)
        for job_id, ended in logs.items()
        if job_id not in kept_for_failed_videos and job_id not in failed
    )
    old_others = [job_id for _, job_id in others[: max(0, len(others) - JOB_LOGS_KEPT)]]
    old_failed = [job_id for job_id, since in failed.items() if job_id in logs and since < limit]
    return sorted([*old_others, *old_failed], key=lambda job_id: logs[job_id])
