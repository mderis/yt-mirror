"""Tests of the decisions of auto-mirror: what it queues, asks and fetches the date of first."""

import dataclasses
from collections.abc import Sequence

from tests.fixtures.catalogue import NOW, make_channel, make_video
from ytmirror.core.auto_mirror import (
    FAILED_AGAIN_AFTER_S,
    after_limit,
    auto_plan,
    eligible,
    estimated_bytes,
    missing_videos,
)
from ytmirror.core.channels import DatePrecision, Video, VideoStatus
from ytmirror.core.dates import DAY_S
from ytmirror.core.errors import ErrorCode

ON = dataclasses.replace(make_channel(), auto_mirror=True)
LIMIT = NOW - 30 * DAY_S
"""The start of the first day auto-mirror takes, a month ago."""


def ids(videos: Sequence[Video]) -> list[str]:
    """Return the IDs of videos."""
    return [video.id for video in videos]


def test_auto_mirror_takes_every_video_that_is_not_excluded_synced_or_removed() -> None:
    """R-MI-02, R-MI-05: excluded, synced, removed and waiting videos are left out."""
    videos = [
        make_video(1),
        make_video(2, excluded=True),
        make_video(3, status=VideoStatus.SYNCED),
        make_video(4, gone=True),
        make_video(5),
        make_video(6, status=VideoStatus.QUEUED),
    ]

    plan = auto_plan(ON, videos, busy={make_video(5).id}, now=NOW)

    assert ids(plan.new) == [make_video(1).id]


def test_auto_mirror_off_or_a_paused_channel_takes_nothing() -> None:
    """R-MI-02, R-CH-31: off by default; a paused channel's downloads do not run."""
    videos = [make_video(1)]

    assert auto_plan(make_channel(), videos, busy=(), now=NOW).new == ()
    assert auto_plan(dataclasses.replace(ON, paused=True), videos, busy=(), now=NOW).new == ()


def test_missing_files_are_kept_apart_for_their_limit() -> None:
    """R-MI-06, D-092: missing files are queued apart, so a limit can hold them."""
    plan = auto_plan(ON, [make_video(1, status=VideoStatus.FILE_MISSING)], busy=(), now=NOW)

    assert (ids(plan.new), ids(plan.missing)) == ([], [make_video(1).id])


def test_an_exact_date_decides_the_limit_and_the_day_itself_is_included() -> None:
    """R-MI-03: the day of the limit is included, from its start."""
    on_the_day = make_video(1, published_at=LIMIT, published_exact=True, published_precision=None)
    before = make_video(2, published_at=LIMIT - 1, published_exact=True, published_precision=None)

    assert after_limit(on_the_day, LIMIT) is True
    assert after_limit(before, LIMIT) is False
    assert after_limit(before, None) is True


def test_an_approximate_date_decides_only_when_its_whole_range_is_on_one_side() -> None:
    """R-MI-03: a range that includes the limit waits for the exact date."""
    long_after = make_video(1, published_at=NOW, published_precision=DatePrecision.DAY)
    long_before = make_video(
        2, published_at=LIMIT - 400 * DAY_S, published_precision=DatePrecision.YEAR
    )
    across = make_video(3, published_at=LIMIT + 3 * DAY_S, published_precision=DatePrecision.WEEK)

    assert after_limit(long_after, LIMIT) is True
    assert after_limit(long_before, LIMIT) is False
    assert after_limit(across, LIMIT) is None


def test_a_video_whose_date_cannot_decide_gets_its_exact_date_first() -> None:
    """R-MI-03: such a video is neither queued nor left out; its exact date is fetched first."""
    channel = dataclasses.replace(ON, mirror_after=LIMIT)
    across = make_video(3, published_at=LIMIT + 3 * DAY_S, published_precision=DatePrecision.WEEK)
    no_date = make_video(4, published_at=None, published_precision=None)

    plan = auto_plan(channel, [across, no_date], busy=(), now=NOW)

    assert (plan.new, ids(plan.decide_first)) == ((), [across.id, no_date.id])


def test_a_failed_video_is_tried_again_after_6_hours_but_never_a_permanent_failure() -> None:
    """R-QU-09: at most once every 6 hours, never after a permanent failure."""
    transient = dataclasses.replace(
        make_video(1, status=VideoStatus.FAILED),
        last_error_code=ErrorCode.NETWORK_UNREACHABLE,
        last_error_at=NOW - FAILED_AGAIN_AFTER_S,
    )
    recent = dataclasses.replace(transient, last_error_at=NOW - FAILED_AGAIN_AFTER_S + 1)
    permanent = dataclasses.replace(transient, last_error_code=ErrorCode.MEMBERS_ONLY)

    assert eligible(transient, (), NOW) is True
    assert eligible(recent, (), NOW) is False
    assert eligible(permanent, (), NOW) is False


def test_mirror_everything_missing_takes_old_videos_too() -> None:
    """R-MI-04: by hand, without the date limit of auto-mirror, but never excluded videos."""
    old = make_video(1, published_at=LIMIT - 400 * DAY_S, published_precision=DatePrecision.YEAR)
    failed = dataclasses.replace(
        make_video(2, status=VideoStatus.FAILED), last_error_code=ErrorCode.RATE_LIMITED
    )
    members = dataclasses.replace(
        make_video(3, status=VideoStatus.FAILED), last_error_code=ErrorCode.MEMBERS_ONLY
    )
    videos = [
        old,
        failed,
        members,
        make_video(4, excluded=True),
        make_video(5, status=VideoStatus.FILE_MISSING),
    ]

    assert ids(missing_videos(videos, busy=())) == [old.id, failed.id, make_video(5).id]


def test_the_estimate_of_a_large_start_grows_with_length_and_height() -> None:
    """R-MI-02, D-095: the question shows an estimated size, larger for longer, sharper videos."""
    videos = [make_video(1, duration_s=600), make_video(2, duration_s=1200)]

    assert estimated_bytes(videos, 1080) == 600_000 * 1800
    assert (
        estimated_bytes(videos, 480) < estimated_bytes(videos, 1080) < estimated_bytes(videos, None)
    )
