"""Tests of ``ytmirror.core.jobs``."""

from ytmirror.core.jobs import FAILED_JOB_LOG_DAYS, JOB_LOGS_KEPT, job_logs_to_delete

DAY = 24 * 60 * 60
NOW = 1_794_700_000


def test_the_newest_fifty_logs_of_jobs_that_did_not_fail_are_kept() -> None:
    """R-LG-01: of the jobs that ended well, the 50 newest logs stay and older ones go."""
    logs = {f"job{number:03d}": NOW - number for number in range(JOB_LOGS_KEPT + 3)}

    deleted = job_logs_to_delete(logs, frozenset(), {}, NOW)

    assert deleted == ["job052", "job051", "job050"]


def test_the_log_of_a_video_that_is_still_failed_is_kept_however_old() -> None:
    """R-LG-01: the log of the latest failed attempt stays while its video is failed."""
    logs = {"old-failure": NOW - 400 * DAY}

    deleted = job_logs_to_delete(logs, frozenset({"old-failure"}), {}, NOW)

    assert deleted == []


def test_a_failed_log_goes_fourteen_days_after_its_video_stopped_failing() -> None:
    """R-LG-01: the 14 days of a failed job count from when its video stopped being failed."""
    logs = {"recent": NOW - 300 * DAY, "long-ago": NOW - 300 * DAY}
    failed = {
        "recent": NOW - (FAILED_JOB_LOG_DAYS - 1) * DAY,
        "long-ago": NOW - (FAILED_JOB_LOG_DAYS + 1) * DAY,
    }

    deleted = job_logs_to_delete(logs, frozenset(), failed, NOW)

    assert deleted == ["long-ago"]


def test_failed_logs_do_not_count_against_the_fifty_kept() -> None:
    """R-LG-01: a failed log is never deleted to make room among the 50 newest."""
    logs = {f"ok{number:02d}": NOW - number for number in range(JOB_LOGS_KEPT)}
    logs["failed"] = NOW - 10 * DAY

    deleted = job_logs_to_delete(logs, frozenset({"failed"}), {}, NOW)

    assert deleted == []
