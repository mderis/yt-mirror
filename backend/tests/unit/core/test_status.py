"""Tests of ``ytmirror.core.status``."""

import itertools

import pytest

from tests.fixtures.catalogue import NOW, make_channel, make_video
from ytmirror.core.channels import ChannelStatus, VideoStatus
from ytmirror.core.errors import ErrorCode
from ytmirror.core.status import (
    ALLOWED_TRANSITIONS,
    NEW_FOR_S,
    InvalidTransitionError,
    StatusChange,
    change_status,
    channel_status,
    is_new,
)

S = VideoStatus
DAY = 24 * 60 * 60


def test_the_allowed_transitions_are_exactly_those_of_the_architecture() -> None:
    """R-QA-08: the table is the one of ARCHITECTURE section 6.1, no more and no less."""
    assert {
        (S.NOT_DOWNLOADED, S.QUEUED),
        (S.QUEUED, S.DOWNLOADING),
        (S.QUEUED, S.NOT_DOWNLOADED),
        (S.DOWNLOADING, S.PROCESSING),
        (S.DOWNLOADING, S.NOT_DOWNLOADED),
        (S.DOWNLOADING, S.FAILED),
        (S.PROCESSING, S.SYNCED),
        (S.PROCESSING, S.FAILED),
        (S.FAILED, S.QUEUED),
        (S.SYNCED, S.FILE_MISSING),
        (S.SYNCED, S.QUEUED),
        (S.FILE_MISSING, S.QUEUED),
    } == ALLOWED_TRANSITIONS


@pytest.mark.parametrize(("current", "to"), sorted(ALLOWED_TRANSITIONS))
def test_an_allowed_change_returns_the_event_to_record(current: S, to: S) -> None:
    """R-QA-08: a change along a transition is accepted and described for the status history."""
    change = change_status("vid00000001", current, to, "test")

    assert change == StatusChange("vid00000001", current, to, "test")


@pytest.mark.parametrize(
    ("current", "to"),
    sorted(set(itertools.product(S, S)) - ALLOWED_TRANSITIONS),
)
def test_every_other_change_is_refused(current: S, to: S) -> None:
    """R-QA-08: a change that is no transition is refused, also a change to the same status."""
    with pytest.raises(InvalidTransitionError) as refused:
        change_status("vid00000001", current, to, "test")

    assert refused.value.from_status is current
    assert refused.value.to_status is to
    assert current.value in str(refused.value)
    assert to.value in str(refused.value)


def test_a_video_of_the_first_listing_is_not_new() -> None:
    """R-CH-15: only a video first seen after the first listing is new."""
    video = make_video(seen_in_first_listing=True, first_seen_at=NOW)

    assert is_new(video, NOW) is False


def test_a_video_first_seen_in_a_later_check_is_new() -> None:
    """R-CH-15: a video first seen in a check after the first listing is new."""
    video = make_video(seen_in_first_listing=False, first_seen_at=NOW)

    assert is_new(video, NOW) is True


def test_a_video_stays_new_for_fourteen_days_after_the_app_first_saw_it() -> None:
    """R-CH-15: new ends 14 days after the app first saw the video."""
    video = make_video(seen_in_first_listing=False, first_seen_at=NOW)

    assert is_new(video, NOW + NEW_FOR_S - 1) is True
    assert is_new(video, NOW + NEW_FOR_S) is False
    assert NEW_FOR_S == 14 * DAY


def test_the_date_of_a_video_plays_no_part_in_being_new() -> None:
    """R-CH-15: an old video that the app saw for the first time today is new."""
    video = make_video(
        seen_in_first_listing=False, first_seen_at=NOW, published_at=NOW - 3650 * DAY
    )

    assert is_new(video, NOW) is True


def test_a_synced_video_is_not_new() -> None:
    """R-CH-15: a video is new until it is synced."""
    video = make_video(seen_in_first_listing=False, first_seen_at=NOW, status=S.SYNCED)

    assert is_new(video, NOW) is False


def test_an_excluded_video_is_not_new() -> None:
    """R-CH-15: a video is new until it is excluded."""
    video = make_video(seen_in_first_listing=False, first_seen_at=NOW, excluded=True)

    assert is_new(video, NOW) is False


def test_a_channel_with_nothing_to_say_is_up_to_date() -> None:
    """R-FB-01, R-CH-34: a channel that was checked and has no new videos is up to date."""
    status = channel_status(make_channel(), checking=False, new_videos=0)

    assert status is ChannelStatus.UP_TO_DATE


def test_a_paused_channel_says_so() -> None:
    """R-FB-01: a paused channel shows "Paused"."""
    status = channel_status(make_channel(paused=True), checking=False, new_videos=0)

    assert status is ChannelStatus.PAUSED


def test_new_videos_come_before_paused() -> None:
    """R-FB-01: by priority, new videos are shown before paused."""
    status = channel_status(make_channel(paused=True), checking=False, new_videos=3)

    assert status is ChannelStatus.NEW_VIDEOS


def test_checking_comes_before_new_videos() -> None:
    """R-FB-01: by priority, a running check is shown before new videos."""
    status = channel_status(make_channel(), checking=True, new_videos=3)

    assert status is ChannelStatus.CHECKING


def test_a_failed_check_comes_first() -> None:
    """R-FB-01: by priority, an error is shown before everything else."""
    failed = make_channel(last_check_error=ErrorCode.NETWORK_UNREACHABLE, paused=True)

    status = channel_status(failed, checking=True, new_videos=3)

    assert status is ChannelStatus.COULD_NOT_CHECK
