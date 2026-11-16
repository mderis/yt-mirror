"""The services of the catalogue, wired with fakes, for the tests of the services and the API.

Everything is real except the outside world: the database is a migrated
file in a temp folder, YouTube is the fixture adapter with channels a test
writes, and the clock, the folders, the folder dialog and the picture cache
are fakes. Nothing runs in the background by itself: a test says when.
"""

import itertools
import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from tests.fixtures.database import migrated_engine
from tests.fixtures.fakes.app_meta_repository import InMemoryAppMetaRepository
from tests.fixtures.fakes.clock import FakeClock
from tests.fixtures.fakes.file_system import FakeFileSystem
from tests.fixtures.fakes.folder_picker import FakeFolderPicker
from tests.fixtures.fakes.image_cache import InMemoryImageCache
from tests.fixtures.fakes.media_tools import FakeMediaTools
from tests.fixtures.fakes.settings_repository import InMemorySettingsRepository
from ytmirror.adapters.db.catalogue_repository import SqlCatalogueRepository
from ytmirror.adapters.db.job_repository import SqlJobRepository
from ytmirror.adapters.fixture_youtube import FixtureYouTube
from ytmirror.core.channels import (
    ChannelFacts,
    ChannelListing,
    ChannelReference,
    ChannelUpdated,
    CheckKind,
    ListedVideo,
    TaskProgressed,
    YouTubePauseChanged,
)
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.jobs import (
    DownloadCancelledError,
    DownloadProgress,
    DownloadRequest,
    DownloadResult,
    Stage,
    SubtitleKind,
    SubtitlesFailedError,
    VideoUpdated,
)
from ytmirror.core.models import AppEvent
from ytmirror.services.catalogue import CatalogueService
from ytmirror.services.channel_views import ChannelViews
from ytmirror.services.channels import ChannelsService, NewChannel
from ytmirror.services.download_state import DownloadState
from ytmirror.services.downloader import DownloaderService
from ytmirror.services.events import EventBus
from ytmirror.services.settings import SettingsService
from ytmirror.services.state import StateService
from ytmirror.services.thumbnails import ThumbnailService
from ytmirror.services.youtube_access import YouTubeAccess

LISTED_AT = "2026-11-14T06:42:00Z"
type Download = Callable[
    [DownloadRequest, Callable[[DownloadProgress], None], Callable[[], bool]], DownloadResult
]
"""Downloads a video like the gateway: the request, where progress goes, and whether to stop."""

SMALL_ID = "UCsmallsmallsmallsmall01"


def job_id(number: int) -> str:
    """Return a job ID in the shape of a ULID, as the app gives them."""
    return f"01JD{number:022d}"


BIG_ID = "UCbigbigbigbigbigbigbi02"


def channel_file(
    channel_id: str = SMALL_ID,
    *,
    title: str = "Small Channel",
    handle: str = "@small",
    videos: int = 5,
    prefix: str = "sm",
    count: int | dict[str, str] | None = None,
    checks: list[dict[str, Any]] | None = None,
    **more: Any,
) -> dict[str, Any]:
    """Return the description of a fixture channel with generated videos."""
    return {
        "id": channel_id,
        "title": title,
        "handle": handle,
        "listed_at": LISTED_AT,
        "video_count": videos if count is None else count,
        "generate": {"count": videos, "id_prefix": prefix, "title": "Video {number}"},
        "checks": checks or [],
        **more,
    }


def new_video(
    video_id: str, title: str = "A new video", before: str | None = None
) -> dict[str, Any]:
    """Return a video for the ``add`` of a step of a fixture script."""
    video: dict[str, Any] = {
        "id": video_id,
        "title": title,
        "duration_s": 300,
        "point": "2026-11-13",
    }
    if before is not None:
        video["before"] = before
    return video


def log_lines(logs: Sequence[Mapping[str, Any]], event: str) -> list[Mapping[str, Any]]:
    """Return the captured log lines with an event name."""
    return [line for line in logs if line["event"] == event]


class RefusingGateway:
    """Passes everything on to the fake YouTube, and can refuse like the real one.

    Attributes:
        refuse: Kinds of request ("lookup", "listing", "count", "image", "download") with the
            error code to answer them with.
        asked: Every request that reached the gateway, by kind.
    """

    def __init__(self, youtube: FixtureYouTube) -> None:
        """Wrap the fake YouTube."""
        self._youtube = youtube
        self.refuse: dict[str, ErrorCode] = {}
        self.asked: list[str] = []
        self.refuse_listing_after: int | None = None
        self.download_with: Download | None = None
        """A stand-in for the downloads, when a test needs no real video file."""

    def _maybe_refuse(self, kind: str) -> None:
        self.asked.append(kind)
        if kind in self.refuse:
            raise AppError(self.refuse[kind], {"message": f"refused {kind}"})

    def lookup_channel(self, reference: ChannelReference) -> ChannelFacts:
        """Look a channel up, unless lookups are refused."""
        self._maybe_refuse("lookup")
        return self._youtube.lookup_channel(reference)

    def list_channel(self, channel_id: str) -> ChannelListing:
        """Start a listing, unless listings are refused now or part of the way."""
        if self.refuse_listing_after is None:
            self._maybe_refuse("listing")
        else:
            self.asked.append("listing")
        listing = self._youtube.list_channel(channel_id)
        if self.refuse_listing_after is None:
            return listing
        return ChannelListing(listing.facts, self._cut(listing.videos, self.refuse_listing_after))

    def _cut(self, videos: Iterator[ListedVideo], after: int) -> Iterator[ListedVideo]:
        for index, video in enumerate(videos):
            if index == after:
                raise AppError(self.refuse["listing"], {"message": "refused part of the way"})
            yield video

    def preview_video_count(self, channel_id: str) -> int:
        """Return the count, unless counts are refused."""
        self._maybe_refuse("count")
        return self._youtube.preview_video_count(channel_id)

    def fetch_image(self, url: str) -> bytes:
        """Fetch a picture, unless pictures are refused."""
        self._maybe_refuse("image")
        return self._youtube.fetch_image(url)

    def download(
        self,
        request: DownloadRequest,
        on_progress: Callable[[DownloadProgress], None],
        is_cancelled: Callable[[], bool],
    ) -> DownloadResult:
        """Download, unless downloads are refused, with the stand-in when there is one."""
        self._maybe_refuse("download")
        if self.download_with is not None:
            return self.download_with(request, on_progress, is_cancelled)
        return self._youtube.download(request, on_progress, is_cancelled)


def own_file(video_id: str) -> bytes:
    """The content of a fake video file of the app: the fake media tools read its video ID."""
    return f"video:{video_id}".encode()


class FakeDownload:
    """Stands in for a download: writes the files yt-dlp leaves, and calls the hooks.

    Attributes:
        calls: Every request, in order.
        fail: An error to raise instead of downloading, or None.
        subtitles_fail_once: Whether the first download with subtitles fails them.
        cancel_at: A stage at which the test cancels, through ``on_cancel``, or None.
        on_cancel: What the test does at that stage, for example press Cancel.
        published: The upload time the metadata gives.
        release: The release time of a premiere, or None.
        no_thumbnail: Whether YouTube gives no thumbnail.
    """

    def __init__(self, files: FakeFileSystem) -> None:
        """Write into the given fake file system."""
        self._files = files
        self.calls: list[DownloadRequest] = []
        self.fail: Exception | None = None
        self.subtitles_fail_once = False
        self.cancel_at: Stage | None = None
        self.on_cancel: Callable[[], object] = lambda: None
        self.published: int | None = 1_793_379_761
        self.release: int | None = None
        self.no_thumbnail = False
        self.info_json: str | None = None
        """The raw metadata to give, or None for a small valid one."""

    def __call__(
        self,
        request: DownloadRequest,
        on_progress: Callable[[DownloadProgress], None],
        is_cancelled: Callable[[], bool],
    ) -> DownloadResult:
        """Download like the gateway, into the temp folder of the job."""
        self.calls.append(request)
        if self.fail is not None:
            raise self.fail
        for stage in (Stage.VIDEO, Stage.AUDIO, Stage.PROCESSING):
            if stage is self.cancel_at:
                self.on_cancel()
            if is_cancelled():
                raise DownloadCancelledError(f"cancelled at {stage.value}")
            on_progress(DownloadProgress(stage=stage, fraction=1.0, speed_bps=1e6, left_s=0))
        if request.manual_subtitles and self.subtitles_fail_once:
            self.subtitles_fail_once = False
            raise SubtitlesFailedError("the subtitles failed")
        # The file carries its video ID, as the tag of a real download does (R-MD-01).
        self._files.add_files(
            request.work_folder, [f"{request.video_id}.mkv"], data=own_file(request.video_id)
        )
        if not self.no_thumbnail:
            self._files.add_files(
                request.work_folder, [f"{request.video_id}.jpg"], data=b"twelve bytes"
            )
        return DownloadResult(
            file=request.work_folder / f"{request.video_id}.mkv",
            thumbnail=None
            if self.no_thumbnail
            else request.work_folder / f"{request.video_id}.jpg",
            info_json=json.dumps({"id": request.video_id})
            if self.info_json is None
            else self.info_json,
            title="Title at YouTube",
            description="A description.",
            duration_s=2,
            release_time=self.release,
            upload_time=self.published,
            subtitles=SubtitleKind.MANUAL if request.manual_subtitles else None,
        )


class World:
    """The catalogue services with fakes around them.

    Attributes:
        events: Every event that was published, in order.
        background: Work that was handed to the background and did not run yet.
        later: Work that was scheduled for later, with its delay in seconds.
    """

    def __init__(
        self, folder: Path, *channels: dict[str, Any], bus: EventBus | None = None
    ) -> None:
        """Build the services on a new database and a fake YouTube with the given channels.

        Args:
            folder: A temp folder of the test.
            channels: The channels of the fake YouTube. Default: one small channel.
            bus: The event bus to publish on. Default: a new one.
        """
        world_dir = folder / "youtube"
        world_dir.mkdir()
        for index, channel in enumerate(channels or (channel_file(),)):
            (world_dir / f"{index}.json").write_text(json.dumps(channel), encoding="utf-8")
        self.library = folder / "library"
        self.clock = FakeClock()
        self.slept: list[float] = []
        self.fixture = FixtureYouTube(world_dir, sleep=self.slept.append)
        self.gateway = RefusingGateway(self.fixture)
        self.bus = bus if bus is not None else EventBus()
        self.events: list[AppEvent] = []
        self.bus.subscribe(lambda event: self.events.append(event) if event is not None else None)
        self.background: list[Callable[[], None]] = []
        self.later: list[tuple[float, Callable[[], None]]] = []
        self.files = FakeFileSystem()
        self.media = FakeMediaTools(self.files)
        self.close_wait_s = 30.0
        """How long a removal waits for the downloads of its channel."""
        self.stopped_job_tools: list[Path] = []
        """The temp folders of the jobs whose ffmpeg a cancel stopped."""
        self.picker = FakeFolderPicker()
        self.cache = InMemoryImageCache()
        self.meta = InMemoryAppMetaRepository()
        self.settings_repository = InMemorySettingsRepository()
        engine = migrated_engine(folder)
        self.repository = SqlCatalogueRepository(engine, self.clock)
        self.jobs = SqlJobRepository(engine, self.clock)
        self.settings = SettingsService(self.settings_repository, self.library)
        self.youtube = YouTubeAccess(
            self.gateway, self.clock, self.bus, lambda delay, work: self.later.append((delay, work))
        )
        self.downloads = DownloadState()
        self.views = ChannelViews(
            self.repository,
            self.settings,
            self.clock,
            self.bus,
            youtube_paused=lambda: self.youtube.pause() is not None,
            downloads=self.downloads,
        )
        self.waited: list[float] = []
        self.during_wait: Callable[[], None] | None = None
        self.thumbnails = ThumbnailService(
            self.repository,
            self.youtube,
            self.cache,
            self.views,
            self.background.append,
            parallel=1,
        )
        self.catalogue = CatalogueService(
            self.repository,
            self.youtube,
            self.views,
            self.clock,
            self.background.append,
            after_check=self._after_check,
            choose_delay=lambda least, most: (least + most) / 2,
            wait=self._wait,
        )
        self.channels = ChannelsService(
            self.repository,
            self.youtube,
            self.files,
            self.picker,
            self.settings,
            self.views,
            self.catalogue,
            self.thumbnails,
            self.clock,
            self.background.append,
            close_downloads=lambda channel_id: self.downloader.channel_closed(
                channel_id, self.close_wait_s
            ),
            media=self.media,
        )
        self.state = StateService(
            self.views, self.settings, self.files, self.picker, self.meta, self.youtube
        )
        self.stop_tools: Callable[[], None] = lambda: None
        """What stopping the tools at quit does in a test."""
        self.job_numbers = itertools.count(1)
        self.download = FakeDownload(self.files)
        self.gateway.download_with = self.download
        self.downloader = DownloaderService(
            repository=self.repository,
            jobs=self.jobs,
            youtube=self.youtube,
            files=self.files,
            media=self.media,
            settings=self.settings,
            views=self.views,
            state=self.downloads,
            events=self.bus,
            clock=self.clock,
            new_job_id=lambda: job_id(next(self.job_numbers)),
            job_logs=folder / "logs" / "jobs",
            run_in_background=self.background.append,
            stop_tools=lambda: self.stop_tools(),
            stop_job_tools=self.stopped_job_tools.append,
        )

    def _after_check(self, channel_id: str, kind: CheckKind) -> None:
        """What the container does after a check: the pictures and the channel file."""
        self.thumbnails.fill(channel_id, renew_avatar=kind is CheckKind.FULL)
        self.channels.write_channel_file(channel_id)

    def download_all(self) -> None:
        """Let every waiting download run, one after another."""
        while self.downloader.work_once():
            pass

    def video_updates(self) -> list[VideoUpdated]:
        """Return the video updates that were published."""
        return [event for event in self.events if isinstance(event, VideoUpdated)]

    def statuses(self, video_id: str) -> list[tuple[str, str, str]]:
        """Return the recorded status changes of a video: from, to and why."""
        return [
            (event.from_status, event.to_status, event.reason)
            for event in self.jobs.events(video_id)
        ]

    def at_progress(self, done: int, action: Callable[[], object]) -> None:
        """Run an action once, when a long check has read so many videos."""
        ran: list[int] = []

        def listener(event: AppEvent | None) -> None:
            if isinstance(event, TaskProgressed) and event.progress.done == done and not ran:
                ran.append(done)
                action()

        self.bus.subscribe(listener)

    def now(self) -> int:
        """Return the time of the fake clock as seconds since the epoch."""
        return int(self.clock.now().timestamp())

    def _wait(self, seconds: float) -> None:
        """Stand in for the wait between two channels: note it, and let a test act meanwhile."""
        self.waited.append(seconds)
        if self.during_wait is not None:
            self.during_wait()

    def run_background(self) -> None:
        """Run everything that was handed to the background, except the worker of the checks."""
        while self.background:
            self.background.pop(0)()

    def work(self) -> None:
        """Let every check that waits run, and everything in the background with it."""
        self.run_background()
        while self.catalogue.work_once():
            self.run_background()

    def add(self, handle: str = "@small", **choices: Any) -> str:
        """Look a channel up and add it, without running its first listing. Returns its ID."""
        looked_up = self.channels.lookup(handle)
        self.run_background()
        self.channels.add(NewChannel(channel_id=looked_up.facts.channel_id, **choices))
        return looked_up.facts.channel_id

    def add_and_list(self, handle: str = "@small", **choices: Any) -> str:
        """Add a channel and let its first listing run. Returns its ID."""
        channel_id = self.add(handle, **choices)
        self.work()
        return channel_id

    def check(self, channel_id: str, kind: CheckKind = CheckKind.QUICK) -> None:
        """Ask for a check and let it run."""
        self.catalogue.request_check(channel_id, kind)
        self.work()

    def titles(self, channel_id: str) -> list[str]:
        """Return the titles of the catalogue of a channel, in channel order."""
        return [video.title for video in self.repository.videos(channel_id)]

    def ids(self, channel_id: str) -> list[str]:
        """Return the video IDs of the catalogue of a channel, in channel order."""
        return [video.id for video in self.repository.videos(channel_id)]

    def updates(self) -> list[ChannelUpdated]:
        """Return the channel updates that were published."""
        return [event for event in self.events if isinstance(event, ChannelUpdated)]

    def progress(self) -> list[TaskProgressed]:
        """Return the progress events that were published."""
        return [event for event in self.events if isinstance(event, TaskProgressed)]

    def pauses(self) -> list[YouTubePauseChanged]:
        """Return the changes of the pause that were published."""
        return [event for event in self.events if isinstance(event, YouTubePauseChanged)]
