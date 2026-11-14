"""The status machines: what a video's status may become, and what a channel shows.

Implements R-QA-08 (docs/ARCHITECTURE.md section 6.1): a video's status
changes only along the allowed transitions, through ``change_status``.
Nothing else may assign a status. It also derives the one status line of a
channel (R-FB-01, section 6.2) and whether a video is "new" (R-CH-15).

This module must not read a clock or store anything: time is passed in.

Tests: backend/tests/unit/core/test_status.py
"""

from dataclasses import dataclass

from ytmirror.core.channels import Channel, ChannelStatus, Video, VideoStatus

NEW_FOR_S = 14 * 24 * 60 * 60
"""How long a video stays "new" after the app first saw it (R-CH-15)."""

_S = VideoStatus

ALLOWED_TRANSITIONS: frozenset[tuple[VideoStatus, VideoStatus]] = frozenset(
    {
        (_S.NOT_DOWNLOADED, _S.QUEUED),  # enqueue
        (_S.QUEUED, _S.DOWNLOADING),  # a worker picks it
        (_S.QUEUED, _S.NOT_DOWNLOADED),  # cancel
        (_S.DOWNLOADING, _S.PROCESSING),  # the streams are done
        (_S.DOWNLOADING, _S.NOT_DOWNLOADED),  # cancel
        (_S.DOWNLOADING, _S.FAILED),
        (_S.PROCESSING, _S.SYNCED),  # verified
        (_S.PROCESSING, _S.FAILED),
        (_S.FAILED, _S.QUEUED),  # retry
        (_S.SYNCED, _S.FILE_MISSING),  # the file was not found at a check
        (_S.SYNCED, _S.QUEUED),  # re-download: the old file stays until the new one is verified
        (_S.FILE_MISSING, _S.QUEUED),  # enqueue
    }
)
"""Every allowed change of a video's status, as (from, to)."""


class InvalidTransitionError(ValueError):
    """A status change that the status machine does not allow. A programming error.

    Attributes:
        from_status: The status the video has.
        to_status: The status that was asked for.
    """

    def __init__(self, from_status: VideoStatus, to_status: VideoStatus) -> None:
        """Create the error.

        Args:
            from_status: The status the video has.
            to_status: The status that was asked for.
        """
        super().__init__(f"A video cannot go from {from_status.value} to {to_status.value}")
        self.from_status = from_status
        self.to_status = to_status


@dataclass(frozen=True, slots=True)
class StatusChange:
    """One change of a video's status, to be recorded (R-LG-03).

    Attributes:
        video_id: The video.
        from_status: The status before.
        to_status: The status after.
        reason: Why it changed, as a short stable word.
    """

    video_id: str
    from_status: VideoStatus
    to_status: VideoStatus
    reason: str


def change_status(
    video_id: str, current: VideoStatus, to: VideoStatus, reason: str
) -> StatusChange:
    """Validate a change of a video's status and return the event to record.

    Implements R-QA-08. Nothing is changed here: the caller stores the new
    status together with the returned event.

    Args:
        video_id: The video.
        current: The status the video has now.
        to: The status it should get.
        reason: Why, as a short stable word.

    Returns:
        The change to record.

    Raises:
        InvalidTransitionError: When the status machine does not allow this change.
    """
    if (current, to) not in ALLOWED_TRANSITIONS:
        raise InvalidTransitionError(current, to)
    return StatusChange(video_id=video_id, from_status=current, to_status=to, reason=reason)


def is_new(video: Video, now: int) -> bool:
    """Return whether a video counts as "new" (R-CH-15).

    A video is new when the app first saw it in a check after the first
    listing of its channel, until it is synced, excluded, or 14 days have
    passed since the app first saw it. The video's own date plays no part.

    Args:
        video: The video.
        now: The current time, as seconds since the epoch.
    """
    if video.seen_in_first_listing or video.excluded or video.status is VideoStatus.SYNCED:
        return False
    return now - video.first_seen_at < NEW_FOR_S


def channel_status(channel: Channel, *, checking: bool, new_videos: int) -> ChannelStatus:
    """Return the one status line of a channel (R-FB-01, R-CH-34).

    One status is shown at a time, by the priority of R-FB-01: error,
    mirroring, checking, matching, exact dates, new, paused, up to date.
    The statuses of later milestones take their place in this order when
    they are built.

    Args:
        channel: The channel.
        checking: Whether a check of this channel is waiting or running.
        new_videos: How many of its videos are new.
    """
    if channel.last_check_error is not None:
        return ChannelStatus.COULD_NOT_CHECK
    if checking:
        return ChannelStatus.CHECKING
    if new_videos > 0:
        return ChannelStatus.NEW_VIDEOS
    if channel.paused:
        return ChannelStatus.PAUSED
    return ChannelStatus.UP_TO_DATE
