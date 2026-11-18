"""Auto-mirror: the videos of a channel are queued by themselves (R-MI-02 to R-MI-06).

After every check, at the start of the app, when auto-mirror is turned on and
when an exact date that a decision waited for arrives, the plan of
``core/auto_mirror.py`` is carried out: new videos are queued as automatic
downloads, which wait for room in the lookup budget (D-090); videos whose
approximate date cannot decide the date limit get their exact date first
(R-MI-03); a few missing files are downloaded again, more are asked about
(D-092); a large start is asked about first (D-095). "Mirror everything
missing" queues every video without a file, by hand (R-MI-04).

What waits for an answer is kept in memory (``AutoMirrorState``) and shown
with the channel; a restart finds it again from the stored channel.

Tests: backend/tests/unit/services/test_auto_mirror.py
"""

import threading
from collections.abc import Callable, Sequence

import structlog
from structlog.typing import FilteringBoundLogger

from ytmirror.core.auto_mirror import (
    AUTO_MIRROR_ASK_ABOVE,
    MISSING_AGAIN_AT_MOST,
    AutoMirrorAnswer,
    AutoMirrorQuestion,
    auto_plan,
    estimated_bytes,
    missing_count,
    missing_videos,
    question_count,
)
from ytmirror.core.channels import Channel, Quality, VideoStatus
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.jobs import ACTIVE_STATES, Job
from ytmirror.core.quality import effective_quality
from ytmirror.ports.catalogue_repository import CatalogueRepository
from ytmirror.ports.clock import Clock
from ytmirror.ports.job_repository import JobRepository
from ytmirror.services.auto_mirror_state import AutoMirrorState
from ytmirror.services.channel_views import ChannelViews
from ytmirror.services.downloader import DownloaderService
from ytmirror.services.settings import SettingsService

_log: FilteringBoundLogger = structlog.get_logger(__name__)


class AutoMirrorService:
    """Queues the videos of channels with auto-mirror on, and asks when it should."""

    def __init__(
        self,
        *,
        repository: CatalogueRepository,
        jobs: JobRepository,
        downloader: DownloaderService,
        views: ChannelViews,
        settings: SettingsService,
        clock: Clock,
        state: AutoMirrorState,
        prioritize: Callable[[Sequence[str]], None] = lambda _video_ids: None,
    ) -> None:
        """Create the service.

        Args:
            repository: The stored channels and videos.
            jobs: The stored jobs: what waits or runs already.
            downloader: Puts videos in line.
            views: Publishes a channel when what it waits for changed.
            settings: The default quality, for the estimate of a large start.
            clock: The source of time.
            state: What waits for the user, shared with the views.
            prioritize: Puts videos at the front of the exact-date fetch (R-MI-03).
        """
        self._repository = repository
        self._jobs = jobs
        self._downloader = downloader
        self._views = views
        self._settings = settings
        self._clock = clock
        self._state = state
        self._prioritize = prioritize
        self._lock = threading.Lock()

    def run_all(self) -> None:
        """Carry out auto-mirror for every channel, as at the start of the app."""
        for channel in self._repository.channels():
            self.run(channel.id)

    def run(self, channel_id: str) -> None:
        """Carry out auto-mirror for a channel now (R-MI-02). A failure is logged.

        Args:
            channel_id: The channel.
        """
        try:
            with self._lock:
                self._run(channel_id)
        except Exception:  # noqa: BLE001  (auto-mirror never fails a check)
            _log.error(
                "automirror.failed",
                msg="Auto-mirror could not look at a channel",
                channel_id=channel_id,
                error_code=ErrorCode.INTERNAL.value,
                exc_info=True,
            )

    def set_auto_mirror(self, channel_id: str, *, on: bool) -> None:
        """Turn auto-mirror of a channel on or off (R-MI-02).

        Turned on, it asks first when it would start more than a few downloads (D-095).

        Args:
            channel_id: The channel.
            on: Whether it is on now.

        Raises:
            AppError: ``NOT_FOUND`` for an unknown channel.
        """
        channel = self._known(channel_id)
        if channel.auto_mirror != on:
            self._repository.update_channel(channel_id, auto_mirror=on, auto_mirror_asked=not on)
            _log.info(
                "automirror.turned_on" if on else "automirror.turned_off",
                msg="Auto-mirror turned on" if on else "Auto-mirror turned off",
                channel_id=channel_id,
            )
        if on:
            self.run(channel_id)
        else:
            self._state.set(channel_id, None, None)
        self._views.publish(channel_id)

    def answer(self, channel_id: str, answer: AutoMirrorAnswer) -> None:
        """Take the answer to the question before a large start (D-095).

        Args:
            channel_id: The channel.
            answer: Mirror all, only new videos from now on (the date limit becomes
                today), or turn auto-mirror off.

        Raises:
            AppError: ``NOT_FOUND`` for an unknown channel.
        """
        self._known(channel_id)
        if answer is AutoMirrorAnswer.TURN_OFF:
            self._repository.update_channel(channel_id, auto_mirror=False, auto_mirror_asked=True)
        elif answer is AutoMirrorAnswer.ONLY_NEW:
            self._repository.update_channel(
                channel_id, mirror_after=self._start_of_today(), auto_mirror_asked=True
            )
        else:
            self._repository.update_channel(channel_id, auto_mirror_asked=True)
        _log.info("automirror.answered", msg="Auto-mirror got its answer", answer=answer.value)
        self._state.set(channel_id, None, None)
        self.run(channel_id)
        self._views.publish(channel_id)

    def mirror_missing(self, channel_id: str) -> list[Job]:
        """Queue every video of a channel without a file, once, by hand (R-MI-04).

        Auto-mirror is not turned on, and its date limit does not apply.

        Args:
            channel_id: The channel.

        Returns:
            The jobs that were put in line.

        Raises:
            AppError: ``NOT_FOUND`` for an unknown channel.
        """
        self._known(channel_id)
        videos = missing_videos(self._repository.videos(channel_id), self._busy())
        jobs = self._downloader.mirror([video.id for video in videos], failed_too=True)
        if self._state.set(channel_id, self._state.question(channel_id), None):
            self._views.publish(channel_id)
        return jobs

    def mirror_them_again(self, channel_id: str) -> list[Job]:
        """Queue the missing files of a channel again, and nothing else (R-MI-06, D-092).

        "Mirror them again" of the banner of many missing files: an action by hand,
        whose first 20 jobs start by hand (D-090). Videos that were never mirrored
        are left alone.

        Args:
            channel_id: The channel.

        Returns:
            The jobs that were put in line.

        Raises:
            AppError: ``NOT_FOUND`` for an unknown channel.
        """
        self._known(channel_id)
        busy = self._busy()
        ids = [
            video.id
            for video in self._repository.videos(channel_id)
            if video.status is VideoStatus.FILE_MISSING
            and not video.excluded
            and not video.gone
            and video.id not in busy
        ]
        jobs = self._downloader.mirror(ids)
        if self._state.set(channel_id, self._state.question(channel_id), None):
            self._views.publish(channel_id)
        return jobs

    def leave_missing(self, channel_id: str) -> None:
        """Leave the missing files of a channel missing, until more are missing (D-092).

        Args:
            channel_id: The channel.

        Raises:
            AppError: ``NOT_FOUND`` for an unknown channel.
        """
        self._known(channel_id)
        held = self._state.missing_held(channel_id)
        if held is not None:
            self._repository.update_channel(channel_id, missing_left=held)
        self._state.set(channel_id, self._state.question(channel_id), None)
        self._views.publish(channel_id)

    def _run(self, channel_id: str) -> None:
        channel = self._repository.channel(channel_id)
        if channel is None or channel.first_listed_at is None:
            # Nothing is known before the first listing: nothing is counted, asked or
            # queued. The listing's end runs auto-mirror again (D-095).
            self._state.set(channel_id, None, None)
            return
        now = int(self._clock.now().timestamp())
        videos = self._repository.videos(channel_id)
        plan = auto_plan(channel, videos, self._busy(), now)
        question: AutoMirrorQuestion | None = None
        held: int | None = None
        to_queue = list(plan.new)
        missing = list(plan.missing)
        decide = list(plan.decide_first)
        if channel.auto_mirror and not channel.paused and not channel.auto_mirror_asked:
            count = question_count(plan)
            if count > AUTO_MIRROR_ASK_ABOVE:
                # A large start is never silent: the user is asked first (D-095). Until
                # the answer, nothing starts, not even the lookups of undecided dates.
                question = AutoMirrorQuestion(
                    count=count,
                    estimated_bytes=estimated_bytes(
                        [*to_queue, *missing, *decide], self._height(channel)
                    ),
                )
                to_queue, missing, decide = [], [], []
            else:
                self._repository.update_channel(channel_id, auto_mirror_asked=True)
        if question is None:
            total = missing_count(videos)
            if total > MISSING_AGAIN_AT_MOST:
                if channel.missing_left is None or total > channel.missing_left:
                    held = total
                    _log.info(
                        "queue.missing_held",
                        msg="Many files of a channel are missing. Auto-mirror asks first",
                        channel_id=channel_id,
                        missing=held,
                    )
                missing = []
            ids = [video.id for video in [*to_queue, *missing]]
            if ids:
                self._downloader.mirror(ids, automatic=True, failed_too=True)
            if decide:
                self._prioritize([video.id for video in decide])
        if self._state.set(channel_id, question, held):
            self._views.publish(channel_id)

    def _busy(self) -> set[str]:
        return {job.video_id for job in self._jobs.jobs(ACTIVE_STATES)}

    def _height(self, channel: Channel) -> int | None:
        quality = effective_quality(channel.quality, self._settings.current().default_quality)
        return None if quality is Quality.BEST else int(quality.value)

    def _start_of_today(self) -> int:
        """The start of today in the Mac's time zone, as the date limit stores a day."""
        local = self._clock.now().astimezone()
        return int(local.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

    def _known(self, channel_id: str) -> Channel:
        channel = self._repository.channel(channel_id)
        if channel is None:
            raise AppError(ErrorCode.NOT_FOUND, {"channel": channel_id})
        return channel
