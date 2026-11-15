"""Tests of ``ytmirror.services.download_state``."""

from ytmirror.core.jobs import JobProgress, Stage
from ytmirror.services.download_state import DownloadState, Mirroring


def test_a_channel_counts_its_downloads_until_none_is_left() -> None:
    """R-FB-01: "Mirroring X of Y" counts the downloads of a channel since it last had none."""
    state = DownloadState()
    state.queued("v1", "UCa", "job1")
    state.queued("v2", "UCa", "job2")

    state.ended("v1")
    halfway = state.mirroring("UCa")
    state.ended("v2")

    assert halfway == Mirroring(done=1, total=2)
    assert state.mirroring("UCa") is None


def test_progress_belongs_to_the_job_that_runs_now() -> None:
    """R-QU-04: progress of an ended job is not kept, nor that of an older job of the video."""
    state = DownloadState()
    state.queued("v1", "UCa", "job2")
    old = JobProgress(job_id="job1", video_id="v1", channel_id="UCa", stage=Stage.VIDEO)
    now = JobProgress(job_id="job2", video_id="v1", channel_id="UCa", stage=Stage.AUDIO)

    state.progressed(old)
    state.progressed(now)
    running = state.progress_of("v1")
    state.ended("v1")

    assert running == now
    assert (state.progress_of("v1"), state.job_of("v1")) == (None, None)


def test_ending_a_video_it_never_knew_changes_nothing() -> None:
    """R-QU-04: an end without a start is harmless."""
    state = DownloadState()

    state.ended("v9")

    assert state.mirroring("UCa") is None
