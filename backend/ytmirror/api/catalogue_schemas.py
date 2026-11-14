"""Request and response models of the HTTP API for channels and their catalogue.

The OpenAPI schema generated from these models is the contract with the
frontend (docs/ARCHITECTURE.md section 8). After a change here, run
``npm --prefix frontend run gen:api``. This module must not contain logic:
a model only says how a value of the app looks on the wire.

Tests: backend/tests/api/test_channels.py, test_state.py and test_videos.py
"""

from pydantic import BaseModel

from ytmirror.core.channels import (
    ChannelStatus,
    ChannelView,
    CheckKind,
    DatePrecision,
    Quality,
    TaskKind,
    TaskProgress,
    VideoStatus,
    VideoView,
    YouTubePause,
)
from ytmirror.core.errors import ErrorCode
from ytmirror.services.channels import ChannelLookup, ChosenFolder
from ytmirror.services.state import AppState


class Progress(BaseModel):
    """How far a first listing or a full check has come (R-CH-11, R-CH-27).

    Attributes:
        channel_id: The channel.
        kind: What is running.
        done: How many videos were read so far.
        total: About how many there are, or None when the catalogue had none.
    """

    channel_id: str
    kind: TaskKind
    done: int
    total: int | None

    @classmethod
    def of(cls, progress: TaskProgress) -> Progress:
        """Return the wire form of a progress."""
        return cls(
            channel_id=progress.channel_id,
            kind=progress.kind,
            done=progress.done,
            total=progress.total,
        )


class Channel(BaseModel):
    """One channel as the interface shows it (R-CH-34, R-CH-35).

    Attributes:
        id: The channel ID.
        title: The name of the channel.
        handle: The handle with its ``@``, or None.
        url: The address of the channel at YouTube.
        folder: The channel folder as an absolute path.
        folder_is_custom: Whether the user chose the folder.
        quality: The quality of this channel, or None for the default.
        auto_mirror: Whether auto-mirror is on.
        mirror_after: Auto-mirror only videos uploaded after this time, or None.
        paused: Whether the channel is paused.
        status: The one status line (R-FB-01).
        videos: How many videos the catalogue has.
        synced: How many of them are synced.
        excluded: How many of them are excluded.
        size_bytes: The size of the synced files together.
        new_videos: How many videos are new (R-CH-15).
        first_listed_at: When the first listing completed, or None while it has not.
        last_check_at: The last successful check of either kind, or None.
        last_full_check_at: The last successful full check, or None.
        last_check_error: The error code of the last check when it failed, or None.
        progress: The first listing or full check that is running, or None.
        pictures: A number that grows when more pictures of the channel are cached.
        avatar_version: A number that grows when the avatar of the channel was cached anew.
        catalogue_version: A number that grows with every successful check of the channel.
    """

    id: str
    title: str
    handle: str | None
    url: str
    folder: str
    folder_is_custom: bool
    quality: Quality | None
    auto_mirror: bool
    mirror_after: int | None
    paused: bool
    status: ChannelStatus
    videos: int
    synced: int
    excluded: int
    size_bytes: int
    new_videos: int
    first_listed_at: int | None
    last_check_at: int | None
    last_full_check_at: int | None
    last_check_error: ErrorCode | None
    progress: Progress | None
    pictures: int
    avatar_version: int
    catalogue_version: int

    @classmethod
    def of(cls, view: ChannelView) -> Channel:
        """Return the wire form of a channel view."""
        channel = view.channel
        return cls(
            id=channel.id,
            title=channel.title,
            handle=channel.handle,
            url=channel.url,
            folder=view.folder,
            folder_is_custom=channel.folder_is_custom,
            quality=channel.quality,
            auto_mirror=channel.auto_mirror,
            mirror_after=channel.mirror_after,
            paused=channel.paused,
            status=view.status,
            videos=view.totals.videos,
            synced=view.totals.synced,
            excluded=view.totals.excluded,
            size_bytes=view.totals.size_bytes,
            new_videos=view.totals.new,
            first_listed_at=channel.first_listed_at,
            last_check_at=channel.last_check_at,
            last_full_check_at=channel.last_full_check_at,
            last_check_error=channel.last_check_error,
            progress=None if view.progress is None else Progress.of(view.progress),
            pictures=view.pictures,
            avatar_version=view.avatar_version,
            catalogue_version=view.catalogue_version,
        )


class Video(BaseModel):
    """One video of a catalogue, with the fields a list needs (R-CH-10).

    Attributes:
        id: The video ID.
        title: The title.
        duration_s: The length in seconds, or None.
        view_count: The number of views, or None.
        published_at: The exact published time, or None while it is not known exactly.
        published_around: For an approximate date, the moment to show it from (R-DT-04).
        published_precision: The unit of an approximate date, or None.
        status: The stored status.
        is_new: Whether the video counts as new (R-CH-15).
        gone: Whether it is removed from YouTube (R-CH-14).
        excluded: Whether it is excluded.
    """

    id: str
    title: str
    duration_s: int | None
    view_count: int | None
    published_at: int | None
    published_around: int | None
    published_precision: DatePrecision | None
    status: VideoStatus
    is_new: bool
    gone: bool
    excluded: bool

    @classmethod
    def of(cls, view: VideoView) -> Video:
        """Return the wire form of a video view."""
        video = view.video
        return cls(
            id=video.id,
            title=video.title,
            duration_s=video.duration_s,
            view_count=video.view_count,
            published_at=video.published_at if video.published_exact else None,
            published_around=view.published_around,
            published_precision=video.published_precision,
            status=video.status,
            is_new=view.is_new,
            gone=video.gone,
            excluded=video.excluded,
        )


class VideosResponse(BaseModel):
    """The answer of ``GET /api/channels/{id}/videos``.

    Attributes:
        videos: The catalogue in the order of the channel, newest first.
    """

    videos: list[Video]


class Pause(BaseModel):
    """The pause of what the app asks of YouTube by itself (R-ER-05).

    Attributes:
        code: Why the app pauses.
        until: When it tries again, as seconds since the epoch.
    """

    code: ErrorCode
    until: int

    @classmethod
    def of(cls, pause: YouTubePause | None) -> Pause | None:
        """Return the wire form of a pause, or None when there is none."""
        return None if pause is None else cls(code=pause.code, until=pause.until)


class DiskSpace(BaseModel):
    """The disk the library is on (R-UI-01).

    Attributes:
        name: The name of the volume.
        free_bytes: How much room is left on it.
    """

    name: str
    free_bytes: int


class StateResponse(BaseModel):
    """The answer of ``GET /api/state``: the app as the window draws it.

    Attributes:
        channels: Every channel, in the order of the sidebar.
        open_channel_id: The channel that was open last, or None (R-UI-02).
        library_folder: The library folder as a path.
        disk: The disk the library is on.
        can_choose_folder: Whether the folder dialog of macOS can be shown.
        youtube_pause: The pause of the whole app, or None (R-ER-05).
    """

    channels: list[Channel]
    open_channel_id: str | None
    library_folder: str
    disk: DiskSpace
    can_choose_folder: bool
    youtube_pause: Pause | None

    @classmethod
    def of(cls, state: AppState) -> StateResponse:
        """Return the wire form of the app state."""
        return cls(
            channels=[Channel.of(view) for view in state.channels],
            open_channel_id=state.open_channel_id,
            library_folder=state.library_folder,
            disk=DiskSpace(name=state.disk.name, free_bytes=state.disk.free_bytes),
            can_choose_folder=state.can_choose_folder,
            youtube_pause=Pause.of(state.youtube_pause),
        )


class OpenChannelRequest(BaseModel):
    """The body of ``PUT /api/state/open-channel``.

    Attributes:
        channel_id: The channel the user has open, or None for no channel.
    """

    channel_id: str | None


class LookupRequest(BaseModel):
    """The body of ``POST /api/channels/lookup``.

    Attributes:
        text: What the user pasted or typed (R-CH-01).
    """

    text: str


class LookupResponse(BaseModel):
    """The preview of a channel before the user confirms (R-CH-03 to R-CH-06).

    The video count is not in it: it is fetched apart, so it never delays the preview.

    Attributes:
        channel_id: The channel ID.
        title: The name of the channel.
        handle: The handle with its ``@``, or None.
        has_avatar: Whether the channel has an avatar to show.
        existing: Whether the channel was added before (R-CH-04).
        folder: The folder the channel gets when the user chooses none.
        video_files: How many video files that folder already contains (R-CH-06).
    """

    channel_id: str
    title: str
    handle: str | None
    has_avatar: bool
    existing: bool
    folder: str
    video_files: int

    @classmethod
    def of(cls, lookup: ChannelLookup) -> LookupResponse:
        """Return the wire form of a lookup."""
        return cls(
            channel_id=lookup.facts.channel_id,
            title=lookup.facts.title,
            handle=lookup.facts.handle,
            has_avatar=lookup.facts.avatar_url is not None,
            existing=lookup.existing,
            folder=lookup.folder,
            video_files=lookup.video_files,
        )


class VideoCountResponse(BaseModel):
    """The answer of ``GET /api/channels/lookup/{id}/video-count``.

    Attributes:
        video_count: The number of videos of the preview, or None when YouTube
            gave none in time (R-CH-03).
    """

    video_count: int | None


class ChosenFolderResponse(BaseModel):
    """The answer of ``POST /api/folders/choose``.

    Attributes:
        folder: The folder the user chose, or None after Cancel.
        video_files: How many video files it already contains (R-CH-06).
    """

    folder: str | None
    video_files: int

    @classmethod
    def of(cls, chosen: ChosenFolder | None) -> ChosenFolderResponse:
        """Return the wire form of a choice, or of a cancelled dialog."""
        if chosen is None:
            return cls(folder=None, video_files=0)
        return cls(folder=chosen.folder, video_files=chosen.video_files)


class AddChannelRequest(BaseModel):
    """The body of ``POST /api/channels``: step 2 of the add channel dialog (R-CH-05).

    Attributes:
        channel_id: The channel that was looked up.
        folder: A folder the folder dialog returned, or None for the default.
        quality: The quality of this channel, or None for "use default".
        auto_mirror: Whether everything is mirrored automatically.
        mirror_after: Auto-mirror only videos uploaded after this time, or None.
    """

    channel_id: str
    folder: str | None = None
    quality: Quality | None = None
    auto_mirror: bool = False
    mirror_after: int | None = None


class AddChannelResponse(BaseModel):
    """The answer of ``POST /api/channels``.

    Attributes:
        channel: The channel as it is now.
        existing: True when the channel was there already and nothing was added (R-CH-04).
    """

    channel: Channel
    existing: bool


class ChangeChannelRequest(BaseModel):
    """The body of ``PATCH /api/channels/{id}``. More fields arrive with channel settings in M7.

    Attributes:
        paused: True to pause the channel, False to resume it (R-CH-31).
    """

    paused: bool


class CheckRequest(BaseModel):
    """The body of ``POST /api/channels/{id}/check``.

    Attributes:
        kind: A quick check ("Check now") or a full check (R-CH-23).
    """

    kind: CheckKind = CheckKind.QUICK


class CheckAllResponse(BaseModel):
    """The answer of ``POST /api/channels/check-all``.

    Attributes:
        channels: How many channels are being checked.
    """

    channels: int


class CancelCheckResponse(BaseModel):
    """The answer of ``POST /api/channels/{id}/check/cancel``.

    Attributes:
        cancelled: Whether there was a full check to cancel (R-CH-27).
    """

    cancelled: bool


class ChannelUpdatedEvent(BaseModel):
    """The data of the ``channel.updated`` event of ``GET /api/events``.

    Attributes:
        channel: The channel as it is now.
    """

    channel: Channel


class TaskProgressEvent(BaseModel):
    """The data of the ``task.progress`` event of ``GET /api/events``.

    Attributes:
        progress: How far a first listing or a full check has come.
    """

    progress: Progress


class BannerChangedEvent(BaseModel):
    """The data of the ``banner.changed`` event of ``GET /api/events``.

    Attributes:
        youtube_pause: The pause of the whole app, or None when it ended (R-ER-05).
    """

    youtube_pause: Pause | None
