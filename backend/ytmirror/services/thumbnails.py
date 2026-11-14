"""Caches the pictures of the catalogue: thumbnails of videos and avatars of channels.

Implements R-CH-16 (docs/DECISIONS.md D-067). After a listing the pictures
of a channel are fetched in the background, newest video first, a few at a
time. The interface only ever gets a cached picture: a picture that is not
cached yet is simply missing, and the interface is told when more are there.

Fetching pictures is work the app does by itself, so the pause of the whole
app holds it up (R-ER-05) and it is taken up again when the pause ends.

Tests: backend/tests/unit/services/test_thumbnails.py
"""

import re
import threading
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor

import structlog
from structlog.typing import FilteringBoundLogger

from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.ports.catalogue_repository import CatalogueRepository
from ytmirror.ports.image_cache import ImageCache, ImageKind
from ytmirror.services.channel_views import ChannelViews
from ytmirror.services.youtube_access import YouTubeAccess

_log: FilteringBoundLogger = structlog.get_logger(__name__)

BATCH = 24
"""Pictures are fetched in groups of this size, and the interface is told after each group."""

GIVE_UP_AFTER_FAILED_BATCHES = 2
"""A channel whose pictures fail for this many groups in a row is left for later."""

type _Wanted = tuple[ImageKind, str, str]

_AN_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
"""What the ID of a video or a channel looks like. Anything else has no picture."""


class ThumbnailService:
    """Fills and reads the cache of pictures."""

    def __init__(
        self,
        repository: CatalogueRepository,
        youtube: YouTubeAccess,
        cache: ImageCache,
        views: ChannelViews,
        run_in_background: Callable[[Callable[[], None]], None],
        parallel: int = 4,
    ) -> None:
        """Create the service. Nothing is fetched before ``start`` or ``fill``.

        Args:
            repository: The stored channels and videos.
            youtube: The access to YouTube.
            cache: Where the pictures are kept.
            views: Tells the interface that more pictures are there.
            run_in_background: Runs the fetching without blocking the caller.
            parallel: How many pictures are fetched at the same time.
        """
        self._repository = repository
        self._youtube = youtube
        self._cache = cache
        self._views = views
        self._run_in_background = run_in_background
        self._parallel = parallel
        self._lock = threading.Lock()
        self._waiting: list[tuple[str, bool]] = []
        self._working = False

    def start(self) -> None:
        """Fetch what is missing for every channel, now and whenever a pause of the app ends."""
        self._youtube.when_asking_again(self.fill_all)
        self.fill_all()

    def fill_all(self) -> None:
        """Fetch the missing pictures of every channel."""
        for channel in self._repository.channels():
            self.fill(channel.id)

    def fill(self, channel_id: str, *, renew_avatar: bool = False) -> None:
        """Fetch the missing pictures of one channel in the background.

        Args:
            channel_id: The channel ID.
            renew_avatar: Fetch the avatar again although one is cached: a channel
                can change its avatar, and a full check takes the new one over (R-CH-12).
        """
        with self._lock:
            self._waiting = [entry for entry in self._waiting if entry[0] != channel_id]
            self._waiting.append((channel_id, renew_avatar))
            if self._working:
                return
            self._working = True
        self._run_in_background(self._work)

    def thumbnail(self, video_id: str) -> bytes | None:
        """Return the cached thumbnail of a video, or None.

        Args:
            video_id: The video ID.
        """
        if not _AN_ID.fullmatch(video_id):
            return None
        return self._cache.load(ImageKind.THUMBNAIL, video_id)

    def avatar(self, channel_id: str) -> bytes | None:
        """Return the cached avatar of a channel, or None.

        Args:
            channel_id: The channel ID.
        """
        if not _AN_ID.fullmatch(channel_id):
            return None
        return self._cache.load(ImageKind.AVATAR, channel_id)

    def keep_avatar(self, channel_id: str, picture: bytes) -> None:
        """Cache an avatar that was fetched already, as for the preview of a new channel.

        Args:
            channel_id: The channel ID.
            picture: The bytes of the avatar.
        """
        self._cache.store(ImageKind.AVATAR, channel_id, picture)

    def forget(self, channel_id: str, video_ids: Iterable[str]) -> None:
        """Drop the pictures of a channel that was removed (R-CH-32).

        Args:
            channel_id: The channel ID.
            video_ids: The IDs of its videos.
        """
        with self._lock:
            self._waiting = [entry for entry in self._waiting if entry[0] != channel_id]
        self._cache.remove(ImageKind.AVATAR, [channel_id])
        self._cache.remove(ImageKind.THUMBNAIL, video_ids)

    def _work(self) -> None:
        while True:
            with self._lock:
                if not self._waiting:
                    self._working = False
                    return
                channel_id, renew_avatar = self._waiting.pop(0)
            if not self._fill_channel(channel_id, renew_avatar):
                with self._lock:
                    self._waiting.clear()
                    self._working = False
                return

    def _fill_channel(self, channel_id: str, renew_avatar: bool) -> bool:
        """Fetch what a channel lacks. Returns False when the app pauses and all must wait."""
        wanted = self._wanted(channel_id, renew_avatar)
        stored = failed = failed_batches = 0
        for start in range(0, len(wanted), BATCH):
            batch = wanted[start : start + BATCH]
            with ThreadPoolExecutor(max_workers=self._parallel) as pool:
                outcomes = list(pool.map(self._fetch, batch))
            if ErrorCode.BOT_CHECK in outcomes:
                return False
            fetched = outcomes.count(None)
            stored += fetched
            failed += len(batch) - fetched
            if fetched:
                self._views.more_pictures(channel_id)
            failed_batches = 0 if fetched else failed_batches + 1
            if failed_batches >= GIVE_UP_AFTER_FAILED_BATCHES:
                break
        if wanted:
            log = _log.warning if failed else _log.info
            log(
                "image.cache.finished",
                msg="Pictures of a channel were cached",
                channel_id=channel_id,
                stored=stored,
                failed=failed,
                left=len(wanted) - stored - failed,
            )
        return True

    def _wanted(self, channel_id: str, renew_avatar: bool) -> list[_Wanted]:
        channel = self._repository.channel(channel_id)
        if channel is None:
            return []
        wanted: list[_Wanted] = []
        if channel.avatar_url and (
            renew_avatar or not self._cache.has(ImageKind.AVATAR, channel_id)
        ):
            wanted.append((ImageKind.AVATAR, channel_id, channel.avatar_url))
        wanted.extend(
            (ImageKind.THUMBNAIL, video.id, video.thumbnail_url)
            for video in self._repository.videos(channel_id)
            if video.thumbnail_url and not self._cache.has(ImageKind.THUMBNAIL, video.id)
        )
        return wanted

    def _fetch(self, wanted: _Wanted) -> ErrorCode | None:
        """Fetch and keep one picture. Returns the error code when it failed."""
        kind, item_id, url = wanted
        try:
            self._cache.store(kind, item_id, self._youtube.fetch_image(url))
        except AppError as error:
            return error.code
        return None
