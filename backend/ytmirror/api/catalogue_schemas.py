"""Request and response models of the HTTP API for channels and their catalogue.

The OpenAPI schema generated from these models is the contract with the
frontend (docs/ARCHITECTURE.md section 8). After a change here, run
``npm --prefix frontend run gen:api``. This module must not contain logic:
a model only says how a value of the app looks on the wire.

Tests: backend/tests/api/test_channels.py, test_state.py and test_videos.py
"""

from pydantic import BaseModel

from ytmirror.core.auto_mirror import AutoMirrorAnswer
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
from ytmirror.core.exact_dates import (
    DateShown,
    DateState,
    ExactDatesProgress,
    KeyState,
    KeyStatus,
)
from ytmirror.core.jobs import JobProgress, Stage
from ytmirror.core.progress import PartKind, PartProgress
from ytmirror.core.queue import (
    NO_QUEUE,
    FailedEntry,
    QueueEntry,
    QueueSummary,
    QueueView,
)
from ytmirror.services.channels import ChannelLookup, ChosenFolder, KeptFile, KeptReason
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


class AutoMirrorQuestionInfo(BaseModel):
    """Auto-mirror waits for the user before a large start (R-MI-02, D-095).

    Attributes:
        count: How many videos it would download.
        estimated_bytes: About how much room they take.
    """

    count: int
    estimated_bytes: int


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
        exact_dates: While dates of the channel wait to be looked up, how far they are
            ("Exact dates X of Y"), the time left and the key offer. Otherwise None.
        key_notice: Whether a saved API key is not working while dates of the channel
            wait (R-DT-12): "the API key is not working, using the slow way".
        waiting_until: When the exact dates go on, while they wait for YouTube.
        retry_at: When a failed check is tried again by itself (R-CH-25), or None.
        auto_mirror_question: What auto-mirror would start and waits for an answer
            about (D-095), or None.
        missing_held: How many missing files auto-mirror waits for an answer about
            (D-092), or None.
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
    exact_dates: ExactDates | None = None
    key_notice: bool = False
    waiting_until: int | None = None
    retry_at: int | None = None
    auto_mirror_question: AutoMirrorQuestionInfo | None = None
    missing_held: int | None = None

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
            exact_dates=ExactDates.of(view.exact_dates),
            key_notice=view.key_notice,
            waiting_until=view.waiting_until,
            retry_at=view.retry_at,
            auto_mirror_question=None
            if view.auto_mirror_question is None
            else AutoMirrorQuestionInfo(
                count=view.auto_mirror_question[0],
                estimated_bytes=view.auto_mirror_question[1],
            ),
            missing_held=view.missing_held,
        )


class ExactDates(BaseModel):
    """How far the exact dates of a channel are (R-FB-01, R-DT-14, R-DT-15).

    Attributes:
        done: How many dates were found since the channel last had none waiting.
        total: How many there are in all since then.
        left_s: The measured time left, or None while it is not known.
        offer_key: Whether the channel offers the key.
    """

    done: int
    total: int
    left_s: int | None
    offer_key: bool

    @classmethod
    def of(cls, progress: ExactDatesProgress | None) -> ExactDates | None:
        """Return the wire form of the progress, or None."""
        if progress is None:
            return None
        return cls(
            done=progress.done,
            total=progress.total,
            left_s=progress.left_s,
            offer_key=progress.offer_key,
        )


class DateInfo(BaseModel):
    """What an approximate date shows (R-DT-13).

    Attributes:
        state: Waiting, updating or unavailable.
        reason: Why it is unavailable, or None.
        retry_at: When it is tried again, or None.
    """

    state: DateState
    reason: ErrorCode | None
    retry_at: int | None

    @classmethod
    def of(cls, shown: DateShown | None) -> DateInfo | None:
        """Return the wire form, or None for an exact date."""
        if shown is None:
            return None
        return cls(state=shown.state, reason=shown.reason, retry_at=shown.retry_at)


class ApiKey(BaseModel):
    """How the optional YouTube API key stands (R-DT-12). Never the key itself.

    Attributes:
        status: None saved, saved, or saved but unreadable, invalid or out of quota.
        until: Until when the app does without a failing key, or None.
    """

    status: KeyStatus
    until: int | None

    @classmethod
    def of(cls, key: KeyState) -> ApiKey:
        """Return the wire form of the key state."""
        return cls(status=key.status, until=key.until)


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
        fraction: How much of the whole video is done, its streams together, from 0
            to 1. None while it is processed, or when a size is not known.
        speed_bps: Bytes per second, or None.
        left_s: Seconds left of the download, or None.
        height: The height being downloaded, or None.
        downloaded_bytes: How many bytes arrived, all parts together, or None.
        total_bytes: How many bytes all parts have, real or estimated, or None.
        parts: Each part: video, audio, subtitles, thumbnail (R-QU-04).
        again: Whether this is a second download without subtitles (R-MD-04).
    """

    job_id: str
    video_id: str
    channel_id: str
    stage: Stage
    fraction: float | None
    speed_bps: float | None
    left_s: int | None
    height: int | None
    downloaded_bytes: int | None
    total_bytes: int | None = None
    parts: list[DownloadPart] = []
    again: bool = False

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
            downloaded_bytes=progress.downloaded_bytes,
            total_bytes=progress.total_bytes,
            parts=[DownloadPart.of(part) for part in progress.parts],
            again=progress.again,
        )


class DownloadPart(BaseModel):
    """One part of a running download, for the details panel (R-QU-04).

    Attributes:
        kind: Video, audio, subtitles or thumbnail.
        size: Its size in bytes, real or estimated.
        done: How many of its bytes arrived.
        estimated: Whether the size is an estimate.
        finished: Whether it is complete.
    """

    kind: PartKind
    size: int
    done: int
    estimated: bool
    finished: bool

    @classmethod
    def of(cls, part: PartProgress) -> DownloadPart:
        """Return the wire form of a part."""
        return cls(
            kind=part.kind,
            size=part.size,
            done=part.done,
            estimated=part.estimated,
            finished=part.finished,
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
        date: What an approximate date shows (R-DT-13), or None for an exact date.
        paced_until: When an automatic download that waits for room in the lookup
            budget may start, or None (R-DT-06, D-090).
        retry_at: When a download that failed in a way that passes is tried again by
            itself, or None (R-QU-07).
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
    date: DateInfo | None = None
    paced_until: int | None = None
    retry_at: int | None = None

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
            date=DateInfo.of(view.date),
            paced_until=view.paced_until,
            retry_at=view.retry_at,
        )


class MirrorRequest(BaseModel):
    """The body of ``POST /api/videos/mirror`` (R-MI-01).

    Attributes:
        ids: The videos to put in line, in this order.
        first: Whether they go to the top of the line ("Mirror first", R-QU-02).
    """

    ids: list[str]
    first: bool = False


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


class DiskGuard(BaseModel):
    """The queue is paused because a disk has too little free space (R-QU-10).

    Attributes:
        disk: The name of the volume.
        free_bytes: Its free space when the guard saw it.
        limit_bytes: The free space below which the queue pauses.
    """

    disk: str
    free_bytes: int
    limit_bytes: int


class Queue(BaseModel):
    """How the queue stands, for the queue bar (R-QU-01, R-QU-02).

    Attributes:
        downloading: How many downloads run now.
        waiting: How many wait in line.
        failed: How many videos failed (R-QU-08).
        paused: Whether the user paused all downloads.
        places: How many downloads may run at once.
        speed_limit_mbps: The limit of all downloads together, 0 for none (R-QU-03).
        disk_guard: The pause of the disk space guard, or None (R-QU-10).
        folders_away: The channels whose folder cannot be reached (R-QU-11).
    """

    downloading: int
    waiting: int
    failed: int
    paused: bool
    places: int
    speed_limit_mbps: int = 0
    disk_guard: DiskGuard | None = None
    folders_away: list[str] = []

    @classmethod
    def of(cls, summary: QueueSummary) -> Queue:
        """Return the wire form of a summary of the queue."""
        guard = summary.disk_guard
        return cls(
            downloading=summary.downloading,
            waiting=summary.waiting,
            failed=summary.failed,
            paused=summary.paused,
            places=summary.places,
            speed_limit_mbps=summary.speed_limit_mbps,
            disk_guard=None
            if guard is None
            else DiskGuard(
                disk=guard.disk, free_bytes=guard.free_bytes, limit_bytes=guard.limit_bytes
            ),
            folders_away=list(summary.folders_away),
        )


class StateResponse(BaseModel):
    """The answer of ``GET /api/state``: the app as the window draws it.

    Attributes:
        channels: Every channel, in the order of the sidebar.
        open_channel_id: The channel that was open last, or None (R-UI-02).
        library_folder: The library folder as a path.
        disk: The disk the library is on.
        can_choose_folder: Whether the folder dialog of macOS can be shown.
        youtube_pause: The pause of the whole app, or None (R-ER-05).
        api_key: How the optional API key stands (R-DT-12).
        checking_all: How far a check of all channels is ("Checking channels: 3 of 5"),
            or None (R-CH-20).
        queue: How the queue of downloads stands (R-QU-02).
    """

    channels: list[Channel]
    open_channel_id: str | None
    library_folder: str
    disk: DiskSpace
    can_choose_folder: bool
    youtube_pause: Pause | None
    api_key: ApiKey
    checking_all: Mirroring | None = None
    queue: Queue = Queue.of(NO_QUEUE)

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
            api_key=ApiKey.of(state.api_key),
            checking_all=None
            if state.checking_all is None
            else Mirroring(done=state.checking_all[0], total=state.checking_all[1]),
            queue=Queue.of(state.queue),
        )


class QueueItem(BaseModel):
    """One download that waits or runs, as the downloads panel shows it (R-QU-02).

    Attributes:
        job_id: The job.
        video_id: The video.
        channel_id: Its channel.
        channel_title: The name of the channel.
        title: The title of the video.
        duration_s: Its length in seconds, or None.
        quality: The quality it is downloaded in.
        by_hand: Whether the user started it by hand (R-DT-06, D-090).
        download: How far it is, when it runs and reported already, else None.
        paced_until: When it may start, while it waits for room in the lookup
            budget (D-090), else None.
    """

    job_id: str
    video_id: str
    channel_id: str
    channel_title: str
    title: str
    duration_s: int | None
    quality: Quality
    by_hand: bool
    download: Download | None = None
    paced_until: int | None = None

    @classmethod
    def of(cls, entry: QueueEntry) -> QueueItem:
        """Return the wire form of a queue entry."""
        return cls(
            job_id=entry.job.id,
            video_id=entry.video.id,
            channel_id=entry.video.channel_id,
            channel_title=entry.channel_title,
            title=entry.video.title,
            duration_s=entry.video.duration_s,
            quality=entry.job.quality,
            by_hand=entry.job.by_hand,
            download=None if entry.progress is None else Download.of(entry.progress),
            paced_until=entry.paced_until,
        )


class FailedItem(BaseModel):
    """One failed video, as the downloads panel shows it (R-QU-08).

    Attributes:
        video_id: The video.
        channel_id: Its channel.
        channel_title: The name of the channel.
        title: The title of the video.
        error_code: Why it failed, or None.
        attempts: How many automatic attempts were made since it last succeeded.
        gone: Whether YouTube no longer has it: then it offers no Retry (R-CH-14).
    """

    video_id: str
    channel_id: str
    channel_title: str
    title: str
    error_code: ErrorCode | None
    attempts: int
    gone: bool

    @classmethod
    def of(cls, entry: FailedEntry) -> FailedItem:
        """Return the wire form of a failed video."""
        return cls(
            video_id=entry.video.id,
            channel_id=entry.video.channel_id,
            channel_title=entry.channel_title,
            title=entry.video.title,
            error_code=entry.video.last_error_code,
            attempts=entry.video.attempts,
            gone=entry.video.gone,
        )


class QueueResponse(BaseModel):
    """The answer of ``GET /api/queue``: the whole queue (R-QU-02).

    Attributes:
        queue: How it stands.
        running: The downloads that run.
        waiting: The downloads that wait, in their order.
        failed: The failed videos, newest failure first.
    """

    queue: Queue
    running: list[QueueItem]
    waiting: list[QueueItem]
    failed: list[FailedItem]

    @classmethod
    def of(cls, view: QueueView) -> QueueResponse:
        """Return the wire form of the queue."""
        return cls(
            queue=Queue.of(view.summary),
            running=[QueueItem.of(entry) for entry in view.running],
            waiting=[QueueItem.of(entry) for entry in view.waiting],
            failed=[FailedItem.of(entry) for entry in view.failed],
        )


class ReorderRequest(BaseModel):
    """The body of ``POST /api/queue/reorder`` (R-QU-02).

    Attributes:
        job_ids: The waiting jobs in the order the user wants.
    """

    job_ids: list[str]


class SpeedLimitRequest(BaseModel):
    """The body of ``POST /api/queue/speed-limit`` (R-QU-03).

    Attributes:
        mbps: The limit of all downloads together in MB/s: 0 (unlimited), 5, 2 or 1.
    """

    mbps: int


class TryFolderResponse(BaseModel):
    """The answer of ``POST /api/queue/folders/{channel_id}/try-again`` (R-QU-11).

    Attributes:
        available: Whether the folder can be reached now: then its downloads go on.
    """

    available: bool


class ClearWaitingResponse(BaseModel):
    """The answer of ``POST /api/queue/clear-waiting`` (R-QU-02).

    Attributes:
        removed: How many waiting downloads were removed.
    """

    removed: int


class QueueUpdatedEvent(BaseModel):
    """The data of the event ``queue.updated``: the queue changed (R-FB-03).

    Attributes:
        queue: How it stands now.
    """

    queue: Queue


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


class KeptFileResponse(BaseModel):
    """A file that "Delete the files" left in the folder, and why (R-CH-32).

    Attributes:
        file: The path, relative to the channel folder.
        reason: ``trash_refused`` (macOS refused), ``another_video`` (another
            video is inside), ``not_checked`` (the video inside could not be
            read) or ``outside_folder`` (it leads out of the folder).
    """

    file: str
    reason: KeptReason

    @classmethod
    def of(cls, kept: KeptFile) -> KeptFileResponse:
        """Return the wire form of a kept file."""
        return cls(file=kept.file, reason=kept.reason)


class RemovedChannelResponse(BaseModel):
    """The answer of ``DELETE /api/channels/{id}`` (R-CH-32).

    Attributes:
        folder: The folder of the channel.
        files_trashed: How many files and folders went to the Trash.
        left: Every file that should have gone to the Trash and stayed, with
            its reason. Empty when every file went, or when the files were kept.
    """

    folder: str
    files_trashed: int
    left: list[KeptFileResponse]


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


class ApiKeyChangedEvent(BaseModel):
    """The data of the ``apikey.changed`` event of ``GET /api/events``.

    Attributes:
        api_key: How the key stands now (R-DT-12).
    """

    api_key: ApiKey


class SaveApiKeyRequest(BaseModel):
    """The body of ``PUT /api/settings/api-key``.

    Attributes:
        key: The key as the user pasted it. Never logged or stored outside its file.
    """

    key: str


class TestApiKeyRequest(BaseModel):
    """The body of ``POST /api/settings/api-key/test``.

    Attributes:
        key: The key to test, or None for the saved key.
    """

    key: str | None = None


class TestApiKeyResponse(BaseModel):
    """The answer of "Test key" (R-DT-12).

    Attributes:
        works: Whether the YouTube API answered with the key.
        error_code: Why not, or None.
        api_key: How the saved key stands now.
    """

    works: bool
    error_code: ErrorCode | None
    api_key: ApiKey


class ChecksProgressEvent(BaseModel):
    """The data of the ``checks.progress`` event of ``GET /api/events``.

    Attributes:
        checking_all: How many checks of a check of all channels ended, and how many
            there are, or None when it ended (R-CH-20: "Checking channels: 3 of 5").
    """

    checking_all: Mirroring | None


class RepairDatesResponse(BaseModel):
    """The answer of ``POST /api/channels/{channel_id}/repair-dates`` (R-DT-09).

    Attributes:
        checked: How many synced files were compared.
        repaired: How many had other dates and were set again.
        failed: How many could not be set or did not read back.
    """

    checked: int
    repaired: int
    failed: int


class AutoMirrorRequest(BaseModel):
    """The body of ``PUT /api/channels/{id}/auto-mirror`` (R-MI-02).

    Attributes:
        on: Whether auto-mirror is on.
    """

    on: bool


class AutoMirrorAnswerRequest(BaseModel):
    """The body of ``POST /api/channels/{id}/auto-mirror/answer`` (D-095).

    Attributes:
        answer: Mirror all, only new videos from now on, or turn auto-mirror off.
    """

    answer: AutoMirrorAnswer
