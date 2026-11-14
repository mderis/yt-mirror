"""Domain data of channels and their catalogue.

Frozen dataclasses and enums only: a channel, a video, what a lookup and a
listing of YouTube give, and the two kinds of check. The rules that work on
them are in ``catalogue.py``, ``status.py`` and ``dates.py``. This module
must not read or write anything.

Tests: backend/tests/unit/core/test_channels.py
"""

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum

from ytmirror.core.errors import ErrorCode

CHANNEL_ADDRESS = "https://www.youtube.com/channel/"
"""What the canonical address of a channel starts with. The channel ID follows."""


class Quality(StrEnum):
    """The quality a channel asks for (R-QL-01). The rules that use it arrive in milestone M3."""

    BEST = "best"
    P2160 = "2160"
    P1440 = "1440"
    P1080 = "1080"
    P720 = "720"
    P480 = "480"


class DatePrecision(StrEnum):
    """The unit YouTube gave an approximate date in (R-DT-04, docs/GLOSSARY.md)."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class CheckKind(StrEnum):
    """The two kinds of check (R-CH-12, docs/DECISIONS.md D-059)."""

    QUICK = "quick"
    FULL = "full"


class VideoStatus(StrEnum):
    """The stored status of a video (docs/ARCHITECTURE.md section 6.1)."""

    NOT_DOWNLOADED = "not_downloaded"
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    SYNCED = "synced"
    FILE_MISSING = "file_missing"
    FAILED = "failed"


class ChannelStatus(StrEnum):
    """The one status line of a channel (R-FB-01). Derived, never stored.

    Each milestone adds the statuses that can occur from it on.
    """

    COULD_NOT_CHECK = "could_not_check"
    CHECKING = "checking"
    NEW_VIDEOS = "new_videos"
    PAUSED = "paused"
    UP_TO_DATE = "up_to_date"


class ReferenceKind(StrEnum):
    """The forms in which a user can name a channel (R-CH-01)."""

    HANDLE = "handle"
    CHANNEL_ID = "channel_id"
    CUSTOM_NAME = "custom_name"
    USER_NAME = "user_name"


@dataclass(frozen=True, slots=True)
class ChannelReference:
    """A channel as the user named it, before YouTube was asked.

    Attributes:
        kind: The form the user used.
        value: The handle with its ``@``, the channel ID, or the name.
    """

    kind: ReferenceKind
    value: str

    @property
    def address(self) -> str:
        """The address of the channel at YouTube, without a tab."""
        if self.kind is ReferenceKind.HANDLE:
            return f"https://www.youtube.com/{self.value}"
        if self.kind is ReferenceKind.CHANNEL_ID:
            return f"{CHANNEL_ADDRESS}{self.value}"
        if self.kind is ReferenceKind.CUSTOM_NAME:
            return f"https://www.youtube.com/c/{self.value}"
        return f"https://www.youtube.com/user/{self.value}"


@dataclass(frozen=True, slots=True)
class ChannelFacts:
    """What YouTube says about a channel itself (R-CH-03).

    Attributes:
        channel_id: The channel ID (``UC...``).
        title: The name of the channel.
        handle: The handle with its ``@``, or None.
        avatar_url: The address of the avatar picture at YouTube, or None.
    """

    channel_id: str
    title: str
    handle: str | None
    avatar_url: str | None

    @property
    def url(self) -> str:
        """The canonical address of the channel."""
        return f"{CHANNEL_ADDRESS}{self.channel_id}"


@dataclass(frozen=True, slots=True)
class ListedVideo:
    """One video as a listing of its channel gives it.

    Attributes:
        id: The video ID.
        title: The title.
        duration_s: The length in seconds, or None when the listing has none.
        view_count: The rounded number of views, or None.
        published_at: The approximate published time as seconds since the epoch, or None.
            It is "the time of the listing minus N units" (docs/DECISIONS.md D-060).
        listed_at: When this entry was read, as seconds since the epoch.
        thumbnail_url: The address of a thumbnail at YouTube, or None.
    """

    id: str
    title: str
    duration_s: int | None
    view_count: int | None
    published_at: int | None
    listed_at: int
    thumbnail_url: str | None


@dataclass(frozen=True, slots=True)
class ChannelListing:
    """A listing of a channel that is read video by video (R-CH-12).

    The reader decides when to stop: nothing more is asked of YouTube than
    what was taken from ``videos``.

    Attributes:
        facts: The channel itself.
        videos: Its regular videos, newest first. It can be read once.
    """

    facts: ChannelFacts
    videos: Iterator[ListedVideo]


@dataclass(frozen=True, slots=True)
class Channel:
    """A channel the user added (docs/ARCHITECTURE.md section 5).

    Attributes:
        id: The channel ID.
        url: The canonical address.
        title: The name.
        handle: The handle with its ``@``, or None.
        avatar_url: The address of the avatar at YouTube, or None.
        folder: The channel folder: absolute, or relative to the library when not custom.
        folder_is_custom: Whether the user chose the folder.
        quality: The quality of this channel, or None for the default.
        auto_mirror: Whether auto-mirror is on.
        mirror_after: Auto-mirror only videos published after this time, or None.
        paused: Whether the channel is paused.
        first_listed_at: When the first listing completed, or None.
        last_check_at: The last successful check of either kind, or None.
        last_full_check_at: The last successful full check, or None.
        last_check_error: The error code of the last check when it failed, or None.
        position: The place in the sidebar, from 0.
    """

    id: str
    url: str
    title: str
    handle: str | None
    avatar_url: str | None
    folder: str
    folder_is_custom: bool
    quality: Quality | None = None
    auto_mirror: bool = False
    mirror_after: int | None = None
    paused: bool = False
    first_listed_at: int | None = None
    last_check_at: int | None = None
    last_full_check_at: int | None = None
    last_check_error: ErrorCode | None = None
    position: int = 0


@dataclass(frozen=True, slots=True)
class Video:
    """One regular video of a channel (docs/ARCHITECTURE.md section 5).

    Attributes:
        id: The video ID.
        channel_id: The channel it belongs to.
        title: The current title at YouTube.
        duration_s: The length in seconds, or None.
        view_count: The number of views, or None.
        published_at: The published time, or None while nothing is known.
        published_exact: False while only an approximate date is known.
        published_precision: The unit of an approximate date. None for an exact or missing date.
        thumbnail_url: The address of the thumbnail at YouTube, or None.
        channel_position: The place on the channel, 0 for the newest.
        status: The stored status.
        excluded: Whether the video is excluded.
        excluded_by: ``manual`` or a rule ID, or None.
        exclude_exception: Whether the user protected it from the rules.
        missing_checks: Consecutive successful full checks without this video.
        gone: Whether it is removed from YouTube.
        first_seen_at: When the app first saw it.
        last_seen_at: The last successful check that listed it.
        seen_in_first_listing: False means the video can be "new".
        file_name: The file relative to the channel folder, or None.
        file_size: The size of the file in bytes, or None.
        height: The downloaded height, or None.
        vcodec: The video codec of the file, or None.
        acodec: The audio codec of the file, or None.
        has_subtitles: ``manual``, ``auto`` or None.
        downloaded_at: When the file was completed, or None.
        last_error_code: The code of the last failure, or None.
        last_error_at: When the last failure happened, or None.
        attempts: Automatic attempts since the last success.
    """

    id: str
    channel_id: str
    title: str
    duration_s: int | None
    view_count: int | None
    published_at: int | None
    published_exact: bool
    published_precision: DatePrecision | None
    thumbnail_url: str | None
    channel_position: int
    first_seen_at: int
    last_seen_at: int
    seen_in_first_listing: bool
    status: VideoStatus = VideoStatus.NOT_DOWNLOADED
    excluded: bool = False
    excluded_by: str | None = None
    exclude_exception: bool = False
    missing_checks: int = 0
    gone: bool = False
    file_name: str | None = None
    file_size: int | None = None
    height: int | None = None
    vcodec: str | None = None
    acodec: str | None = None
    has_subtitles: str | None = None
    downloaded_at: int | None = None
    last_error_code: ErrorCode | None = None
    last_error_at: int | None = None
    attempts: int = 0


@dataclass(frozen=True, slots=True)
class ChannelTotals:
    """The numbers of a channel's catalogue (R-CH-35, R-CH-34).

    Attributes:
        videos: How many videos the catalogue has.
        synced: How many of them are synced.
        excluded: How many of them are excluded.
        size_bytes: The size of the files of the synced videos together.
        new: How many of them are new (R-CH-15).
    """

    videos: int = 0
    synced: int = 0
    excluded: int = 0
    size_bytes: int = 0
    new: int = 0
