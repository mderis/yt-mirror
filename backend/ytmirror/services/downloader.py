"""The downloader: from "Mirror" to a synced file (docs/ARCHITECTURE.md section 7.2).

Implements R-MI-01 (one video at a time from the row and the details panel),
the flow of section 7.2, R-FI-03 (temp files only in the hidden folder),
R-FN-01 to R-FN-05 (the file name), R-MD-01 to R-MD-05 (metadata, subtitles,
thumbnails), R-DT-01, R-DT-07, R-DT-10 (the file dates), R-LG-02 (the job ID
in every log line) and R-LG-03 (every status change recorded).

Jobs wait in one line and are taken in the order of their priority. The
worker is built so that more than one can run (R-QU-01, milestone M5): a
worker takes the next job under a lock, and everything about a job is kept
by its ID. Milestone M3 runs one worker.

Cancel ends a download at its next step. A download is past the point of no
return once its file is moved into the channel folder: then it ends synced.
After a cancel, a failure or a quit, nothing of the job is left but its log:
its temp folder is deleted, and no file of another video is touched.

Tests: backend/tests/unit/services/test_downloader.py,
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
from ytmirror.core.status import InvalidTransitionError, StatusChange, change_status
from ytmirror.ports.catalogue_repository import CatalogueRepository
from ytmirror.ports.clock import Clock
from ytmirror.ports.file_system import FileSystem
from ytmirror.ports.job_repository import JobRepository
from ytmirror.ports.media_tools import MediaTools
from ytmirror.services.channel_views import ChannelViews
from ytmirror.services.download_state import DownloadState
from ytmirror.services.events import EventBus
from ytmirror.services.settings import SettingsService
from ytmirror.services.youtube_access import YouTubeAccess

_log: FilteringBoundLogger = structlog.get_logger(__name__)

PROGRESS_EVERY_S = 0.25
"""The shortest time between two progress events of one job: at most four a second."""

MIRRORABLE = frozenset({VideoStatus.NOT_DOWNLOADED, VideoStatus.FILE_MISSING})
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
        workers: int = 1,
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
            workers: How many downloads run at once. One in milestone M3.
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
        self._work_of: dict[str, Path] = {}
        self._workers = workers
        self._wake = threading.Condition()
        self._running: dict[str, str] = {}
        """The jobs that run, with the channel of each."""
        self._videos: dict[str, Video] = {}
        """The video of each running job, as it is now."""
        self._cancelled: set[str] = set()
        self._closed: set[str] = set()
        self._writing_side_files_of: str | None = None
        self._stopped = False
        self._last_told: dict[str, float] = {}

    # --- the life of the app

    def start(self) -> None:
        """Clean up what a quit left, and start the workers.

        A job that waited or ran when the app ended is cancelled, its temp
        folder deleted and its video back to "not downloaded": nothing half
        written stays (R-QA-06). Milestone M5 resumes these instead (R-QU-05,
        R-QU-06).
        """
        for job in self._jobs.jobs(ACTIVE_STATES):
            try:
                self._end_left_over(job)
            except Exception:  # noqa: BLE001  (one broken job must not stop the start)
                _log.error(
                    "download.failed",
                    msg="A job left by the last run could not be ended. The start goes on",
                    job_id=job.id,
                    error_code=ErrorCode.INTERNAL.value,
                    exc_info=True,
                )
        self._retry_side_files_quietly()
        self._youtube.when_asking_again(self._wake_up)
        for _ in range(self._workers):
            self._run_in_background(self._work_until_stopped)

    def _wake_up(self) -> None:
        with self._wake:
            self._wake.notify_all()

    def stop(self, wait_s: float = 2.0) -> None:
        """Stop: a running download is cancelled and cleaned up before this returns.

        Args:
            wait_s: How long to wait for a running download to end. The ffmpeg
                and the other tools the app started are stopped first, so that
                the job ends at once. The wait is short, so a logout is
                never held (D-052); a job that has not ended by then is cleaned up
                at the next start.
        """
        with self._wake:
            self._stopped = True
            self._wake.notify_all()
        # A running ffmpeg step is stopped, so that its job ends and cleans up now.
        self._stop_tools()
        with self._wake:
            self._wake.wait_for(lambda: not self._running, timeout=wait_s)

    def _work_until_stopped(self) -> None:
        while True:
            with self._wake:
                self._wake.wait_for(lambda: self._stopped or self._has_waiting())
                if self._stopped:
                    return
            try:
                self.work_once()
            except Exception:  # noqa: BLE001  (the one worker must never die)
                # The one worker must never die: the queue would stop until the next start.
                _log.error(
                    "download.failed",
                    msg="The download worker hit an unexpected error and goes on",
                    error_code=ErrorCode.INTERNAL.value,
                    exc_info=True,
                )

    def _has_waiting(self) -> bool:
        """Whether a job can start now. While YouTube is paused, waiting jobs wait (R-ER-05)."""
        return self._youtube.pause() is None and bool(self._jobs.jobs([JobState.WAITING]))

    def work_once(self) -> bool:
        """Run the next waiting job, if there is one. Returns whether one ran."""
        with self._wake:
            if self._stopped or self._youtube.pause() is not None:
                return False
            job = next(
                (job for job in self._jobs.jobs([JobState.WAITING]) if job.id not in self._running),
                None,
            )
            if job is None:
                return False
            video = self._repository.video(job.video_id)
            self._running[job.id] = "" if video is None else video.channel_id
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
                self._cancelled.discard(job.id)
                self._wake.notify_all()
        return True

    # --- what the user asks for

    def mirror(self, video_ids: list[str]) -> list[Job]:
        """Put videos in line to be downloaded, in the order given (R-MI-01).

        A video that waits or runs already, or is synced, is left as it is.

        Args:
            video_ids: The videos.

        Returns:
            The jobs that were put in line.

        Raises:
            AppError: ``NOT_FOUND`` for a video no catalogue has.
        """
        queued: list[Job] = []
        for video_id in video_ids:
            # Two presses that arrive together must not give two jobs for one video.
            with self._wake:
                video = self._known(video_id)
                if video.status not in MIRRORABLE or self._jobs.active_job_of(video_id) is not None:
                    continue
                queued.append(self._put_in_line(video, "mirror"))
        return queued

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
                or self._jobs.active_job_of(video_id) is not None
            ):
                raise AppError(
                    ErrorCode.INVALID_REQUEST, {"video": video_id, "status": video.status}
                )
            return self._put_in_line(video, "retry")

    def cancel(self, job_id: str) -> bool:
        """Cancel a download that waits or runs (R-QU-02, R-ER-03).

        A waiting job goes at once. A running one ends at its next step, and
        its video goes back to "not downloaded".

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
            if running:
                self._cancelled.add(job.id)
                work = self._work_of.get(job.id)
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
            return self._wake.wait_for(
                lambda: (
                    channel_id not in self._running.values()
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
        place = self._place_of(channel, job)
        with self._wake:
            self._work_of[job.id] = place.work
        started = self._clock.monotonic()
        log.info("download.started", msg="Download started", quality=job.quality.value)
        running = replace(job, state=JobState.RUNNING, stage=Stage.VIDEO, started_at=self._now())
        try:
            video = self._change(running, video, VideoStatus.DOWNLOADING, "started")
            self._videos[job.id] = video
            self._files.make_folder(place.work, inside=place.folder)
            result = self._download(running, video, place, log)
            video = self._processing(running)
            self._finish(running, video, channel, place, result, log, started)
        except Exception as error:  # noqa: BLE001  (a cancel is asked before any error is read)
            # A job that was cancelled, or an app that quits, stopped the tools: the error
            # that follows is the cancel, never a failure nor a retry (R-QU-02, R-PL-13).
            if isinstance(error, DownloadCancelledError) or self._is_cancelled(job.id):
                self._end(
                    running, video, JobState.CANCELLED, VideoStatus.NOT_DOWNLOADED, "cancelled"
                )
                log.info(
                    "download.cancelled",
                    msg="Download cancelled. Its temp files were deleted",
                    duration_ms=self._ms_since(started),
                )
            elif isinstance(error, AppError):
                self._failed(running, video, error.code, log, started, error.details)
            else:
                self._failed_unexpectedly(running, video, log, started)
        finally:
            self._files.remove_temp_folder(place.work)

    def _failed_unexpectedly(
        self, job: Job, video: Video, log: FilteringBoundLogger, started: float
    ) -> None:
        log.error(
            "download.failed",
            msg="Download failed with an unexpected error",
            error_code=ErrorCode.INTERNAL.value,
            exc_info=True,
        )
        self._failed(job, video, ErrorCode.INTERNAL, None, started, {})

    def _download(
        self, job: Job, video: Video, place: _Place, log: FilteringBoundLogger
    ) -> DownloadResult:
        """Step 3 and 4: yt-dlp downloads, merges and embeds. Subtitles fail only once."""
        settings = self._settings.current()
        request = DownloadRequest(
            video_id=video.id,
            quality=job.quality,
            work_folder=place.work,
            log_file=self._job_logs / f"{job.id}.log",
            manual_subtitles=settings.embed_subtitles,
            auto_subtitles=settings.auto_subtitles,
        )
        try:
            return self._ask(job, video, request)
        except SubtitlesFailedError as failure:
            log.warning(
                "download.retry",
                msg="The subtitles failed. The video is downloaded again without them",
                reason=str(failure),
            )
            self._files.remove_temp_folder(place.work)
            self._files.make_folder(place.work, inside=place.folder)
            return self._ask(
                job, video, replace(request, manual_subtitles=False, auto_subtitles=False)
            )

    def _ask(self, job: Job, video: Video, request: DownloadRequest) -> DownloadResult:
        def told(progress: DownloadProgress) -> None:
            self._progressed(job, video, progress)

        try:
            return self._youtube.download(
                request, told, lambda: self._is_cancelled(job.id), by_user=True
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
        if self._is_cancelled(job.id):
            raise DownloadCancelledError("cancelled before the file was put in its place")
        name = self._move_into_place(job, video, place, result.file)
        target = place.folder / name
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
        side_files = self._side_files_of(video, name, result)
        try:
            self._verify_dates(target, published, log)
            synced = replace(synced, file_size=self._files.size_of(target))
            done = replace(job, state=JobState.DONE, stage=None, finished_at=self._now())
            # The file is recorded, its marker cleared and its side files kept in one
            # write (R-QA-06). That commit is the point of no return: nothing after it
            # moves, trashes or deletes the file.
            stored = self._store_end(
                done, synced, JobState.DONE, VideoStatus.SYNCED, "verified", side_files
            )
        except BaseException as error:
            if not isinstance(error, Exception):
                raise  # the end of the process: the next start cleans up by the marker
            # Until the video is recorded as synced, a file in the folder must not stay
            # unknown to the app (R-QA-06): it goes back to the temp folder of the job.
            self._files.move(target, place.work / "not-finished.mkv")
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
        dates = self._files.read_dates(target)
        if (dates.created, dates.modified) != (published, published):
            log.error(
                "dates.verify_failed",
                msg="The file dates did not read back as they were set",
                error_code=ErrorCode.DATES_NOT_APPLIED.value,
                expected=published,
                created=dates.created,
                modified=dates.modified,
            )
            raise AppError(
                ErrorCode.DATES_NOT_APPLIED,
                {"expected": str(published), "created": str(dates.created)},
            )
        log.info("dates.applied", msg="File dates set to the published time", published=published)

    # --- side files: the info JSON, the original thumbnail, the thumbnail next to the video

    def _side_files_of(
        self, video: Video, name: str, result: DownloadResult
    ) -> list[tuple[str, bytes]]:
        """The side files of a download: the info JSON, the original thumbnail, the cover."""
        files: list[tuple[str, bytes]] = [
            (f"{HIDDEN_DIR}/{video.id}.info.json", result.info_json.encode())
        ]
        cover = None if result.thumbnail is None else self._files.read_bytes(result.thumbnail)
        if cover is not None:
            files.append((f"{HIDDEN_DIR}/{video.id}.jpg", cover))
            if self._settings.current().thumbnail_next_to_video:
                files.append((str(Path(name).with_suffix(".jpg")), cover))
        return files

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
        """Write the side files that waited (R-MD-02, R-MD-05). One that fails again waits on."""
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
    ) -> None:
        if code is ErrorCode.BOT_CHECK:
            # One condition of the whole app, never one error per video (R-ER-05): the job
            # waits in line until YouTube is asked again.
            self._end(job, video, JobState.WAITING, VideoStatus.QUEUED, "youtube paused")
            self._tell(replace(video, status=VideoStatus.QUEUED))
            if log is not None:
                log.warning(
                    "download.retry",
                    msg="YouTube asked to confirm that the app is not a bot. The download waits",
                    error_code=code.value,
                )
            return
        failed = replace(
            video, last_error_code=code, last_error_at=self._now(), attempts=video.attempts
        )
        self._end(
            replace(job, error_code=code, finished_at=self._now()),
            failed,
            JobState.FAILED,
            VideoStatus.FAILED,
            code.value,
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

    def _end(
        self,
        job: Job,
        video: Video | None,
        state: JobState,
        status: VideoStatus | None,
        reason: str,
    ) -> None:
        """Store how a job ended, with its video and the status change, and tell everyone."""
        self._announce(self._store_end(job, video, state, status, reason))

    def _store_end(
        self,
        job: Job,
        video: Video | None,
        state: JobState,
        status: VideoStatus | None,
        reason: str,
        side_files: Sequence[tuple[str, bytes]] = (),
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
            video = replace(video, placing_file=None)
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
        except Exception:  # noqa: BLE001  (the file is stored: nothing may undo it)
            _log.error(
                "download.tell_failed",
                msg="The interface could not be told about a synced video. The file stays",
                video_id=None if video is None else video.id,
                error_code=ErrorCode.INTERNAL.value,
                exc_info=True,
            )

    def _end_left_over(self, job: Job) -> None:
        """Clean up a job that a quit or a crash left waiting or running (R-QA-06).

        Its temp folder goes. A file it was moving into the channel folder (its
        marker) goes to the Trash, but only when the video ID inside the file
        shows it is this download: a file of the user's is never touched. A
        failure is logged, and the job ends anyway: the start goes on.
        """
        video = self._repository.video(job.video_id)
        channel = None if video is None else self._repository.channel(video.channel_id)
        try:
            if channel is not None and video is not None:
                place = self._place_of(channel, job)
                self._files.remove_temp_folder(place.work)
                if video.placing_file:
                    self._trash_own_download(video, place.folder / video.placing_file)
        except (AppError, OSError, ValueError) as error:
            _log.warning(
                "file.trash_failed",
                msg="A file of an interrupted download could not be cleaned up",
                job_id=job.id,
                video_id=job.video_id,
                error_code=getattr(error, "code", ErrorCode.INTERNAL).value,
            )
        self._end(job, video, JobState.CANCELLED, VideoStatus.NOT_DOWNLOADED, "app quit")
        _log.info(
            "download.cancelled",
            msg="A download that the last quit interrupted was cleaned up",
            job_id=job.id,
            video_id=job.video_id,
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

    def _put_in_line(self, video: Video, reason: str) -> Job:
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
        )
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
        )
        self._tell(queued)
        self._views.publish(channel.id)
        with self._wake:
            self._wake.notify_all()
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

    def _progressed(self, job: Job, video: Video, progress: DownloadProgress) -> None:
        if progress.stage is Stage.PROCESSING:
            video = self._processing(job)
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
        )
        self._state.progressed(told)
        now = self._clock.monotonic()
        last = self._last_told.get(job.id)
        stage_changed = (
            previous is None or previous.stage is not progress.stage or progress.fraction == 1.0
        )
        if last is not None and now - last < PROGRESS_EVERY_S and not stage_changed:
            return
        self._last_told[job.id] = now
        self._events.publish(JobProgressed(told))

    def _tell(self, video: Video) -> None:
        """Tell the interface how a video is now (R-FB-03)."""
        view = self._views.video(video.id)
        if view is not None:
            self._events.publish(VideoUpdated(view))

    def _is_cancelled(self, job_id: str) -> bool:
        with self._wake:
            return self._stopped or job_id in self._cancelled

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
