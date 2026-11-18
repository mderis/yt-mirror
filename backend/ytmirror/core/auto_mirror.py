"""What auto-mirror queues, what it asks first, and what waits for an exact date.

Implements the decisions of R-MI-02 (every eligible video, now and after
every check), R-MI-03 (the date limit, with approximate dates), R-MI-05
(never an excluded video), R-MI-06 with D-092 (at most a few missing files
again by itself), R-QU-09 (a failed video at most once every 6 hours, never a
permanent failure) and D-095 (a large start is asked first). "Mirror
everything missing" (R-MI-04) takes the same videos, without the date limit.

This module must not read a clock or store anything: time is passed in.

Tests: backend/tests/unit/core/test_auto_mirror.py
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from enum import StrEnum

from ytmirror.core.channels import Channel, Video, VideoStatus
from ytmirror.core.dates import possible_range
from ytmirror.core.errors import ErrorKind

AUTO_MIRROR_ASK_ABOVE = 5
"""Above this many videos to download, turning auto-mirror on asks first (R-MI-02, D-095)."""

MISSING_AGAIN_AT_MOST = 5
"""Auto-mirror downloads at most this many missing files of a channel again by itself
(R-MI-06, D-092). Above, it asks."""

FAILED_AGAIN_AFTER_S = 6 * 60 * 60
"""Auto-mirror tries a failed video again at most once in this time (R-QU-09)."""

BYTES_PER_SECOND = {
    None: 1_000_000,
    2160: 3_000_000,
    1440: 1_500_000,
    1080: 600_000,
    720: 300_000,
    480: 150_000,
}
"""A typical size of one second of video at a height, video and audio together, for the
estimate of a large start (D-095). An estimate only: the real size comes with the lookup."""

TYPICAL_DURATION_S = 10 * 60
"""The length assumed for a video whose duration the listing did not give."""


class AutoMirrorAnswer(StrEnum):
    """The answers to the question before a large start of auto-mirror (D-095)."""

    MIRROR_ALL = "mirror_all"
    ONLY_NEW = "only_new"
    TURN_OFF = "turn_off"


@dataclass(frozen=True, slots=True)
class AutoMirrorQuestion:
    """Auto-mirror waits for the user before it starts many downloads (R-MI-02, D-095).

    Attributes:
        count: How many videos it would download.
        estimated_bytes: About how much room they take.
    """

    count: int
    estimated_bytes: int


@dataclass(frozen=True, slots=True)
class AutoPlan:
    """What auto-mirror does for one channel now.

    Attributes:
        new: Videos to queue: not downloaded, or failed long enough ago.
        missing: Videos whose file is missing, to queue unless too many (D-092).
        decide_first: Videos whose approximate date cannot decide the date limit:
            their exact date is fetched first (R-MI-03).
    """

    new: tuple[Video, ...] = ()
    missing: tuple[Video, ...] = ()
    decide_first: tuple[Video, ...] = ()


def auto_plan(
    channel: Channel, videos: Sequence[Video], busy: Collection[str], now: int
) -> AutoPlan:
    """Return what auto-mirror does for a channel now (R-MI-02, R-MI-03, R-QU-09).

    Args:
        channel: The channel, with its date limit.
        videos: Its catalogue.
        busy: Videos that wait or run already.
        now: The time now.

    Returns:
        The plan. Nothing when auto-mirror is off or the channel is paused.
    """
    if not channel.auto_mirror or channel.paused:
        return AutoPlan()
    new: list[Video] = []
    missing: list[Video] = []
    decide: list[Video] = []
    for video in videos:
        if not eligible(video, busy, now):
            continue
        verdict = after_limit(video, channel.mirror_after)
        if verdict is None:
            decide.append(video)
        elif verdict:
            (missing if video.status is VideoStatus.FILE_MISSING else new).append(video)
    return AutoPlan(new=tuple(new), missing=tuple(missing), decide_first=tuple(decide))


def eligible(video: Video, busy: Collection[str], now: int) -> bool:
    """Return whether a video is one auto-mirror would queue, apart from the date limit.

    Not excluded (R-MI-05), not removed from YouTube, not synced, not waiting or
    running. A failed video only when its failure can pass and it failed at least
    6 hours ago (R-QU-09).

    Args:
        video: The video.
        busy: Videos that wait or run already.
        now: The time now.
    """
    if video.excluded or video.gone or video.id in busy:
        return False
    if video.status in (VideoStatus.NOT_DOWNLOADED, VideoStatus.FILE_MISSING):
        return True
    if video.status is VideoStatus.FAILED:
        code = video.last_error_code
        failed_at = video.last_error_at or 0
        return (
            code is not None
            and code.kind is ErrorKind.TRANSIENT
            and now - failed_at >= FAILED_AGAIN_AFTER_S
        )
    return False


def missing_videos(videos: Sequence[Video], busy: Collection[str]) -> list[Video]:
    """Return the videos "Mirror everything missing" queues (R-MI-04).

    Every video without a file that is not excluded, not removed and not waiting
    or running: not downloaded, file missing, or failed with a failure that can
    pass. The date limit of auto-mirror does not apply: this is an action of the user.

    Args:
        videos: The catalogue of a channel.
        busy: Videos that wait or run already.
    """
    return [
        video
        for video in videos
        if not (video.excluded or video.gone or video.id in busy)
        and (
            video.status in (VideoStatus.NOT_DOWNLOADED, VideoStatus.FILE_MISSING)
            or (
                video.status is VideoStatus.FAILED
                and video.last_error_code is not None
                and video.last_error_code.kind is ErrorKind.TRANSIENT
            )
        )
    ]


def after_limit(video: Video, mirror_after: int | None) -> bool | None:
    """Return whether a video falls on or after the date limit, or None when it cannot say.

    The limit is the start of a day: that day is included (R-MI-03). An exact date
    decides at once. An approximate date decides only when its whole possible range
    lies before or after the limit; a video without a date cannot decide.

    Args:
        video: The video.
        mirror_after: The start of the first day to mirror, or None for no limit.
    """
    if mirror_after is None:
        return True
    if video.published_at is None:
        return None
    if video.published_exact or video.published_precision is None:
        return video.published_at >= mirror_after
    earliest, latest = possible_range(video.published_at, video.published_precision)
    if earliest >= mirror_after:
        return True
    if latest < mirror_after:
        return False
    return None


def estimated_bytes(videos: Sequence[Video], height: int | None) -> int:
    """Return an estimate of the room some videos take at a height (D-095).

    Args:
        videos: The videos.
        height: The height of the channel's quality, or None for the best available.
    """
    rate = BYTES_PER_SECOND.get(height, BYTES_PER_SECOND[None])
    return sum(rate * (video.duration_s or TYPICAL_DURATION_S) for video in videos)
