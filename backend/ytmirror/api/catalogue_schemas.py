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
    CheckTrigger,
    DatePrecision,
    Quality,
    TaskKind,
    TaskProgress,
    VideoStatus,
    VideoView,
    YouTubePause,
)
from ytmirror.core.errors import ErrorCode
from ytmirror.core.jobs import JobProgress, Stage
from ytmirror.services.channels import ChannelLookup, ChosenFolder
from ytmirror.services.downloader import VideoDetails
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
        last_check_error_at: When that check failed, or None.
        progress: The first listing or full check that is running, or None.
        pictures: A number that grows when more pictures of the channel are cached.
        avatar_version: A number that grows when the avatar of the channel was cached anew.
        catalogue_version: A number that grows with every successful check of the channel.
        mirroring: While videos of the channel are downloaded, how many ended and how
            many there are (R-FB-01: "Mirroring X of Y"). Otherwise None.
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
    last_check_error_at: int | None
    progress: Progress | None
    pictures: int
    avatar_version: int
    catalogue_version: int
    mirroring: Mirroring | None = None

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
            last_check_error_at=channel.last_check_error_at,
            progress=None if view.progress is None else Progress.of(view.progress),
            pictures=view.pictures,
            avatar_version=view.avatar_version,
            catalogue_version=view.catalogue_version,
            mirroring=None
            if view.mirroring is None
            else Mirroring(done=view.mirroring[0], total=view.mirroring[1]),
        )


class Mirroring(BaseModel):
    """How far the downloads of a channel are (R-FB-01).

    Attributes:
        done: How many ended, well or not.
        total: How many there are in all.
    """

    done: int
    total: int


class Download(BaseModel):
    """How far the running download of a video is (R-QU-04).

    Attributes:
        job_id: The job.
        video_id: The video.
        channel_id: Its channel.
        stage: Video, audio or processing.
        fraction: How much of the stage is done, from 0 to 1, or None.
        speed_bps: Bytes per second, or None.
        left_s: Seconds left of the stage, or None.
        height: The height being downloaded, or None.
    """

    job_id: str
    video_id: str
    channel_id: str
    stage: Stage
    fraction: float | None
    speed_bps: float | None
    left_s: int | None
    height: int | None

    @classmethod
    def of(cls, progress: JobProgress) -> Download:
        """Return the wire form of a progress."""
        return cls(
            job_id=progress.job_id,
            video_id=progress.video_id,
            channel_id=progress.channel_id,
            stage=progress.stage,
            fraction=progress.fraction,
            speed_bps=progress.speed_bps,
            left_s=progress.left_s,
            height=progress.height,
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
        job_id: The job of a download that waits or runs, for Cancel, or None.
        download: How far a running download is (R-QU-04), or None.
        height: The height of the file of a synced video (R-FB-02), or None.
        file_size: The size of its file in bytes, or None.
        error_code: Why the last download failed (R-QU-08), or None.
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
    job_id: str | None = None
    download: Download | None = None
    height: int | None = None
    file_size: int | None = None
    error_code: ErrorCode | None = None

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
            job_id=view.job_id,
            download=None if view.progress is None else Download.of(view.progress),
            height=video.height,
            file_size=video.file_size,
            error_code=video.last_error_code,
        )


class MirrorRequest(BaseModel):
    """The body of ``POST /api/videos/mirror`` (R-MI-01).

    Attributes:
        ids: The videos to put in line, in this order.
    """

    ids: list[str]


class QueuedJob(BaseModel):
    """A download that was put in line.

    Attributes:
        job_id: The job.
        video_id: The video.
    """

    job_id: str
    video_id: str


class MirrorResponse(BaseModel):
    """The answer of ``POST /api/videos/mirror``.

    Attributes:
        jobs: The downloads that were put in line. A video that waits, runs or is
            synced already is left out.
    """

    jobs: list[QueuedJob]


class CancelJobResponse(BaseModel):
    """The answer of ``POST /api/jobs/{id}/cancel`` (R-QU-02).

    Attributes:
        cancelled: Whether there was a download that waited or ran.
    """

    cancelled: bool


class ChapterInfo(BaseModel):
    """One chapter of a video (R-UI-08).

    Attributes:
        start_s: Where it starts, in seconds.
        title: Its title.
    """

    start_s: float
    title: str


class FileFacts(BaseModel):
    """The file of a synced video, as the details panel shows it (R-UI-08).

    Attributes:
        name: The file name.
        size: Its size in bytes.
        width: The width of the video, or None.
        height: The height of the video, or None.
        fps: Frames per second, or None.
        vcodec: The video codec, or None.
        acodec: The audio codec, or None.
        audio_channels: The number of audio channels, or None.
        subtitles: ``manual``, ``auto`` or None.
        cover_embedded: Whether the thumbnail is inside the file.
    """

    name: str
    size: int | None
    width: int | None
    height: int | None
    fps: float | None
    vcodec: str | None
    acodec: str | None
    audio_channels: int | None
    subtitles: str | None
    cover_embedded: bool


class VideoDetailsResponse(BaseModel):
    """The answer of ``GET /api/videos/{id}``: everything the details panel shows (R-UI-08).

    Attributes:
        video: The video as a list shows it.
        channel_id: Its channel.
        folder: The channel folder.
        file: The file of a synced video, or None.
        downloaded_at: When the file was completed, or None.
        description: The description from the saved metadata, or None.
        chapters: The chapters from the saved metadata.
        thumbnail_saved: Whether the original thumbnail is in the hidden folder.
        url: The address of the video on YouTube.
    """

    video: Video
    channel_id: str
    folder: str
    file: FileFacts | None
    downloaded_at: int | None
    description: str | None
    chapters: list[ChapterInfo]
    thumbnail_saved: bool
    url: str

    @classmethod
    def of(cls, details: VideoDetails) -> VideoDetailsResponse:
        """Return the wire form of the details of a video."""
        video = details.view.video
        media = details.media
        file = (
            None
            if details.file is None
            else FileFacts(
                name=details.file.name,
                size=video.file_size,
                width=None if media is None else media.width,
                height=video.height if media is None else media.height,
                fps=None if media is None else media.fps,
                vcodec=video.vcodec if media is None else media.vcodec,
                acodec=video.acodec if media is None else media.acodec,
                audio_channels=None if media is None else media.audio_channels,
                subtitles=video.has_subtitles,
                cover_embedded=media is not None
                and any(name.startswith("cover") for name in media.attachments),
            )
        )
        return cls(
            video=Video.of(details.view),
            channel_id=video.channel_id,
            folder=str(details.folder),
            file=file,
            downloaded_at=video.downloaded_at,
            description=details.description,
            chapters=[
                ChapterInfo(start_s=chapter.start_s, title=chapter.title)
                for chapter in details.chapters
            ],
            thumbnail_saved=details.thumbnail_saved,
            url=f"https://www.youtube.com/watch?v={video.id}",
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
        trigger: What the user pressed: the button, the menu, or "Try again". It is
            logged with the check, so the log alone tells why it ran.
    """

    kind: CheckKind = CheckKind.QUICK
    trigger: CheckTrigger = CheckTrigger.API


class CheckAllResponse(BaseModel):
    """The answer of ``POST /api/channels/check-all``.

    Attributes:
        channels: How many channels are being checked.
    """

    channels: int


class FilesToTrashResponse(BaseModel):
    """The answer of ``GET /api/channels/{id}/files-to-trash`` (R-CH-32).

    Attributes:
        files: How many visible files "Delete the files" moves to the Trash.
        size_bytes: How much room they take, the hidden folder of the app included.
    """

    files: int
    size_bytes: int


class RemovedChannelResponse(BaseModel):
    """The answer of ``DELETE /api/channels/{id}`` (R-CH-32).

    Attributes:
        folder: The folder of the channel.
        files_trashed: How many files and folders went to the Trash.
        left: The files, relative to the folder, that macOS refused to move to
            the Trash. Empty when every file went, or when the files were kept.
    """

    folder: str
    files_trashed: int
    left: list[str]


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


class VideoUpdatedEvent(BaseModel):
    """The data of the ``video.updated`` event of ``GET /api/events`` (R-FB-03).

    Attributes:
        channel_id: The channel of the video.
        video: The video as a list shows it now.
    """

    channel_id: str
    video: Video


class JobProgressEvent(BaseModel):
    """The data of the ``job.progress`` event of ``GET /api/events`` (R-QU-04).

    Attributes:
        download: How far the download is.
    """

    download: Download


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
