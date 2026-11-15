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

import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

import structlog
from structlog.typing import FilteringBoundLogger

from ytmirror.core.channels import Channel, Video, VideoStatus
from ytmirror.core.dates import published_time
from ytmirror.core.errors import AppError, ErrorCode, ErrorKind
from ytmirror.core.jobs import (
    ACTIVE_STATES,
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
from ytmirror.core.media import verification_problem
from ytmirror.core.naming import HIDDEN_DIR, TEMP_DIR, video_file_name
from ytmirror.core.quality import effective_quality
from ytmirror.core.status import StatusChange, change_status
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
        self._workers = workers
        self._wake = threading.Condition()
        self._running: dict[str, str] = {}
        """The jobs that run, with the channel of each."""
        self._videos: dict[str, Video] = {}
        """The video of each running job, as it is now."""
        self._cancelled: set[str] = set()
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
            self._end_left_over(job)
        self._youtube.when_asking_again(self._wake_up)
        for _ in range(self._workers):
            self._run_in_background(self._work_until_stopped)

    def _wake_up(self) -> None:
        with self._wake:
            self._wake.notify_all()

    def stop(self, wait_s: float = 10.0) -> None:
        """Stop: a running download is cancelled and cleaned up before this returns.

        Args:
            wait_s: How long to wait for a running download to end. A running
                ffmpeg step is not interrupted, so this can take a moment.
        """
        with self._wake:
            self._stopped = True
            self._wake.notify_all()
            self._wake.wait_for(lambda: not self._running, timeout=wait_s)

    def _work_until_stopped(self) -> None:  # pragma: no cover  (a thread. Tests use work_once)
        while True:
            with self._wake:
                self._wake.wait_for(lambda: self._stopped or self._has_waiting())
                if self._stopped:
                    return
            self.work_once()

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
        finally:
            with self._wake:
                self._running.pop(job.id, None)
                self._videos.pop(job.id, None)
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
        video = self._known(video_id)
        if video.status is not VideoStatus.FAILED:
            raise AppError(ErrorCode.INVALID_REQUEST, {"video": video_id, "status": video.status})
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
        with self._wake:
            job = self._jobs.job(job_id)
            if job is None or job.state not in ACTIVE_STATES:
                return False
            if job.id in self._running:
                self._cancelled.add(job.id)
                return True
            video = self._repository.video(job.video_id)
            self._end(job, video, JobState.CANCELLED, VideoStatus.NOT_DOWNLOADED, "cancelled")
        _log.info(
            "download.cancelled",
            msg="Download cancelled before it started",
            job_id=job_id,
            video_id=job.video_id,
        )
        return True

    def cancel_channel(self, channel_id: str, wait_s: float = 30.0) -> None:
        """Cancel every download of a channel, and wait until none of them runs (R-CH-32).

        Args:
            channel_id: The channel.
            wait_s: How long to wait for a running download to end.
        """
        for job in self._jobs.jobs(ACTIVE_STATES):
            video = self._repository.video(job.video_id)
            if video is not None and video.channel_id == channel_id:
                self.cancel(job.id)
        with self._wake:
            self._wake.wait_for(lambda: channel_id not in self._running.values(), timeout=wait_s)

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
        started = self._clock.monotonic()
        log.info("download.started", msg="Download started", quality=job.quality.value)
        running = replace(job, state=JobState.RUNNING, stage=Stage.VIDEO, started_at=self._now())
        video = self._change(running, video, VideoStatus.DOWNLOADING, "started")
        self._videos[job.id] = video
        try:
            self._files.make_folder(place.work)
            result = self._download(running, video, place, log)
            video = self._processing(running)
            self._finish(running, video, channel, place, result, log, started)
        except DownloadCancelledError:
            self._end(running, video, JobState.CANCELLED, VideoStatus.NOT_DOWNLOADED, "cancelled")
            log.info(
                "download.cancelled",
                msg="Download cancelled. Its temp files were deleted",
                duration_ms=self._ms_since(started),
            )
        except AppError as error:
            self._failed(running, video, error.code, log, started, error.details)
        except Exception:
            log.error(
                "download.failed",
                msg="Download failed with an unexpected error",
                error_code=ErrorCode.INTERNAL.value,
                exc_info=True,
            )
            self._failed(running, video, ErrorCode.INTERNAL, None, started, {})
        finally:
            self._files.remove_temp_folder(place.work)

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
            self._files.make_folder(place.work)
            return self._ask(
                job, video, replace(request, manual_subtitles=False, auto_subtitles=False)
            )

    def _ask(self, job: Job, video: Video, request: DownloadRequest) -> DownloadResult:
        def told(progress: DownloadProgress) -> None:
            self._progressed(job, video, progress)

        return self._youtube.download(
            request, told, lambda: self._is_cancelled(job.id), by_user=True
        )

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
        self._files.write_file(
            place.hidden / f"{video.id}.info.json", result.info_json.encode(), overwrite=True
        )
        cover = None if result.thumbnail is None else self._files.read_bytes(result.thumbnail)
        if cover is not None:
            self._files.write_file(place.hidden / f"{video.id}.jpg", cover, overwrite=True)
        if self._is_cancelled(job.id):
            raise DownloadCancelledError("cancelled before the file was put in its place")
        name = self._move_into_place(video, place, result.file)
        target = place.folder / name
        try:
            self._apply_dates(target, published, log)
        except AppError:
            # A file with wrong dates must not look finished (R-QA-06): back to the temp folder.
            self._files.move(target, place.work / "dates-not-applied.mkv")
            raise
        if cover is not None and self._settings.current().thumbnail_next_to_video:
            self._put_cover_next_to(place, name, cover, published)
        synced = replace(
            video,
            file_name=name,
            file_size=self._files.size_of(target),
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
        done = replace(job, state=JobState.DONE, stage=None, finished_at=self._now())
        self._end(done, synced, JobState.DONE, VideoStatus.SYNCED, "verified")
        log.info(
            "download.finished",
            msg="Download finished",
            file_size=synced.file_size,
            height=facts.height,
            subtitles=synced.has_subtitles,
            duration_ms=self._ms_since(started),
        )

    def _move_into_place(self, video: Video, place: _Place, file: Path) -> str:
        """Step 2 and 7: choose the name and move the file in one step, never overwriting."""
        for _ in range(2):
            taken = [
                *self._files.file_names(place.folder),
                *(
                    other.file_name
                    for other in self._repository.videos(video.channel_id)
                    if other.id != video.id and other.file_name
                ),
            ]
            name = video_file_name(video.title, video.id, taken)
            if self._files.move(file, place.folder / name):
                _log.info("file.moved", msg="File moved into its place", file=name)
                return name
        raise AppError(ErrorCode.INTERNAL, {"reason": "the name was taken twice while moving"})

    def _apply_dates(self, target: Path, published: int, log: FilteringBoundLogger) -> None:
        """Step 8: set both dates to the published time, and read them back (R-DT-07)."""
        self._files.set_dates(target, published)
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

    def _put_cover_next_to(self, place: _Place, name: str, cover: bytes, published: int) -> None:
        """Save the thumbnail next to the video when the setting asks for it (R-MD-05)."""
        cover_name = str(Path(name).with_suffix(".jpg"))
        staged = place.work / "cover.jpg"
        self._files.write_file(staged, cover, overwrite=True)
        if self._files.move(staged, place.folder / cover_name):
            self._files.set_dates(place.folder / cover_name, published)

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
        ended = replace(
            job,
            state=state,
            stage=None,
            finished_at=None if state is JobState.WAITING else self._now(),
        )
        change: StatusChange | None = None
        if video is not None and status is not None and video.status is not status:
            current = self._repository.video(video.id)
            stored = current.status if current is not None else video.status
            change = change_status(video.id, stored, status, reason)
            video = replace(video, status=status)
        self._jobs.record(ended, video, change)
        if state is JobState.WAITING:
            return
        if video is not None:
            self._state.ended(video.id)
            self._tell(video)
            self._views.publish(video.channel_id)

    def _end_left_over(self, job: Job) -> None:
        """Clean up a job that a quit left waiting or running."""
        video = self._repository.video(job.video_id)
        channel = None if video is None else self._repository.channel(video.channel_id)
        if channel is not None:
            self._files.remove_temp_folder(self._place_of(channel, job).work)
        self._end(job, video, JobState.CANCELLED, VideoStatus.NOT_DOWNLOADED, "app quit")
        _log.info(
            "download.cancelled",
            msg="A download that the last quit interrupted was cleaned up",
            job_id=job.id,
            video_id=job.video_id,
        )

    # --- helpers

    def _put_in_line(self, video: Video, reason: str) -> Job:
        channel = self._repository.channel(video.channel_id)
        if channel is None:
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
