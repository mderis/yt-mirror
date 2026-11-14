"""The services of the catalogue, wired with fakes, for the tests of the services and the API.

Everything is real except the outside world: the database is a migrated
file in a temp folder, YouTube is the fixture adapter with channels a test
writes, and the clock, the folders, the folder dialog and the picture cache
are fakes. Nothing runs in the background by itself: a test says when.
"""

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
from tests.fixtures.fakes.settings_repository import InMemorySettingsRepository
from ytmirror.adapters.db.catalogue_repository import SqlCatalogueRepository
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
from ytmirror.core.models import AppEvent
from ytmirror.services.catalogue import CatalogueService
from ytmirror.services.channel_views import ChannelViews
from ytmirror.services.channels import ChannelsService, NewChannel
from ytmirror.services.events import EventBus
from ytmirror.services.settings import SettingsService
from ytmirror.services.state import StateService
from ytmirror.services.thumbnails import ThumbnailService
from ytmirror.services.youtube_access import YouTubeAccess

LISTED_AT = "2026-11-14T06:42:00Z"
SMALL_ID = "UCsmallsmallsmallsmall01"
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
        refuse: Kinds of request ("lookup", "listing", "count", "image") with the
            error code to answer them with.
        asked: Every request that reached the gateway, by kind.
    """

    def __init__(self, youtube: FixtureYouTube) -> None:
        """Wrap the fake YouTube."""
        self._youtube = youtube
        self.refuse: dict[str, ErrorCode] = {}
        self.asked: list[str] = []
        self.refuse_listing_after: int | None = None

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


class World:
    """The catalogue services with fakes around them.

    Attributes:
        events: Every event that was published, in order.
        background: Work that was handed to the background and did not run yet.
        later: Work that was scheduled for later, with its delay in seconds.
    """

    def __init__(self, folder: Path, *channels: dict[str, Any]) -> None:
        """Build the services on a new database and a fake YouTube with the given channels."""
        world_dir = folder / "youtube"
        world_dir.mkdir()
        for index, channel in enumerate(channels or (channel_file(),)):
            (world_dir / f"{index}.json").write_text(json.dumps(channel), encoding="utf-8")
        self.library = folder / "library"
        self.clock = FakeClock()
        self.fixture = FixtureYouTube(world_dir)
        self.gateway = RefusingGateway(self.fixture)
        self.bus = EventBus()
        self.events: list[AppEvent] = []
        self.bus.subscribe(lambda event: self.events.append(event) if event is not None else None)
        self.background: list[Callable[[], None]] = []
        self.later: list[tuple[float, Callable[[], None]]] = []
        self.files = FakeFileSystem()
        self.picker = FakeFolderPicker()
        self.cache = InMemoryImageCache()
        self.meta = InMemoryAppMetaRepository()
        self.settings_repository = InMemorySettingsRepository()
        self.repository = SqlCatalogueRepository(migrated_engine(folder), self.clock)
        self.settings = SettingsService(self.settings_repository, self.library)
        self.youtube = YouTubeAccess(
            self.gateway, self.clock, self.bus, lambda delay, work: self.later.append((delay, work))
        )
        self.views = ChannelViews(self.repository, self.settings, self.clock, self.bus)
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
            after_check=lambda channel_id, kind: self.thumbnails.fill(
                channel_id, renew_avatar=kind is CheckKind.FULL
            ),
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
        )
        self.state = StateService(
            self.views, self.settings, self.files, self.picker, self.meta, self.youtube
        )

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
