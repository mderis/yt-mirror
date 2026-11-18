"""The downloader: from "Mirror" to a synced file (docs/ARCHITECTURE.md section 7.2).

Implements R-MI-01 (one video at a time from the row and the details panel),
the flow of section 7.2, R-FI-03 (temp files only in the hidden folder),
R-FN-01 to R-FN-05 (the file name), R-MD-01 to R-MD-05 (metadata, subtitles,
thumbnails), R-DT-01, R-DT-07, R-DT-10 (the file dates), R-LG-02 (the job ID
in every log line) and R-LG-03 (every status change recorded).

Jobs wait in one line and are taken in the order of their priority. As many
run at once as the setting "Parallel downloads" allows (R-QU-01): each worker
takes the next job under one lock, and everything about a job is kept by its
ID. A download cancelled while it only asks YouTube takes no place among them:
its worker is replaced at once, and ends when YouTube's answer comes (R-QU-02).

Cancel ends a download at its next step. A download is past the point of no
return once its file is moved into the channel folder: then it ends synced.
After a cancel or a failure, nothing of the job is left but its log: its temp
folder is deleted, and no file of another video is touched. A quit, a crash,
"Pause all" and YouTube's "not a bot" check stop a download instead: it goes
back in line with its temp folder, and continues from its partial files the
next time it runs (R-QU-05, R-QU-06, D-091).

Tests: backend/tests/unit/services/test_downloader.py,
backend/tests/unit/services/test_downloader_queue.py,
backend/tests/integration/test_download_end_to_end.py
"""

import json
import threading
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import structlog
from structlog.typing import FilteringBoundLogger

from ytmirror.core.channels import Channel, Video, VideoStatus, VideoView
from ytmirror.core.dates import published_time
from ytmirror.core.errors import AppError, ErrorCode, ErrorKind
from ytmirror.core.jobs import (
    ACTIVE_STATES,
    Chapter,
    DownloadCancelledError,
    DownloadProgress,
    DownloadRequest,
    DownloadResult,
    Job,
    JobKind,
    JobProgress,
    JobProgressed,
    JobState,
    Stage,
    SubtitlesFailedError,
    VideoUpdated,
)
from ytmirror.core.media import MediaFacts, verification_problem
from ytmirror.core.naming import HIDDEN_DIR, TEMP_DIR, video_file_name
from ytmirror.core.quality import effective_quality
from ytmirror.core.queue import (
    GB,
    HAND_JOBS_PER_ACTION,
    DiskGuardPause,
    QueueChanged,
    QueueSummary,
    priorities_first,
    priorities_in_order,
    retry_delay,
)
from ytmirror.core.status import InvalidTransitionError, StatusChange, change_status
from ytmirror.ports.catalogue_repository import CatalogueRepository
from ytmirror.ports.clock import Clock
from ytmirror.ports.file_system import JOB_ID, FileSystem
from ytmirror.ports.job_repository import JobRepository
from ytmirror.ports.media_tools import MediaTools
from ytmirror.services.channel_views import ChannelViews
from ytmirror.services.download_state import DownloadState
from ytmirror.services.events import EventBus
from ytmirror.services.repair import verify_dates
from ytmirror.services.settings import SettingsService
from ytmirror.services.speed_limit import SpeedLimit
from ytmirror.services.youtube_access import CallLater, YouTubeAccess

_log: FilteringBoundLogger = structlog.get_logger(__name__)

PROGRESS_EVERY_S = 0.25
"""The shortest time between two progress events of one job: at most four a second."""

MIRRORABLE = frozenset({VideoStatus.NOT_DOWNLOADED, VideoStatus.FILE_MISSING})

LONGEST_WAIT_S = 60.0
"""The longest a worker waits before it looks again whether a paced download may start."""

DISK_CHECK_S = 5.0
"""How often a running download looks at the free space of its disk (R-QU-10)."""

_GONE = "removed from YouTube"
"""The reason a queued download of a video removed from YouTube ends (R-CH-14)."""
"""The statuses from which "Mirror" puts a video in line (ARCHITECTURE section 6.1)."""


@dataclass(frozen=True, slots=True)
class VideoDetails:
    """One video as the details panel shows it (R-UI-08).

    Attributes:
        view: The video as a list shows it.
        folder: The channel folder.
        file: The file of a synced video, or None.
        media: What the file contains, or None without a readable file.
        description: The description from the saved metadata, or None.
        chapters: The chapters from the saved metadata.
        thumbnail_saved: Whether the original thumbnail is in the hidden folder.
    """

    view: VideoView
    folder: Path
    file: Path | None
    media: MediaFacts | None
    description: str | None
    chapters: tuple[Chapter, ...]
    thumbnail_saved: bool


@dataclass(frozen=True, slots=True)
class _Place:
    """Where a job works: the channel folder, the hidden folder and its own temp folder."""

    folder: Path
    hidden: Path
    work: Path


@dataclass(frozen=True, slots=True)
class _SideData:
    """What the side files of a download hold, read before its file is moved into place."""

    info_json: bytes
    cover: bytes | None
    next_to_video: bool

    def files(self, video_id: str, name: str) -> list[tuple[str, bytes]]:
        """The side files: the info JSON, the original thumbnail, the cover next to the video."""
        files = [(f"{HIDDEN_DIR}/{video_id}.info.json", self.info_json)]
        if self.cover is not None:
            files.append((f"{HIDDEN_DIR}/{video_id}.jpg", self.cover))
            if self.next_to_video:
                files.append((str(Path(name).with_suffix(".jpg")), self.cover))
        return files


class DownloaderService:
    """Puts videos in line, downloads them one after another, and stores the result."""

    def __init__(
        self,
        *,
        repository: CatalogueRepository,
        jobs: JobRepository,
        youtube: YouTubeAccess,
        files: FileSystem,
        media: MediaTools,
        settings: SettingsService,
        views: ChannelViews,
        state: DownloadState,
        events: EventBus,
        clock: Clock,
        new_job_id: Callable[[], str],
        job_logs: Path,
        run_in_background: Callable[[Callable[[], None]], None],
        call_later: CallLater,
        speed: SpeedLimit | None = None,
        stop_tools: Callable[[], None] = lambda: None,
        stop_job_tools: Callable[[Path], None] = lambda _folder: None,
    ) -> None:
        """Create the downloader. Nothing runs before ``start``.

        Args:
            repository: The stored channels and videos.
            jobs: The stored jobs and the status history.
            youtube: The access to YouTube, under the pause of R-ER-05.
            files: Files and folders on this Mac.
            media: Reads a finished file.
            settings: The general settings: quality, subtitles, thumbnail.
            views: Builds and publishes channels, and knows their folders.
            state: The downloads that wait or run, shared with the views.
            events: Where changes are published.
            clock: The source of time.
            new_job_id: Gives a new ULID for each job.
            job_logs: The folder of the logs of jobs.
            run_in_background: Runs a worker without blocking.
            call_later: Runs work after a delay: the last progress report that
                came too soon after the one before (R-QU-04).
            speed: The limit of all downloads together (R-QU-03). None: unlimited.
            stop_tools: Stops the ffmpeg and the other tools the app started,
                when the app quits (R-PL-13).
            stop_job_tools: Stops the ffmpeg of one job, by its temp folder,
                when that job is cancelled (R-QU-02).
        """
        self._repository = repository
        self._jobs = jobs
        self._youtube = youtube
        self._files = files
        self._media = media
        self._settings = settings
        self._views = views
        self._state = state
        self._events = events
        self._clock = clock
        self._new_job_id = new_job_id
        self._job_logs = job_logs
        self._run_in_background = run_in_background
        self._stop_tools = stop_tools
        self._stop_job_tools = stop_job_tools
        self._call_later = call_later
        self._speed = speed
        self._work_of: dict[str, Path] = {}
        self._folders: dict[str, Path] = {}
        """The channel folder of each running job, for the disk space guard."""
        self._arrived: dict[str, int] = {}
        """How many bytes each running job had told, for the speed limit."""
        self._disk_checked: dict[str, float] = {}
        self._guard: DiskGuardPause | None = None
        """The pause of the disk space guard, or None (R-QU-10)."""
        self._guard_ignored: set[str] = set()
        """Disks the user resumed anyway: the guard leaves them until they had room again."""
        self._folders_away: set[str] = set()
        """Channels whose folder cannot be reached: their downloads wait (R-QU-11)."""
        self._wake = threading.Condition()
        self._started = False
        self._workers = 0
        """How many workers wait for jobs or run one, not counting retired ones."""
        self._worker_threads: set[int] = set()
        self._retired: set[int] = set()
        """Workers whose job was abandoned while it asked YouTube. Each ends with that job."""
        self._thread_of: dict[str, int] = {}
        """The thread that runs each running job."""
        self._side_files = threading.Lock()
        """Held while side files that waited are written: by one worker at a time."""
        self._held_reports: dict[str, JobProgress] = {}
        """The newest progress report of each job that came too soon to be told (R-QU-04)."""
        self._running: dict[str, str] = {}
        """The jobs that run, with the channel of each."""
        self._videos: dict[str, Video] = {}
        """The video of each running job, as it is now."""
        self._cancelled: set[str] = set()
        self._stopping: set[str] = set()
        """Running jobs that stop and go back in line, keeping their temp folder (D-091)."""
        self._asking: set[str] = set()
        """The running jobs that wait for YouTube and have written no file yet."""
        self._abandoned: set[str] = set()
        """Jobs that were cancelled while they waited for YouTube, and ended at once.

        Their worker still waits for YouTube's answer; when it comes, it is ignored:
        such a job writes no file, no row and no event any more (R-QU-02).
        """
        self._nothing_placed: set[str] = set()
        """The running jobs of which no file stands in a channel folder under a marker.

        Only for these may the end of the job clear the marker. For any other the
        marker stays, and the next job of the video or the next start cleans it up.
        """
        self._closed: set[str] = set()
        self._writing_side_files_of: str | None = None
        self._stopped = False
        self._last_told: dict[str, float] = {}

    # --- the life of the app

    def start(self) -> None:
        """Take up what the last run left, and start the workers.

        Jobs that waited stay in line, in their order (R-QU-06). A job that a
        crash left running goes back in line with its temp folder, so that it
        continues from its partial files (R-QU-05, D-091). A file it was moving
        into the channel folder goes to the Trash when it is that download
        (R-QA-06).
        """
        for job in self._jobs.jobs([JobState.RUNNING]):
            try:
                self._take_back(job)
            except Exception:  # noqa: BLE001  (one broken job must not stop the start)
                _log.error(
                    "download.failed",
                    msg="A job left by the last run could not be ended. The start goes on",
                    job_id=job.id,
                    error_code=ErrorCode.INTERNAL.value,
                    exc_info=True,
                )
        for cleanup in (self._clean_markers, self._sweep_temp_folders):
            try:
                cleanup(None)
            except Exception:  # noqa: BLE001  (a cleanup never stops the start)
                _log.error(
                    "download.failed",
                    msg="A cleanup at start failed. The start goes on",
                    error_code=ErrorCode.INTERNAL.value,
                    exc_info=True,
                )
        self._retry_side_files_quietly()
        for job in self._jobs.jobs([JobState.WAITING]):
            if job.not_before is not None and job.not_before > self._now():
                self._state.set_retry(job.video_id, job.not_before)
        self._youtube.when_asking_again(self._wake_up)
        with self._wake:
            self._started = True
        self._add_workers()

    def _wake_up(self) -> None:
        with self._wake:
            self._wake.notify_all()

    def _add_workers(self) -> None:
        """Start workers until as many run as the setting allows (R-QU-01).

        The setting is read each time, so a change takes effect without a restart:
        more workers start here, and the ones that are too many end when idle.
        """
        with self._wake:
            if not self._started or self._stopped:
                return
            missing = max(0, self._capacity() - self._workers)
            self._workers += missing
        for _ in range(missing):
            self._run_in_background(self._work_until_stopped)

    def _capacity(self) -> int:
        """How many downloads may run at once (R-QU-01)."""
        return self._settings.current().parallel_downloads

    def _busy(self) -> int:
        """How many places running jobs take. An abandoned lookup takes none (R-QU-02)."""
        return sum(1 for job_id in self._running if job_id not in self._abandoned)

    def stop(self, wait_s: float = 2.0) -> None:
        """Stop: every running download stops and goes back in line, to continue later.

        A quit is not a cancel (R-QU-02, D-091): each job keeps its temp folder
        and continues from its partial files at the next start (R-QU-05).

        Args:
            wait_s: How long to wait, for all of them together. The ffmpeg and the
                other tools the app started are stopped first, so that the jobs
                end at once. The wait is short, so a logout is never held (D-052);
                a job that has not ended by then is taken back at the next start.
                A job abandoned while it asked YouTube is not waited for.
        """
        with self._wake:
            self._stopped = True
            self._wake.notify_all()
        # The running ffmpeg steps are stopped, so that their jobs end now.
        self._stop_tools()
        with self._wake:
            self._wake.wait_for(lambda: self._busy() == 0, timeout=wait_s)

    def _work_until_stopped(self) -> None:
        me = threading.get_ident()
        with self._wake:
            self._worker_threads.add(me)
        try:
            while True:
                with self._wake:
                    while not (self._stopped or self._too_many() or self._next_job() is not None):
                        if not self._wake.wait(timeout=self._wait_for_room_s()):
                            # Time passed: room in the budget or on the disk may have come back.
                            self._update_paced()
                            self.look_at_disks_again()
                    if self._stopped or self._too_many():
                        self._workers -= 1
                        return
                try:
                    self.work_once()
                except Exception:  # noqa: BLE001  (a worker must never die)
                    # A worker must never die: the queue would stop until the next start.
                    _log.error(
                        "download.failed",
                        msg="A download worker hit an unexpected error and goes on",
                        error_code=ErrorCode.INTERNAL.value,
                        exc_info=True,
                    )
                with self._wake:
                    if me in self._retired:
                        # Its job was abandoned, and another worker took its place.
                        self._retired.discard(me)
                        return
        finally:
            with self._wake:
                self._worker_threads.discard(me)

    def _too_many(self) -> bool:
        """Whether more workers run than the setting allows: one of them ends (R-QU-01)."""
        return self._workers > self._capacity()

    def _next_job(self) -> Job | None:
        """The waiting job a worker takes next, or None when none may start now.

        Nothing starts while YouTube is paused (R-ER-05), while all downloads are
        paused (R-QU-02) or while every place is taken (R-QU-01). A job started by
        hand starts in its turn; an automatic one only when the lookup budget has
        room, and while it waits a later job started by hand goes ahead (D-090).
        A job that a worker took already is never taken twice.
        """
        if (
            self._stopped
            or self._youtube.pause() is not None
            or self._settings.current().downloads_paused
            or self._guard is not None
            or self._busy() >= self._capacity()
        ):
            return None
        room: int | None = None
        now = self._now()
        waiting = self._jobs.jobs([JobState.WAITING])
        away: set[str] = set()
        if self._folders_away:
            videos = self._repository.videos_by_id([job.video_id for job in waiting])
            away = {
                video_id
                for video_id, video in videos.items()
                if video.channel_id in self._folders_away
            }
        for job in waiting:
            if job.id in self._running or (job.not_before is not None and job.not_before > now):
                continue
            if job.video_id in away:
                continue
            if job.by_hand:
                return job
            if room is None:
                room = self._youtube.download_room()
            if room > 0:
                return job
        return None

    def _wait_for_room_s(self) -> float | None:
        """How long a worker waits before it looks again (D-090).

        Until the budget has room when a paced download waits, else until it is woken.
        """
        waiting = [
            job for job in self._jobs.jobs([JobState.WAITING]) if job.id not in self._running
        ]
        now = self._clock.now().timestamp()
        moments: list[float] = [
            job.not_before for job in waiting if job.not_before and job.not_before > now
        ]
        if any(not job.by_hand for job in waiting):
            until = self._youtube.paced_until(1)[0]
            if until is not None:
                moments.append(until)
        if self._guard is not None:
            moments.append(now + LONGEST_WAIT_S)
        if not moments:
            return None
        return min(LONGEST_WAIT_S, max(1.0, min(moments) - now))

    def _update_paced(self) -> None:
        """Note when each automatic download that waits for the budget may start (D-090).

        Its row then says so, with that time, so that it never looks stuck. The
        rows whose time changed are told again.
        """
        automatic = [
            job
            for job in self._jobs.jobs([JobState.WAITING])
            if not job.by_hand and job.id not in self._running
        ]
        times = self._youtube.paced_until(len(automatic))
        paced = {
            job.video_id: int(until)
            for job, until in zip(automatic, times, strict=True)
            if until is not None
        }
        changed = self._state.set_paced(paced)
        if paced and changed:
            _log.info(
                "queue.held",
                msg="Automatic downloads wait for room in the lookup budget",
                paced=len(paced),
                next_start=min(paced.values()),
            )
        for video_id in changed:
            self._views.tell_video(video_id)

    def work_once(self) -> bool:
        """Run the next waiting job, if there is one. Returns whether one ran."""
        with self._wake:
            job = self._next_job()
            if job is None:
                return False
            video = self._repository.video(job.video_id)
            self._running[job.id] = "" if video is None else video.channel_id
            self._thread_of[job.id] = threading.get_ident()
        try:
            with structlog.contextvars.bound_contextvars(job_id=job.id):
                self._run(job)
        except Exception:  # noqa: BLE001  (a broken job must not stop the queue)
            _log.error(
                "download.failed",
                msg="A download ended with an unexpected error. Its job is marked failed",
                job_id=job.id,
                video_id=job.video_id,
                error_code=ErrorCode.INTERNAL.value,
                exc_info=True,
            )
            self._give_up(job)
        finally:
            self._retry_side_files_quietly()
            with self._wake:
                self._running.pop(job.id, None)
                self._videos.pop(job.id, None)
                self._work_of.pop(job.id, None)
                self._last_told.pop(job.id, None)
                self._thread_of.pop(job.id, None)
                self._folders.pop(job.id, None)
                self._arrived.pop(job.id, None)
                self._disk_checked.pop(job.id, None)
                self._cancelled.discard(job.id)
                self._stopping.discard(job.id)
                self._nothing_placed.discard(job.id)
                self._asking.discard(job.id)
                self._abandoned.discard(job.id)
                self._wake.notify_all()
        return True

    # --- what the user asks for

    def mirror(self, video_ids: Sequence[str], *, first: bool = False) -> list[Job]:
        """Put videos in line to be downloaded, in the order given (R-MI-01).

        This is an action of the user: the first 20 jobs it puts in line are
        started by hand and never wait for the lookup budget, the others are
        automatic (R-DT-06, D-090). A video that waits already becomes a job
        started by hand. A video that runs, is synced, excluded (R-MI-05) or
        removed from YouTube is left as it is. With ``first`` the videos go to
        the top of the line, in the order given ("Mirror first", R-QU-02), also
        the ones that waited already.

        Args:
            video_ids: The videos.
            first: Whether they go to the top of the line.

        Returns:
            The jobs that were put in line.

        Raises:
            AppError: ``NOT_FOUND`` for a video no catalogue has.
        """
        queued: list[Job] = []
        chosen: list[str] = []
        for video_id in video_ids:
            # Two presses that arrive together must not give two jobs for one video.
            with self._wake:
                video = self._known(video_id)
                active = self._jobs.active_job_of(video_id)
                if active is not None:
                    if active.state is JobState.WAITING and active.id not in self._running:
                        if not active.by_hand:
                            self._jobs.mark_by_hand(active.id)
                        chosen.append(active.id)
                    continue
                if video.status not in MIRRORABLE or video.gone or video.excluded:
                    continue
                by_hand = len(queued) < HAND_JOBS_PER_ACTION
                job = self._put_in_line(video, "mirror", by_hand=by_hand)
                queued.append(job)
                chosen.append(job.id)
        if first and chosen:
            self._to_top(chosen)
        elif chosen and not queued:
            self._queue_changed()
        self._update_paced()
        return queued

    def pause_all(self) -> None:
        """Pause all downloads: no download starts until they are resumed (R-QU-02).

        The choice is stored, so a restart keeps it (spec section 10).
        """
        self._settings.change(downloads_paused=True)
        _log.info("queue.paused", msg="All downloads paused", reason="user")
        self._stop_running("paused")
        self._queue_changed()

    def _stop_running(self, reason: str) -> None:
        """Stop every running download; each goes back in line with its partial files (D-091).

        Args:
            reason: Why, for the log.
        """
        works: list[Path] = []
        with self._wake:
            for job_id in self._running:
                if job_id in self._abandoned or job_id in self._cancelled:
                    continue
                self._stopping.add(job_id)
                work = self._work_of.get(job_id)
                if work is not None:
                    works.append(work)
        for work in works:
            self._stop_job_tools(work)
        if works:
            _log.info("download.stopped", msg="Running downloads stop", reason=reason)

    def resume_all(self) -> None:
        """Resume all downloads (R-QU-02)."""
        self._settings.change(downloads_paused=False)
        _log.info("queue.resumed", msg="All downloads resumed", reason="user")
        self._wake_up()
        self._add_workers()
        self._queue_changed()

    def clear_waiting(self) -> int:
        """Remove every download that waits from the line (R-QU-02). Running ones go on.

        Returns:
            How many were removed.
        """
        removed = 0
        for job in self._jobs.jobs([JobState.WAITING]):
            with self._wake:
                if job.id in self._running:
                    continue
            if self.cancel(job.id):
                removed += 1
        return removed

    def reorder(self, job_ids: Sequence[str]) -> None:
        """Put the waiting downloads in the given order (R-QU-02, drag and drop).

        Args:
            job_ids: Waiting jobs in the order the user wants. One that no longer
                waits is ignored; a waiting one that is not named stays behind them.
        """
        with self._wake:
            waiting = [
                (job.id, job.priority)
                for job in self._jobs.jobs([JobState.WAITING])
                if job.id not in self._running
            ]
            changes = priorities_in_order(waiting, job_ids)
            self._jobs.set_priorities(changes)
            self._wake.notify_all()
        _log.info("queue.reordered", msg="The waiting downloads were reordered", moved=len(changes))
        self._update_paced()
        self._queue_changed()

    def queue_summary(self) -> QueueSummary:
        """Return how the queue stands (R-QU-01, R-QU-02)."""
        settings = self._settings.current()
        with self._wake:
            guard = self._guard
            away = tuple(sorted(self._folders_away))
        return QueueSummary(
            downloading=self._jobs.count([JobState.RUNNING]),
            waiting=self._jobs.count([JobState.WAITING]),
            failed=self._repository.count_with_status(VideoStatus.FAILED),
            paused=settings.downloads_paused,
            places=settings.parallel_downloads,
            speed_limit_mbps=settings.speed_limit_mbps,
            disk_guard=guard,
            folders_away=away,
        )

    def set_speed_limit(self, mbps: int) -> None:
        """Change the limit of all downloads together; it takes effect at once (R-QU-03).

        Args:
            mbps: MB/s, or 0 for unlimited.
        """
        self._settings.change(speed_limit_mbps=mbps)
        _log.info("queue.speed_limit", msg="The speed limit changed", mbps=mbps)
        self._queue_changed()

    def resume_anyway(self) -> None:
        """Resume the queue that the disk space guard paused (R-QU-10).

        The guard leaves that disk alone until it had more free space than the
        limit again: then it watches it as before.
        """
        with self._wake:
            guard = self._guard
            if guard is None:
                return
            self._guard_ignored.add(guard.disk)
            self._guard = None
            self._wake.notify_all()
        _log.info("queue.resumed", msg="The queue goes on although the disk is low", reason="disk")
        self._add_workers()
        self._queue_changed()

    def try_folder_again(self, channel_id: str) -> bool:
        """Look again whether the folder of a channel can be reached ("Try again", R-QU-11).

        Args:
            channel_id: The channel.

        Returns:
            Whether it can: then its downloads go on.
        """
        channel = self._repository.channel(channel_id)
        if channel is None:
            self._folder_back(channel_id)
            return True
        if not self._files.folder_exists(self._views.folder_of(channel)):
            return False
        self.tidy(channel_id)
        return True

    def _folder_away(self, channel_id: str, log: FilteringBoundLogger) -> None:
        """The folder of a channel cannot be reached: its downloads wait (R-QU-11)."""
        with self._wake:
            new = channel_id not in self._folders_away
            self._folders_away.add(channel_id)
        if new:
            log.warning(
                "queue.paused",
                msg="The folder of a channel cannot be reached. Its downloads wait",
                reason="folder",
                channel_id=channel_id,
            )
            self._queue_changed()

    def _folder_back(self, channel_id: str) -> None:
        """The folder of a channel can be reached again: its downloads go on (R-QU-11)."""
        with self._wake:
            if channel_id not in self._folders_away:
                return
            self._folders_away.discard(channel_id)
            self._wake.notify_all()
        _log.info(
            "queue.resumed",
            msg="The folder of a channel is back. Its downloads go on",
            reason="folder",
            channel_id=channel_id,
        )
        self._add_workers()
        self._queue_changed()

    def _disk_of(self, folder: Path) -> DiskGuardPause:
        disk = self._files.disk_of(folder)
        limit = self._settings.current().disk_guard_gb * GB
        return DiskGuardPause(disk=disk.name, free_bytes=disk.free_bytes, limit_bytes=limit)

    def _low_disk(self, folder: Path) -> DiskGuardPause | None:
        """Return the disk of a folder when the guard must pause for it, else None (R-QU-10)."""
        disk = self._disk_of(folder)
        with self._wake:
            if disk.free_bytes >= disk.limit_bytes:
                # It had room again: a later "Resume anyway" is needed afresh.
                self._guard_ignored.discard(disk.disk)
                return None
            if disk.disk in self._guard_ignored:
                return None
        return disk

    def _guard_hit(
        self, disk: DiskGuardPause, log: FilteringBoundLogger, *, full: bool = False
    ) -> None:
        """Pause the queue for lack of free space; running downloads stop and wait (R-QU-10)."""
        with self._wake:
            new = self._guard is None
            self._guard = disk
        if new:
            log.warning(
                "queue.disk_guard",
                msg="Too little free space: the queue pauses",
                disk=disk.disk,
                free_bytes=disk.free_bytes,
                limit_bytes=disk.limit_bytes,
                full=full,
            )
            self._stop_running("disk guard")
            self._queue_changed()

    def look_at_disks_again(self) -> None:
        """End the pause of the guard when its disk has room again (R-QU-10).

        A waiting worker does this every minute while the guard pauses the queue.
        """
        with self._wake:
            guard = self._guard
        if guard is None:
            return
        folders = [self._views.folder_of(channel) for channel in self._repository.channels()]
        for folder in folders:
            disk = self._files.disk_of(folder)
            if disk.name == guard.disk:
                if disk.free_bytes < self._settings.current().disk_guard_gb * GB:
                    return
                break
        with self._wake:
            self._guard = None
            self._wake.notify_all()
        _log.info("queue.resumed", msg="The disk has room again. The queue goes on", reason="disk")
        self._queue_changed()

    def _limit_speed(self, job: Job, progress: DownloadProgress) -> None:
        """Wait as long as the speed limit of all downloads asks (R-QU-03)."""
        if self._speed is None or progress.downloaded_bytes is None:
            return
        before = self._arrived.get(job.id, 0)
        self._arrived[job.id] = progress.downloaded_bytes
        # A download again without subtitles starts from 0: then it counts from there.
        arrived = progress.downloaded_bytes - before if progress.downloaded_bytes >= before else 0
        self._speed.took(arrived, stop=lambda: self._is_cancelled(job.id))

    def _watch_disk(self, job: Job) -> None:
        """Look at the free space of a running download's disk now and then (R-QU-10)."""
        folder = self._folders.get(job.id)
        now = self._clock.monotonic()
        if folder is None or now - self._disk_checked.get(job.id, -DISK_CHECK_S) < DISK_CHECK_S:
            return
        self._disk_checked[job.id] = now
        low = self._low_disk(folder)
        if low is not None:
            self._guard_hit(low, _log.bind(job_id=job.id))

    def _to_top(self, job_ids: Sequence[str]) -> None:
        """Put waiting jobs at the top of the line, in the order given (R-QU-02)."""
        with self._wake:
            priorities = priorities_first(len(job_ids), self._jobs.lowest_priority())
            self._jobs.set_priorities(dict(zip(job_ids, priorities, strict=True)))
            self._wake.notify_all()
        _log.info("queue.reordered", msg="Videos put at the top of the line", moved=len(job_ids))
        self._queue_changed()

    def _queue_changed(self) -> None:
        """Tell the interface how the queue stands now (R-FB-03)."""
        self._events.publish(QueueChanged(self.queue_summary()))

    def retry(self, video_id: str) -> Job:
        """Put a failed video in line again (R-QU-08, R-ER-03).

        Args:
            video_id: The video.

        Raises:
            AppError: ``NOT_FOUND`` for an unknown video, ``INVALID_REQUEST`` for
                a video that did not fail.
        """
        with self._wake:
            video = self._known(video_id)
            if (
                video.status is not VideoStatus.FAILED
                or video.gone  # YouTube no longer has it (R-CH-14)
                or video.excluded  # never queued by any path (R-MI-05)
                or self._jobs.active_job_of(video_id) is not None
            ):
                raise AppError(
                    ErrorCode.INVALID_REQUEST, {"video": video_id, "status": video.status}
                )
            return self._put_in_line(video, "retry")

    def cancel(self, job_id: str) -> bool:
        """Cancel a download that waits or runs (R-QU-02, R-ER-03).

        A waiting job goes at once, and so does a running one that has written
        no file yet: it only waits for YouTube's answer, which is then ignored.
        A job that writes files ends at its next step, once its ffmpeg is
        stopped and its temp folder removed. Either way its video goes back to
        "not downloaded".

        Args:
            job_id: The job.

        Returns:
            Whether there was such a job.
        """
        work: Path | None = None
        with self._wake:
            job = self._jobs.job(job_id)
            if job is None or job.state not in ACTIVE_STATES:
                return False
            running = job.id in self._running
            abandoned = job.id in self._asking
            if running:
                self._cancelled.add(job.id)
                work = self._work_of.get(job.id)
            if abandoned:
                # It has written nothing, and start_writing now refuses it: it ends here.
                self._asking.discard(job.id)
                self._abandoned.add(job.id)
                self._retire_worker_of(job.id)
                video = self._repository.video(job.video_id)
                self._end(job, video, JobState.CANCELLED, VideoStatus.NOT_DOWNLOADED, "cancelled")
                self._wake.notify_all()
        if abandoned:
            # Its worker waits for YouTube's answer: another one takes its place now.
            self._add_workers()
            _log.info(
                "download.cancelled",
                msg="Download cancelled before a file was written. YouTube's answer is ignored",
                job_id=job_id,
                video_id=job.video_id,
            )
            return True
        if running:
            # Its ffmpeg may copy a large file for a long time: it is stopped, so the job
            # ends at once and writes nothing more (R-QU-02, R-CH-32).
            if work is not None:
                self._stop_job_tools(work)
            return True
        with self._wake:
            video = self._repository.video(job.video_id)
            self._end(job, video, JobState.CANCELLED, VideoStatus.NOT_DOWNLOADED, "cancelled")
        _log.info(
            "download.cancelled",
            msg="Download cancelled before it started",
            job_id=job_id,
            video_id=job.video_id,
        )
        return True

    def _retire_worker_of(self, job_id: str) -> None:
        """Let the worker of an abandoned job end with it, and count it no more (R-QU-02).

        Called under the lock. A job run outside a worker (as in a test) has none.
        """
        thread = self._thread_of.get(job_id)
        if thread is not None and thread in self._worker_threads and thread not in self._retired:
            self._retired.add(thread)
            self._workers -= 1

    def end_removed(self, video_ids: Sequence[str]) -> None:
        """End the waiting downloads of videos a check found removed from YouTube (R-CH-14).

        Each ends at once, so its row never says "Queued" for a removed video. A
        download that already runs goes on: it succeeds, or fails with YouTube's
        reason. A failure here is logged and never fails the check.

        Args:
            video_ids: The videos the check holds as removed.
        """
        for video_id in video_ids:
            try:
                with self._wake:
                    job = self._jobs.active_job_of(video_id)
                    if job is None or job.state is not JobState.WAITING or job.id in self._running:
                        continue
                    video = self._repository.video(video_id)
                    self._end(job, video, JobState.CANCELLED, VideoStatus.NOT_DOWNLOADED, _GONE)
            except Exception:  # noqa: BLE001  (a check is never failed by this)
                _log.error(
                    "download.failed",
                    msg="A waiting download of a removed video could not be ended",
                    video_id=video_id,
                    error_code=ErrorCode.INTERNAL.value,
                    exc_info=True,
                )
                continue
            _log.info(
                "download.cancelled",
                msg="The video is gone from YouTube. Its waiting download ended",
                job_id=job.id,
                video_id=video_id,
                reason=_GONE,
            )

    def cancel_channel(self, channel_id: str, wait_s: float = 30.0) -> bool:
        """Cancel every download of a channel, and wait until none of them runs (R-CH-32).

        Args:
            channel_id: The channel.
            wait_s: How long to wait for a running download to end.

        Returns:
            Whether no download of the channel runs any more.
        """
        for job in self._jobs.jobs(ACTIVE_STATES):
            video = self._repository.video(job.video_id)
            if video is not None and video.channel_id == channel_id:
                self.cancel(job.id)
        with self._wake:
            # A job abandoned while it asked YouTube writes nothing more: no need to wait.
            return self._wake.wait_for(
                lambda: (
                    channel_id
                    not in {
                        channel
                        for job_id, channel in self._running.items()
                        if job_id not in self._abandoned
                    }
                    and self._writing_side_files_of != channel_id
                ),
                timeout=wait_s,
            )

    @contextmanager
    def channel_closed(self, channel_id: str, wait_s: float = 30.0) -> Generator[None]:
        """Keep the downloads of a channel stopped while it is removed (R-CH-32).

        On entry its downloads are cancelled and waited for. Until the exit no
        download of the channel is put in line and no side file is written in
        its folder, so nothing the removal moved to the Trash comes back.

        Args:
            channel_id: The channel.
            wait_s: How long to wait for a running download to end.

        Raises:
            AppError: ``CHANNEL_BUSY`` when a download did not end in time.
        """
        with self._wake:
            self._closed.add(channel_id)
        try:
            if not self.cancel_channel(channel_id, wait_s):
                # Never remove while a tool may still write in the folder.
                raise AppError(
                    ErrorCode.CHANNEL_BUSY,
                    {"channel": channel_id, "reason": "a download did not stop in time"},
                )
            yield
        finally:
            with self._wake:
                self._closed.discard(channel_id)

    def file_of(self, video_id: str) -> Path:
        """Return the file of a synced video (R-UI-10).

        Args:
            video_id: The video.

        Raises:
            AppError: ``NOT_FOUND`` for an unknown video or one without a file.
        """
        video = self._known(video_id)
        channel = self._repository.channel(video.channel_id)
        if channel is None or video.file_name is None:
            raise AppError(ErrorCode.NOT_FOUND, {"video": video_id})
        return self._views.folder_of(channel) / video.file_name

    def details(self, video_id: str) -> VideoDetails:
        """Return a video with everything the details panel shows (R-UI-08).

        Args:
            video_id: The video.

        Raises:
            AppError: ``NOT_FOUND`` for an unknown video.
        """
        view = self._views.video(video_id)
        channel = None if view is None else self._repository.channel(view.video.channel_id)
        if view is None or channel is None:
            raise AppError(ErrorCode.NOT_FOUND, {"video": video_id})
        folder = self._views.folder_of(channel)
        hidden = folder / HIDDEN_DIR
        file = None if view.video.file_name is None else folder / view.video.file_name
        media = None
        if file is not None and self._files.exists(file):
            try:
                media = self._media.probe(file)
            except AppError:
                media = None
        description, chapters = _saved_metadata(
            self._files.read_bytes(hidden / f"{video_id}.info.json")
        )
        return VideoDetails(
            view=view,
            folder=folder,
            file=file,
            media=media,
            description=description,
            chapters=chapters,
            thumbnail_saved=self._files.exists(hidden / f"{video_id}.jpg"),
        )

    def play(self, video_id: str) -> None:
        """Open the file of a video in the default player of macOS (R-UI-10).

        Args:
            video_id: The video.
        """
        self._files.open_file(self.file_of(video_id))

    def reveal(self, video_id: str) -> None:
        """Show the file of a video selected in Finder (R-UI-10).

        Args:
            video_id: The video.
        """
        self._files.reveal(self.file_of(video_id))

    # --- one job from start to synced

    def _run(self, job: Job) -> None:
        log = _log.bind(job_id=job.id, video_id=job.video_id)
        video = self._repository.video(job.video_id)
        channel = None if video is None else self._repository.channel(video.channel_id)
        if video is None or channel is None:
            self._end(job, video, JobState.CANCELLED, None, "gone")
            return
        log = log.bind(channel_id=channel.id)
        if video.gone:
            # A check found it removed from YouTube while it waited: it does not start (R-CH-14).
            self._end(job, video, JobState.CANCELLED, VideoStatus.NOT_DOWNLOADED, _GONE)
            log.info(
                "download.cancelled",
                msg="The video is gone from YouTube. Its download did not start",
                reason=_GONE,
            )
            return
        place = self._place_of(channel, job)
        if not self._files.folder_exists(place.folder):
            # The drive is away, or the folder is gone: the downloads of the channel wait
            # in line, and nothing is marked failed (R-QU-11).
            self._folder_away(channel.id, log)
            return
        low = self._low_disk(place.folder)
        if low is not None:
            self._guard_hit(low, log)
            return
        with self._wake:
            self._work_of[job.id] = place.work
            self._folders[job.id] = place.folder
        started = self._clock.monotonic()
        keep_work = False
        log.info("download.started", msg="Download started", quality=job.quality.value)
        running = replace(job, state=JobState.RUNNING, stage=Stage.VIDEO, started_at=self._now())
        try:
            video = self._change(running, video, VideoStatus.DOWNLOADING, "started")
            self._state.set_retry(video.id, None)
            self._videos[job.id] = video
            self._queue_changed()
            video = self._clean_marker_first(running, video, place)
            with self._wake:
                if self._is_cancelled(job.id):
                    raise DownloadCancelledError("cancelled before YouTube was asked")
                self._asking.add(job.id)
            result = self._download(running, video, place, log)
            video = self._processing(running)
            self._finish(running, video, channel, place, result, log, started)
        except Exception as error:  # noqa: BLE001  (a cancel is asked before any error is read)
            if self._was_abandoned(job.id):
                # Ended by the cancel already; YouTube's late answer, even an error, is ignored.
                return
            # A file of the job that could not leave the channel folder keeps its marker.
            keep_marker = job.id not in self._nothing_placed
            stopped = isinstance(error, DownloadCancelledError) or self._is_cancelled(job.id)
            delay = (
                retry_delay(error.code, video.attempts)
                if isinstance(error, AppError) and not stopped
                else None
            )
            if delay is not None and isinstance(error, AppError):
                # A failure that passes: tried again later, from its partial files (R-QU-07).
                keep_work = True
                self._retry_later(running, video, error.code, delay, log, keep_marker=keep_marker)
                return
            if isinstance(error, AppError) and error.code in (
                ErrorCode.FOLDER_UNAVAILABLE,
                ErrorCode.DISK_FULL,
            ):
                # The folder went away or the disk is full while it ran: the job waits in
                # line with what it downloaded, and the queue pauses (R-QU-10, R-QU-11).
                keep_work = True
                if error.code is ErrorCode.FOLDER_UNAVAILABLE:
                    self._folder_away(channel.id, log)
                else:
                    self._guard_hit(self._disk_of(place.folder), log, full=True)
                self._back_in_line(running, video, log, keep_marker=keep_marker, error=error)
                return
            if (stopped and self._resumes(job.id)) or (
                isinstance(error, AppError) and error.code is ErrorCode.BOT_CHECK
            ):
                # A quit, "Pause all" or YouTube's check: the job goes back in line with
                # its temp folder, to continue from its partial files (D-091).
                keep_work = True
                self._back_in_line(running, video, log, keep_marker=keep_marker, error=error)
                return
            # The temp folder goes before the end is stored and told: a video shown as
            # ended has nothing of its download left (R-QU-02, R-QA-06).
            self._remove_work(place, log)
            # A job that was cancelled stopped its tools: the error that follows is the
            # cancel, never a failure nor a retry (R-QU-02, R-PL-13).
            if stopped:
                self._end(
                    running,
                    video,
                    JobState.CANCELLED,
                    VideoStatus.NOT_DOWNLOADED,
                    "cancelled",
                    keep_marker=keep_marker,
                )
                log.info(
                    "download.cancelled",
                    msg="Download cancelled. Its temp files were deleted",
                    duration_ms=self._ms_since(started),
                )
            elif isinstance(error, AppError):
                self._failed(
                    running, video, error.code, log, started, error.details, keep_marker=keep_marker
                )
            else:
                self._failed_unexpectedly(running, video, log, started, keep_marker=keep_marker)
        finally:
            if not keep_work:
                self._remove_work(place, log)

    def _was_abandoned(self, job_id: str) -> bool:
        with self._wake:
            return job_id in self._abandoned

    def _start_writing(self, job: Job, place: _Place) -> None:
        """Called by the gateway right before the first file of the job is written.

        From here a cancel waits for the job to stop and clean up. Before it, the
        job only asked YouTube, and a cancel ended it at once (R-QU-02).

        Raises:
            DownloadCancelledError: When the job was cancelled meanwhile: then it
                writes nothing, not even its temp folder.
        """
        with self._wake:
            self._asking.discard(job.id)
            if job.id in self._abandoned or self._is_cancelled(job.id):
                raise DownloadCancelledError("cancelled before a file was written")
        self._files.make_folder(place.work, inside=place.folder)
        # Its lookup was counted: the paced downloads may start later now (D-090).
        self._update_paced()

    def _remove_work(self, place: _Place, log: FilteringBoundLogger) -> None:
        """Remove the temp folder of a job. A failure is a warning, never how the job ends.

        The folder stays for the sweep of the next start (R-FI-03): a cancel the user
        asked for never turns into an error because of it.
        """
        try:
            self._files.remove_temp_folder(place.work)
        except (AppError, OSError, ValueError) as error:
            log.warning(
                "download.temp_left",
                msg="The temp folder of a download could not be removed. The next start removes it",
                folder=str(place.work),
                error_code=getattr(error, "code", ErrorCode.INTERNAL).value,
            )

    def _failed_unexpectedly(
        self,
        job: Job,
        video: Video,
        log: FilteringBoundLogger,
        started: float,
        *,
        keep_marker: bool,
    ) -> None:
        log.error(
            "download.failed",
            msg="Download failed with an unexpected error",
            error_code=ErrorCode.INTERNAL.value,
            exc_info=True,
        )
        self._failed(job, video, ErrorCode.INTERNAL, None, started, {}, keep_marker=keep_marker)

    def _clean_marker_first(self, job: Job, video: Video, place: _Place) -> Video:
        """Clean up the file an earlier download of the video left under its marker (R-QA-06).

        That file goes to the Trash when the video ID inside it shows it is that
        download, so its name is free again. While its folder cannot be reached,
        the job fails and the marker stays: no path clears a marker without a cleanup.

        Raises:
            AppError: ``FOLDER_UNAVAILABLE``, or the error of the Trash.
        """
        if video.placing_file:
            problem = self._clean_placed(video, place.folder, job_id=job.id)
            if problem is not None:
                raise AppError(
                    problem,
                    {
                        "folder": str(place.folder),
                        "reason": "the file of an interrupted download is cleaned up first",
                    },
                )
            self._jobs.clear_placing_file(video.id)
            video = replace(video, placing_file=None)
            self._videos[job.id] = video
        self._nothing_placed.add(job.id)
        return video

    def _download(
        self, job: Job, video: Video, place: _Place, log: FilteringBoundLogger
    ) -> DownloadResult:
        """Step 3 and 4: yt-dlp downloads, merges and embeds. Subtitles fail only once."""
        settings = self._settings.current()
        self._prepare_to_continue(job, video, place, log)
        request = DownloadRequest(
            video_id=video.id,
            quality=job.quality,
            work_folder=place.work,
            log_file=self._job_logs / f"{job.id}.log",
            manual_subtitles=settings.embed_subtitles,
            auto_subtitles=settings.auto_subtitles,
            formats=job.formats,
        )
        try:
            return self._ask(job, video, request, place)
        except SubtitlesFailedError as failure:
            log.warning(
                "download.retry",
                msg="The subtitles failed. The video is downloaded again without them",
                reason=str(failure),
            )
            self._files.remove_temp_folder(place.work)
            self._files.make_folder(place.work, inside=place.folder)
            return self._ask(
                job,
                video,
                replace(request, manual_subtitles=False, auto_subtitles=False),
                place,
                again=True,
            )

    def _prepare_to_continue(
        self, job: Job, video: Video, place: _Place, log: FilteringBoundLogger
    ) -> None:
        """Keep what an earlier run of the job left in its temp folder, to continue it (D-091).

        Partial and finished streams stay, and yt-dlp continues them (R-QU-05). A
        finished file means the run stopped while the file was processed: then the
        job starts over, so that no step of the processing runs twice on it.
        """
        if not self._files.folder_exists(place.work):
            return
        if self._files.exists(place.work / f"{video.id}.mkv"):
            self._files.remove_temp_folder(place.work)
            log.info("download.resumed", msg="A download stopped while processed starts over")
            return
        log.info(
            "download.resumed",
            msg="A stopped download continues from its partial files",
            formats=job.formats,
        )

    def _chosen(self, job: Job, formats: str) -> None:
        """Keep the formats a download fetches, for when it continues after a stop (D-091)."""
        if formats != job.formats:
            self._jobs.set_formats(job.id, formats)

    def _ask(
        self,
        job: Job,
        video: Video,
        request: DownloadRequest,
        place: _Place,
        *,
        again: bool = False,
    ) -> DownloadResult:
        def told(progress: DownloadProgress) -> None:
            self._progressed(job, video, progress, again=again)

        try:
            return self._youtube.download(
                request,
                told,
                lambda: self._is_cancelled(job.id),
                by_user=job.by_hand,
                start_writing=lambda: self._start_writing(job, place),
                on_formats=lambda formats: self._chosen(job, formats),
            )
        except DownloadCancelledError:
            raise
        except Exception as error:
            # Asked before the error is read: a stopped ffmpeg is no failed subtitle.
            if self._is_cancelled(job.id):
                raise DownloadCancelledError("cancelled: its tools were stopped") from error
            raise

    def _finish(
        self,
        job: Job,
        video: Video,
        channel: Channel,
        place: _Place,
        result: DownloadResult,
        log: FilteringBoundLogger,
        started: float,
    ) -> None:
        """Steps 5 to 9: verify, keep the metadata, move into place, set the dates, store."""
        facts = self._media.probe(result.file)
        problem = verification_problem(facts, result.duration_s)
        if problem is not None:
            raise AppError(ErrorCode.VERIFY_FAILED, {"reason": problem})
        published = published_time(result.release_time, result.upload_time)
        if published is None:
            raise AppError(ErrorCode.DATES_NOT_APPLIED, {"reason": "YouTube gave no exact time"})
        # The dates are set while the file is still in the temp folder: a move keeps them, so
        # the file never stands in the channel folder with other dates (R-DT-07, R-QA-06).
        self._files.set_dates(result.file, published)
        # Everything that can fail on its own is done before the move.
        side = self._side_data_of(result)
        if self._is_cancelled(job.id):
            raise DownloadCancelledError("cancelled before the file was put in its place")
        name = self._move_into_place(job, video, place, result.file)
        target = place.folder / name
        # The rule from here: between the move into the channel folder and the synced
        # commit, every line is inside this try, whose failure moves the file back. A file
        # in the folder is never left unknown to the app (R-QA-06).
        try:
            synced = replace(
                video,
                file_name=name,
                height=facts.height,
                vcodec=facts.vcodec,
                acodec=facts.acodec,
                has_subtitles=None if result.subtitles is None else result.subtitles.value,
                downloaded_at=self._now(),
                published_at=published,
                published_exact=True,
                published_precision=None,
                last_error_code=None,
                last_error_at=None,
                attempts=0,
            )
            side_files = side.files(video.id, name)
            self._verify_dates(target, published, log)
            synced = replace(synced, file_size=self._files.size_of(target))
            done = replace(job, state=JobState.DONE, stage=None, finished_at=self._now())
            # The file is recorded, its marker cleared and its side files kept in one
            # write (R-QA-06). That commit is the point of no return: nothing after it
            # moves, trashes or deletes the file.
            stored = self._store_end(
                done,
                synced,
                JobState.DONE,
                VideoStatus.SYNCED,
                "verified",
                side_files,
                keep_marker=False,
            )
        except BaseException as error:
            if not isinstance(error, Exception):
                raise  # the end of the process: the next start cleans up by the marker
            # Until the video is recorded as synced, a file in the folder must not stay
            # unknown to the app (R-QA-06): it goes back to the temp folder of the job.
            if self._move_back(target, place, log):
                self._nothing_placed.add(job.id)
            if isinstance(error, AppError):
                raise
            if isinstance(error, OSError):
                raise AppError(ErrorCode.DATES_NOT_APPLIED, {"reason": str(error)}) from error
            raise
        self._announce_quietly(stored)
        self._write_side_files_of(synced, place.folder, log)
        log.info(
            "download.finished",
            msg="Download finished",
            file_size=synced.file_size,
            height=facts.height,
            subtitles=synced.has_subtitles,
            duration_ms=self._ms_since(started),
        )

    def _move_into_place(self, job: Job, video: Video, place: _Place, file: Path) -> str:
        """Step 2 and 7: choose the name and move the file in one step, never overwriting.

        The marker ``placing_file`` is stored before the move, and the name
        itself only when the video is recorded as synced. A crash between the
        two leaves a file the app knows by its marker: the next start moves it
        to the Trash once the video ID inside it shows it is this download.
        """
        tried: list[str] = []
        for _ in range(2):
            taken = [
                *self._files.file_names(place.folder),
                *self._names_tracked_in(place.folder, video.id),
                *tried,
            ]
            name = video_file_name(video.title, video.id, taken)
            current = self._videos.get(job.id, video)
            self._jobs.record(job, replace(current, placing_file=name))
            if self._files.move(file, place.folder / name):
                self._nothing_placed.discard(job.id)
                _log.info("file.moved", msg="File moved into its place", file=name)
                return name
            self._jobs.record(job, replace(current, placing_file=None))
            tried.append(name)
        raise AppError(ErrorCode.INTERNAL, {"reason": "the name was taken twice while moving"})

    def _names_tracked_in(self, folder: Path, except_video: str) -> list[str]:
        """Every name the app tracks in a folder, of every channel that shares it.

        A file the user deleted keeps its name taken: removing its channel later
        must not find another video under it.
        """
        names: list[str] = []
        for channel in self._repository.channels():
            if self._views.folder_of(channel) != folder:
                continue
            for other in self._repository.videos(channel.id):
                if other.id == except_video:
                    continue
                names += [name for name in (other.file_name, other.placing_file) if name]
        return names

    def _verify_dates(self, target: Path, published: int, log: FilteringBoundLogger) -> None:
        """Step 8: read both dates back in the channel folder (R-DT-07)."""
        try:
            verify_dates(self._files, target, published)
        except AppError as error:
            log.error(
                "dates.verify_failed",
                msg="The file dates did not read back as they were set",
                error_code=ErrorCode.DATES_NOT_APPLIED.value,
                expected=published,
                created=error.details.get("created"),
                modified=error.details.get("modified"),
            )
            raise
        log.info("dates.applied", msg="File dates set to the published time", published=published)

    # --- side files: the info JSON, the original thumbnail, the thumbnail next to the video

    def _side_data_of(self, result: DownloadResult) -> _SideData:
        """Read what the side files of a download hold. Done before the move: it can fail."""
        cover = None if result.thumbnail is None else self._files.read_bytes(result.thumbnail)
        return _SideData(
            info_json=result.info_json.encode("utf-8"),
            cover=cover,
            next_to_video=cover is not None and self._settings.current().thumbnail_next_to_video,
        )

    def _move_back(self, target: Path, place: _Place, log: FilteringBoundLogger) -> bool:
        """Move a file that was not recorded back to the temp folder. Returns whether it went."""
        try:
            if self._files.move(target, place.work / "not-finished.mkv"):
                return True
        except (AppError, OSError) as error:
            reason = str(error)
        else:
            reason = "a file of that name is in the temp folder"
        log.warning(
            "file.move_back_failed",
            msg="A file of a failed download could not leave the channel folder. Its marker stays",
            file=str(target),
            reason=reason,
        )
        return False

    def _write_side_files_of(self, video: Video, folder: Path, log: FilteringBoundLogger) -> None:
        """Write the side files a synced video keeps waiting. One that fails waits on."""
        if video.published_at is None:
            return
        for pending in self._jobs.pending_side_files():
            if pending.video_id != video.id:
                continue
            if self._write_side_file(
                video.id, folder, pending.path, pending.data, video.published_at
            ):
                self._jobs.remove_pending_side_file(pending.id)
                continue
            log.warning(
                "download.side_file_failed",
                msg="A side file of a synced video could not be written. It is tried again later",
                file=pending.path,
            )

    def _write_side_file(
        self, video_id: str, folder: Path, path: str, data: bytes, published: int
    ) -> bool:
        """Write one side file. Returns False when it could not be written now.

        A file of the hidden folder is replaced. A thumbnail next to the video is
        made in a temp folder with its dates, then moved, and never replaces a
        file that is there. It waits for the original thumbnail in the hidden
        folder, by which a removal recognises it as the app's own (R-CH-32).
        """
        target = folder / path
        try:
            if path.startswith(f"{HIDDEN_DIR}/"):
                self._files.write_file(target, data, overwrite=True, inside=folder)
                return True
            if self._files.read_bytes(folder / HIDDEN_DIR / f"{video_id}.jpg") != data:
                return False
            stage = folder / HIDDEN_DIR / TEMP_DIR / self._new_job_id()
            try:
                self._files.write_file(stage / target.name, data, overwrite=True, inside=folder)
                self._files.set_dates(stage / target.name, published)
                if not self._files.move(stage / target.name, target):
                    _log.info(
                        "download.side_file_skipped",
                        msg="A file of that name is there: the thumbnail is not put next to it",
                        file=path,
                    )
            finally:
                self._files.remove_temp_folder(stage)
        except AppError, OSError:
            return False
        return True

    def retry_side_files(self) -> None:
        """Write the side files that waited (R-MD-02, R-MD-05). One that fails again waits on.

        One worker at a time writes them: when another one does already, this returns.
        """
        if not self._side_files.acquire(blocking=False):
            return
        try:
            self._write_waiting_side_files()
        finally:
            self._side_files.release()

    def _write_waiting_side_files(self) -> None:
        for pending in self._jobs.pending_side_files():
            video = self._repository.video(pending.video_id)
            channel = None if video is None else self._repository.channel(video.channel_id)
            if video is None or channel is None or video.status is not VideoStatus.SYNCED:
                self._jobs.remove_pending_side_file(pending.id)
                continue
            folder = self._views.folder_of(channel)
            if video.published_at is None or not self._files.folder_exists(folder):
                continue
            with self._wake:
                if channel.id in self._closed:
                    continue
                self._writing_side_files_of = channel.id
            try:
                written = self._write_side_file(
                    video.id, folder, pending.path, pending.data, video.published_at
                )
            finally:
                with self._wake:
                    self._writing_side_files_of = None
                    self._wake.notify_all()
            if written:
                self._jobs.remove_pending_side_file(pending.id)
                _log.info(
                    "download.side_file_written",
                    msg="A side file that waited was written",
                    video_id=video.id,
                    file=pending.path,
                )

    # --- the end of a job

    def _failed(
        self,
        job: Job,
        video: Video,
        code: ErrorCode,
        log: FilteringBoundLogger | None,
        started: float,
        details: dict[str, str],
        *,
        keep_marker: bool = True,
    ) -> None:
        failed = replace(
            video, last_error_code=code, last_error_at=self._now(), attempts=video.attempts
        )
        self._end(
            replace(job, error_code=code, finished_at=self._now()),
            failed,
            JobState.FAILED,
            VideoStatus.FAILED,
            code.value,
            keep_marker=keep_marker,
        )
        if log is not None:
            log_at = log.warning if code.kind is ErrorKind.PERMANENT else log.error
            if code in (ErrorCode.NETWORK_UNREACHABLE, ErrorCode.RATE_LIMITED):
                log_at = log.warning
            log_at(
                "download.failed",
                msg="Download failed",
                error_code=code.value,
                duration_ms=self._ms_since(started),
                **details,
            )

    def _retry_later(
        self,
        job: Job,
        video: Video,
        code: ErrorCode,
        delay: int,
        log: FilteringBoundLogger,
        *,
        keep_marker: bool,
    ) -> None:
        """Put a download that failed in a way that passes back in line, to try later (R-QU-07).

        It waits ``delay`` seconds, keeps its temp folder, and is an automatic job
        from now on: it waits for room in the lookup budget too (D-090). Its row
        says when it is tried again.
        """
        now = self._now()
        attempt = video.attempts + 1
        waiting = replace(job, by_hand=False, not_before=now + delay, error_code=code)
        failed = replace(video, attempts=attempt, last_error_code=code, last_error_at=now)
        self._store_end(
            waiting, failed, JobState.WAITING, VideoStatus.QUEUED, "retry", keep_marker=keep_marker
        )
        self._state.restarted(video.id)
        self._state.set_retry(video.id, now + delay)
        self._views.tell_video(video.id)
        self._views.publish(video.channel_id)
        self._queue_changed()
        self._wake_up()
        log.warning(
            "download.retry",
            msg="The download failed in a way that passes. It is tried again later",
            reason="transient",
            error_code=code.value,
            attempt=attempt,
            delay_s=delay,
        )

    def _back_in_line(
        self,
        job: Job,
        video: Video,
        log: FilteringBoundLogger,
        *,
        keep_marker: bool,
        error: Exception,
    ) -> None:
        """Put a stopped job back in line, with its place and its temp folder (D-091).

        A quit, "Pause all" and YouTube's "not a bot" check stop a download: it
        continues from its partial files the next time it runs (R-QU-05). The "not
        a bot" check is one condition of the whole app, never one error per video
        (R-ER-05): the job waits until YouTube is asked again.
        """
        bot_check = isinstance(error, AppError) and error.code is ErrorCode.BOT_CHECK
        reason = "youtube paused" if bot_check else "stopped"
        self._store_end(
            job, video, JobState.WAITING, VideoStatus.QUEUED, reason, keep_marker=keep_marker
        )
        self._state.restarted(video.id)
        self._tell(replace(video, status=VideoStatus.QUEUED))
        self._views.publish(video.channel_id)
        self._queue_changed()
        if bot_check:
            log.warning(
                "download.retry",
                msg="YouTube asked to confirm that the app is not a bot. The download waits",
                error_code=ErrorCode.BOT_CHECK.value,
            )
        else:
            log.info(
                "download.stopped",
                msg="The download stopped. It continues from its partial files later",
                reason="quit" if self._stopped else "paused",
            )

    def _end(
        self,
        job: Job,
        video: Video | None,
        state: JobState,
        status: VideoStatus | None,
        reason: str,
        *,
        keep_marker: bool = True,
    ) -> None:
        """Store how a job ended, with its video and the status change, and tell everyone.

        ``keep_marker`` keeps the stored marker of a placed file. Only an end that
        knows no file stands under it clears it: no path clears a marker without a
        cleanup (R-QA-06).
        """
        self._announce(self._store_end(job, video, state, status, reason, keep_marker=keep_marker))
        self._queue_changed()

    def _store_end(
        self,
        job: Job,
        video: Video | None,
        state: JobState,
        status: VideoStatus | None,
        reason: str,
        side_files: Sequence[tuple[str, bytes]] = (),
        *,
        keep_marker: bool = True,
    ) -> Video | None:
        """Store how a job ended, in one transaction. Returns the video to tell about, or None."""
        ended = replace(
            job,
            state=state,
            stage=None,
            finished_at=None if state is JobState.WAITING else self._now(),
        )
        current = None if video is None else self._repository.video(video.id)
        if video is not None and current is None:
            # The video went with its channel: its job and history went with it (R-CH-32).
            self._state.ended(video.id)
            return None
        change: StatusChange | None = None
        if video is not None and current is not None and status is not None:
            video = replace(video, placing_file=current.placing_file if keep_marker else None)
            if status is not VideoStatus.SYNCED:
                video = replace(video, file_name=None, file_size=None)
            if current.status is not status:
                try:
                    change = change_status(video.id, current.status, status, reason)
                except InvalidTransitionError:
                    _log.error(
                        "download.failed",
                        msg="A download ended in a status its video cannot take. Kept as it is",
                        job_id=job.id,
                        video_id=video.id,
                        from_status=current.status.value,
                        to_status=status.value,
                        error_code=ErrorCode.INTERNAL.value,
                    )
                    video = current
                else:
                    video = replace(video, status=status)
        self._jobs.record(ended, video, change, side_files)
        return None if state is JobState.WAITING else video

    def _announce(self, video: Video | None) -> None:
        """Tell the interface how a video is after its job ended."""
        if video is not None:
            self._state.ended(video.id)
            self._tell(video)
            self._views.publish(video.channel_id)

    def _announce_quietly(self, video: Video | None) -> None:
        """Tell the interface after the synced commit. A failure is logged, nothing more."""
        try:
            self._announce(video)
            self._queue_changed()
        except Exception:  # noqa: BLE001  (the file is stored: nothing may undo it)
            _log.error(
                "download.tell_failed",
                msg="The interface could not be told about a synced video. The file stays",
                video_id=None if video is None else video.id,
                error_code=ErrorCode.INTERNAL.value,
                exc_info=True,
            )

    def _take_back(self, job: Job) -> None:
        """Put back in line a job that a crash or a quit left running (R-QU-05, R-QU-06, D-091).

        It keeps its place in the line and its temp folder, so that it continues
        from its partial files. A file it was moving into the channel folder (its
        marker) goes to the Trash when the video ID inside it shows it is this
        download; while its folder cannot be reached, the marker stays, and a
        later cleanup takes it once it can (``_clean_markers``).
        """
        video = self._repository.video(job.video_id)
        channel = None if video is None else self._repository.channel(video.channel_id)
        cleaned = True
        if channel is not None and video is not None:
            place = self._place_of(channel, job)
            cleaned = self._clean_placed(video, place.folder, job_id=job.id) is None
        self._store_end(
            job, video, JobState.WAITING, VideoStatus.QUEUED, "interrupted", keep_marker=not cleaned
        )
        _log.info(
            "download.stopped",
            msg="A download that the last run left running goes back in line",
            job_id=job.id,
            video_id=job.video_id,
            reason="interrupted",
        )

    def _clean_placed(
        self, video: Video, folder: Path, job_id: str | None = None
    ) -> ErrorCode | None:
        """Clean up the file a video's marker names. Returns None when it is done.

        Not done while the channel folder cannot be reached, for example on a
        drive that is not connected (``FOLDER_UNAVAILABLE``), or when the Trash
        refused (its error code).
        """
        if not video.placing_file:
            return None
        if not self._files.folder_exists(folder):
            _log.warning(
                "file.unreachable",
                msg="The folder of an interrupted download is not there. It is cleaned up later",
                video_id=video.id,
                folder=str(folder),
            )
            return ErrorCode.FOLDER_UNAVAILABLE
        try:
            self._trash_own_download(video, folder / video.placing_file)
        except (AppError, OSError) as error:
            self._cleanup_failed(video.id, error, job_id=job_id)
            return error.code if isinstance(error, AppError) else ErrorCode.PERMISSION_DENIED
        return None

    def _cleanup_failed(self, video_id: str, error: Exception, job_id: str | None = None) -> None:
        _log.warning(
            "file.trash_failed",
            msg="A file of an interrupted download could not be cleaned up",
            job_id=job_id,
            video_id=video_id,
            error_code=getattr(error, "code", ErrorCode.INTERNAL).value,
        )

    def tidy(self, channel_id: str) -> None:
        """Clean up what earlier runs left in a channel folder that can be reached now.

        At start a drive that is not connected keeps its left-overs: the files of
        markers and the temp folders of jobs that ended. This takes them up as
        soon as the folder is there again, after a check or when the channel is
        opened, without waiting for the next start. The temp folder of a job that
        waits stays: it continues from it (D-091). A failure is logged.

        Args:
            channel_id: The channel.
        """
        channel = self._repository.channel(channel_id)
        if channel is None or not self._files.folder_exists(self._views.folder_of(channel)):
            return
        self._folder_back(channel_id)
        for cleanup in (self._clean_markers, self._sweep_temp_folders):
            try:
                cleanup([channel])
            except Exception:  # noqa: BLE001  (a cleanup never fails a check)
                _log.error(
                    "download.failed",
                    msg="A cleanup of a channel folder failed",
                    channel_id=channel_id,
                    error_code=ErrorCode.INTERNAL.value,
                    exc_info=True,
                )

    def _clean_markers(self, channels: Sequence[Channel] | None = None) -> None:
        """Clean up the files that marked videos left, once their folder is there again."""
        for channel in self._repository.channels() if channels is None else channels:
            folder = self._views.folder_of(channel)
            for video in self._repository.videos(channel.id):
                if not video.placing_file or self._jobs.active_job_of(video.id) is not None:
                    continue
                if self._clean_placed(video, folder) is None:
                    self._jobs.clear_placing_file(video.id)

    def _sweep_temp_folders(self, channels: Sequence[Channel] | None = None) -> None:
        """Remove the temp folders of jobs that are no longer active (R-FI-03, R-QA-06).

        A quit can end a job before its temp folder went. Only a folder named
        like a job ID is removed, through the guard of ``remove_temp_folder``;
        anything else in the temp folder stays.
        """
        active = {job.id for job in self._jobs.jobs(ACTIVE_STATES)}
        for channel in self._repository.channels() if channels is None else channels:
            temp = self._views.folder_of(channel) / HIDDEN_DIR / TEMP_DIR
            if not self._files.folder_exists(temp):
                continue
            for name in self._files.file_names(temp, hidden=True):
                if not JOB_ID.fullmatch(name) or name in active:
                    continue
                try:
                    self._files.remove_temp_folder(temp / name)
                except (AppError, OSError, ValueError) as error:
                    self._cleanup_failed("", error, job_id=name)
                    continue
                _log.info(
                    "download.temp_swept",
                    msg="The temp folder of a job that ended was removed",
                    job_id=name,
                    channel_id=channel.id,
                )

    def _trash_own_download(self, video: Video, moved: Path) -> None:
        """Move a file an interrupted download put in place to the Trash, if it is that video."""
        if not self._files.exists(moved):
            return
        try:
            own = self._media.probe(moved).tags.get("video_id") == video.id
        except AppError:
            own = False
        if not own:
            _log.warning(
                "file.kept",
                msg="A file has the name of an interrupted download but is not that video",
                video_id=video.id,
                file=str(moved),
            )
            return
        self._files.trash(moved)
        _log.info("file.trashed", msg="File of an interrupted download", file=str(moved))

    def _retry_side_files_quietly(self) -> None:
        try:
            self.retry_side_files()
        except Exception:  # noqa: BLE001  (side files never stop a start or the queue)
            _log.error(
                "download.side_file_failed",
                msg="Side files that waited could not be tried again",
                error_code=ErrorCode.INTERNAL.value,
                exc_info=True,
            )

    def _give_up(self, job: Job) -> None:
        """End a job that broke in an unexpected way, as far as that is still possible."""
        try:
            video = self._repository.video(job.video_id)
            self._end(
                replace(job, error_code=ErrorCode.INTERNAL, finished_at=self._now()),
                video,
                JobState.FAILED,
                VideoStatus.FAILED,
                ErrorCode.INTERNAL.value,
            )
        except Exception:  # noqa: BLE001  (the next start cleans it up)
            _log.error(
                "download.failed",
                msg="A broken job could not be ended. The next start cleans it up",
                job_id=job.id,
                error_code=ErrorCode.INTERNAL.value,
                exc_info=True,
            )

    # --- helpers

    def _put_in_line(self, video: Video, reason: str, *, by_hand: bool = True) -> Job:
        channel = self._repository.channel(video.channel_id)
        if channel is None or channel.id in self._closed:
            raise AppError(ErrorCode.NOT_FOUND, {"video": video.id})
        job = Job(
            id=self._new_job_id(),
            video_id=video.id,
            kind=JobKind.DOWNLOAD,
            state=JobState.WAITING,
            priority=self._jobs.next_priority(),
            quality=effective_quality(channel.quality, self._settings.current().default_quality),
            created_at=self._now(),
            by_hand=by_hand,
        )
        if by_hand:
            # An action of the user starts the retries of R-QU-07 afresh.
            video = replace(video, attempts=0)
        queued = self._change(job, video, VideoStatus.QUEUED, reason)
        self._state.queued(video.id, channel.id, job.id)
        _log.info(
            "queue.enqueued",
            msg="Video put in line",
            job_id=job.id,
            video_id=video.id,
            channel_id=channel.id,
            quality=job.quality.value,
            reason=reason,
            by_hand=by_hand,
        )
        self._tell(queued)
        self._views.publish(channel.id)
        with self._wake:
            self._wake.notify_all()
        # The setting may allow more downloads now than when the workers started.
        self._add_workers()
        self._queue_changed()
        return job

    def _change(self, job: Job, video: Video, status: VideoStatus, reason: str) -> Video:
        """Store a job with a status change of its video, and tell the interface."""
        change = change_status(video.id, video.status, status, reason)
        changed = replace(video, status=status)
        self._jobs.record(job, changed, change)
        if job.state is not JobState.WAITING:
            self._tell(changed)
        return changed

    def _processing(self, job: Job) -> Video:
        """The streams are done: the video is processing, once (ARCHITECTURE section 6.1)."""
        video = self._videos[job.id]
        if video.status is VideoStatus.DOWNLOADING:
            video = self._change(
                replace(job, stage=Stage.PROCESSING), video, VideoStatus.PROCESSING, "streams done"
            )
            self._videos[job.id] = video
        return video

    def _progressed(
        self, job: Job, video: Video, progress: DownloadProgress, *, again: bool = False
    ) -> None:
        if progress.stage is Stage.PROCESSING:
            video = self._processing(job)
        self._limit_speed(job, progress)
        self._watch_disk(job)
        previous = self._state.progress_of(video.id)
        told = JobProgress(
            job_id=job.id,
            video_id=video.id,
            channel_id=video.channel_id,
            stage=progress.stage,
            fraction=progress.fraction,
            speed_bps=progress.speed_bps,
            left_s=progress.left_s,
            height=progress.height,
            downloaded_bytes=progress.downloaded_bytes,
            total_bytes=progress.total_bytes,
            parts=progress.parts,
            again=again,
        )
        self._state.progressed(told)
        now = self._clock.monotonic()
        last = self._last_told.get(job.id)
        stage_changed = (
            previous is None or previous.stage is not progress.stage or progress.fraction == 1.0
        )
        if last is not None and now - last < PROGRESS_EVERY_S and not stage_changed:
            # Too soon to be told now. If no newer report comes, this one is told once
            # the quarter second is over, so a row never keeps an old percent (R-QU-04).
            with self._wake:
                first = job.id not in self._held_reports
                self._held_reports[job.id] = told
            if first:
                self._call_later(
                    PROGRESS_EVERY_S - (now - last), lambda: self._tell_held_report(job.id)
                )
            return
        with self._wake:
            self._held_reports.pop(job.id, None)
            self._last_told[job.id] = now
        self._events.publish(JobProgressed(told))

    def _tell_held_report(self, job_id: str) -> None:
        """Tell the progress report that came too soon, unless a newer one was told (R-QU-04)."""
        with self._wake:
            told = self._held_reports.pop(job_id, None)
            if told is None or job_id not in self._running or job_id in self._abandoned:
                return
            self._last_told[job_id] = self._clock.monotonic()
        self._events.publish(JobProgressed(told))

    def _tell(self, video: Video) -> None:
        """Tell the interface how a video is now (R-FB-03)."""
        view = self._views.video(video.id)
        if view is not None:
            self._events.publish(VideoUpdated(view))

    def _is_cancelled(self, job_id: str) -> bool:
        """Whether a running job must end at its next step: cancelled, or stopped (D-091)."""
        with self._wake:
            return self._stopped or job_id in self._cancelled or job_id in self._stopping

    def _resumes(self, job_id: str) -> bool:
        """Whether a job that ends now goes back in line rather than being cancelled (D-091)."""
        with self._wake:
            return (self._stopped or job_id in self._stopping) and job_id not in self._cancelled

    def _place_of(self, channel: Channel, job: Job) -> _Place:
        folder = self._views.folder_of(channel)
        hidden = folder / HIDDEN_DIR
        return _Place(folder=folder, hidden=hidden, work=hidden / TEMP_DIR / job.id)

    def _known(self, video_id: str) -> Video:
        video = self._repository.video(video_id)
        if video is None:
            raise AppError(ErrorCode.NOT_FOUND, {"video": video_id})
        return video

    def _now(self) -> int:
        return int(self._clock.now().timestamp())

    def _ms_since(self, started: float) -> int:
        return round((self._clock.monotonic() - started) * 1000)


def _saved_metadata(info_json: bytes | None) -> tuple[str | None, tuple[Chapter, ...]]:
    """Return the description and the chapters of the saved raw metadata (R-MD-02)."""
    if info_json is None:
        return None, ()
    try:
        info = json.loads(info_json)
    except ValueError:
        return None, ()
    if not isinstance(info, dict):
        return None, ()
    facts = cast(dict[str, Any], info)
    description = facts.get("description")
    chapters = [
        cast(dict[str, Any], chapter)
        for chapter in facts.get("chapters") or ()
        if isinstance(chapter, dict)
    ]
    return (
        description if isinstance(description, str) else None,
        tuple(
            Chapter(
                start_s=float(chapter.get("start_time") or 0), title=str(chapter.get("title") or "")
            )
            for chapter in chapters
        ),
    )
