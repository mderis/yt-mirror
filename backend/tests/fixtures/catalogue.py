"""Builders for channels, videos and listings (CODING-STANDARDS section 5)."""

from collections.abc import Iterable

from ytmirror.core.channels import (
    Channel,
    ChannelFacts,
    DatePrecision,
    ListedVideo,
    Video,
    VideoStatus,
)
from ytmirror.core.errors import ErrorCode

CHANNEL_ID = "UCaaaaaaaaaaaaaaaaaaaaaa"
OTHER_CHANNEL_ID = "UCbbbbbbbbbbbbbbbbbbbbbb"
NOW = 1_794_640_000
"""A fixed moment for tests: 14 November 2026, 07:06:40 UTC."""


def video_id(number: int) -> str:
    """Return a video ID of the right length for a number."""
    return f"vid{number:08d}"


def make_channel(
    channel_id: str = CHANNEL_ID,
    *,
    title: str = "Sample Channel",
    handle: str | None = "@samplechannel",
    folder: str = "Sample Channel",
    folder_is_custom: bool = False,
    paused: bool = False,
    first_listed_at: int | None = NOW,
    last_check_at: int | None = NOW,
    last_full_check_at: int | None = NOW,
    last_check_error: ErrorCode | None = None,
    position: int = 0,
) -> Channel:
    """Return a channel that was added and listed once."""
    return Channel(
        id=channel_id,
        url=f"https://www.youtube.com/channel/{channel_id}",
        title=title,
        handle=handle,
        avatar_url=f"https://images.example/{channel_id}.jpg",
        folder=folder,
        folder_is_custom=folder_is_custom,
        paused=paused,
        first_listed_at=first_listed_at,
        last_check_at=last_check_at,
        last_full_check_at=last_full_check_at,
        last_check_error=last_check_error,
        position=position,
    )


def make_video(
    number: int = 1,
    *,
    channel_id: str = CHANNEL_ID,
    title: str | None = None,
    duration_s: int | None = 600,
    view_count: int | None = 1000,
    published_at: int | None = NOW - 86_400,
    published_exact: bool = False,
    published_precision: DatePrecision | None = DatePrecision.DAY,
    thumbnail_url: str | None = None,
    position: int | None = None,
    first_seen_at: int = NOW,
    last_seen_at: int = NOW,
    seen_in_first_listing: bool = True,
    status: VideoStatus = VideoStatus.NOT_DOWNLOADED,
    excluded: bool = False,
    missing_checks: int = 0,
    gone: bool = False,
) -> Video:
    """Return a video as the catalogue stores it. Its position defaults to its number."""
    return Video(
        id=video_id(number),
        channel_id=channel_id,
        title=f"Video {number}" if title is None else title,
        duration_s=duration_s,
        view_count=view_count,
        published_at=published_at,
        published_exact=published_exact,
        published_precision=published_precision,
        thumbnail_url=thumbnail_url or f"https://images.example/{video_id(number)}.jpg",
        channel_position=number if position is None else position,
        first_seen_at=first_seen_at,
        last_seen_at=last_seen_at,
        seen_in_first_listing=seen_in_first_listing,
        status=status,
        excluded=excluded,
        missing_checks=missing_checks,
        gone=gone,
    )


def listed(
    number: int,
    *,
    title: str | None = None,
    duration_s: int | None = 600,
    view_count: int | None = 1000,
    published_at: int | None = NOW - 86_400,
    listed_at: int = NOW,
    thumbnail_url: str | None = None,
) -> ListedVideo:
    """Return a video as a listing gives it."""
    return ListedVideo(
        id=video_id(number),
        title=f"Video {number}" if title is None else title,
        duration_s=duration_s,
        view_count=view_count,
        published_at=published_at,
        listed_at=listed_at,
        thumbnail_url=thumbnail_url or f"https://images.example/{video_id(number)}.jpg",
    )


def listing_of(numbers: Iterable[int]) -> list[ListedVideo]:
    """Return a listing with one video per number, in that order."""
    return [listed(number) for number in numbers]


def make_facts(channel_id: str = CHANNEL_ID, title: str = "Sample Channel") -> ChannelFacts:
    """Return what YouTube says about a channel."""
    return ChannelFacts(
        channel_id=channel_id,
        title=title,
        handle="@samplechannel",
        avatar_url=f"https://images.example/{channel_id}.jpg",
    )
