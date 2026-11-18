"""The catalogue endpoints: the videos of a channel, their thumbnails, and their downloads.

Implements the HTTP side of R-CH-10 and R-CH-16, and from milestone M3 of
R-MI-01 (Mirror), R-UI-08 (details), R-UI-10 (Play, Show in Finder), R-QU-02
(Cancel) and R-QU-08 (Retry). File operations take video IDs, never paths
(ARCHITECTURE section 8). No logic here.

Tests: backend/tests/api/test_videos.py
"""

from fastapi import APIRouter
from starlette.responses import Response

from ytmirror.api.catalogue_schemas import (
    CancelJobResponse,
    MirrorRequest,
    MirrorResponse,
    QueuedJob,
    Video,
    VideoDetailsResponse,
    VideosResponse,
)
from ytmirror.api.pictures import picture_response
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.services.channel_views import ChannelViews
from ytmirror.services.downloader import DownloaderService
from ytmirror.services.thumbnails import ThumbnailService

_ACCEPTED = 202
_NO_CONTENT = 204


def build_router(
    views: ChannelViews, thumbnails: ThumbnailService, downloader: DownloaderService
) -> APIRouter:
    """Return the router for the catalogue.

    Args:
        views: The catalogue as the interface shows it.
        thumbnails: The cached pictures.
        downloader: Puts videos in line and downloads them.

    Returns:
        The router, to be mounted under ``/api``.
    """
    router = APIRouter(tags=["videos"])

    def get_channel_videos(channel_id: str) -> VideosResponse:
        """Return the catalogue of a channel: every video, with the fields a list needs."""
        return VideosResponse(videos=[Video.of(view) for view in views.videos(channel_id)])

    def get_thumbnail(video_id: str) -> Response:
        """Return the cached thumbnail of a video (R-CH-16)."""
        return picture_response(thumbnails.thumbnail(video_id), "the thumbnail of this video")

    def mirror(body: MirrorRequest) -> MirrorResponse:
        """Put videos in line to be downloaded, in the order given (R-MI-01)."""
        jobs = downloader.mirror(body.ids, first=body.first)
        return MirrorResponse(
            jobs=[QueuedJob(job_id=job.id, video_id=job.video_id) for job in jobs]
        )

    def redownload(body: MirrorRequest) -> MirrorResponse:
        """Download synced videos again; each file is replaced once the new one is verified."""
        jobs = downloader.redownload(body.ids)
        return MirrorResponse(
            jobs=[QueuedJob(job_id=job.id, video_id=job.video_id) for job in jobs]
        )

    def get_video(video_id: str) -> VideoDetailsResponse:
        """Return everything the details panel shows of a video (R-UI-08)."""
        return VideoDetailsResponse.of(downloader.details(video_id))

    def retry(video_id: str) -> Video:
        """Put a failed video in line again (R-QU-08)."""
        downloader.retry(video_id)
        view = views.video(video_id)
        if view is None:
            raise AppError(ErrorCode.NOT_FOUND, {"video": video_id})
        return Video.of(view)

    def cancel_job(job_id: str) -> CancelJobResponse:
        """Cancel a download that waits or runs (R-QU-02)."""
        return CancelJobResponse(cancelled=downloader.cancel(job_id))

    def play(video_id: str) -> Response:
        """Open the file of a video in the default player of macOS (R-UI-10)."""
        downloader.play(video_id)
        return Response(status_code=_NO_CONTENT)

    def reveal(video_id: str) -> Response:
        """Show the file of a video selected in Finder (R-UI-10)."""
        downloader.reveal(video_id)
        return Response(status_code=_NO_CONTENT)

    router.add_api_route(
        "/videos/mirror",
        mirror,
        methods=["POST"],
        response_model=MirrorResponse,
        status_code=_ACCEPTED,
        operation_id="mirrorVideos",
    )
    router.add_api_route(
        "/videos/redownload",
        redownload,
        methods=["POST"],
        response_model=MirrorResponse,
        status_code=_ACCEPTED,
        operation_id="redownloadVideos",
    )
    router.add_api_route(
        "/videos/{video_id}",
        get_video,
        methods=["GET"],
        response_model=VideoDetailsResponse,
        operation_id="getVideo",
    )
    router.add_api_route(
        "/videos/{video_id}/retry",
        retry,
        methods=["POST"],
        response_model=Video,
        status_code=_ACCEPTED,
        operation_id="retryVideo",
    )
    router.add_api_route(
        "/jobs/{job_id}/cancel",
        cancel_job,
        methods=["POST"],
        response_model=CancelJobResponse,
        operation_id="cancelJob",
    )
    for path, action, operation in (
        ("/videos/{video_id}/play", play, "playVideo"),
        ("/videos/{video_id}/reveal", reveal, "revealVideo"),
    ):
        router.add_api_route(
            path,
            action,
            methods=["POST"],
            status_code=_NO_CONTENT,
            response_class=Response,
            operation_id=operation,
        )
    router.add_api_route(
        "/channels/{channel_id}/videos",
        get_channel_videos,
        methods=["GET"],
        response_model=VideosResponse,
        operation_id="getChannelVideos",
    )
    router.add_api_route(
        "/videos/{video_id}/thumbnail",
        get_thumbnail,
        methods=["GET"],
        response_class=Response,
        operation_id="getVideoThumbnail",
    )
    return router
