"""The queue endpoints: the whole queue, pause all, resume all, reorder, clear waiting.

Implements the HTTP side of R-QU-02 (docs/ARCHITECTURE.md section 8). Cancel
and "Mirror first" are in the videos router. No logic here.

Tests: backend/tests/api/test_queue.py
"""

from fastapi import APIRouter
from starlette.responses import Response

from ytmirror.api.catalogue_schemas import (
    ClearWaitingResponse,
    Queue,
    QueueResponse,
    ReorderRequest,
    SpeedLimitRequest,
    TryFolderResponse,
)
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.models import SPEED_LIMITS_MBPS
from ytmirror.services.downloader import DownloaderService
from ytmirror.services.queue import QueueService

_NO_CONTENT = 204


def build_router(queue: QueueService, downloader: DownloaderService) -> APIRouter:
    """Return the router for the queue.

    Args:
        queue: Builds the view of the queue.
        downloader: Changes the queue.

    Returns:
        The router, to be mounted under ``/api``.
    """
    router = APIRouter(tags=["queue"])

    def get_queue() -> QueueResponse:
        """Return every download that runs or waits, in its order, and the failed videos."""
        return QueueResponse.of(queue.view())

    def pause() -> Queue:
        """Pause all downloads (R-QU-02)."""
        downloader.pause_all()
        return Queue.of(downloader.queue_summary())

    def resume() -> Queue:
        """Resume all downloads (R-QU-02)."""
        downloader.resume_all()
        return Queue.of(downloader.queue_summary())

    def reorder(body: ReorderRequest) -> Response:
        """Put the waiting downloads in the given order (R-QU-02)."""
        downloader.reorder(body.job_ids)
        return Response(status_code=_NO_CONTENT)

    def clear_waiting() -> ClearWaitingResponse:
        """Remove every download that waits from the line (R-QU-02)."""
        return ClearWaitingResponse(removed=downloader.clear_waiting())

    def speed_limit(body: SpeedLimitRequest) -> Queue:
        """Change the limit of all downloads together (R-QU-03)."""
        if body.mbps not in SPEED_LIMITS_MBPS:
            raise AppError(ErrorCode.INVALID_REQUEST, {"mbps": str(body.mbps)})
        downloader.set_speed_limit(body.mbps)
        return Queue.of(downloader.queue_summary())

    def resume_anyway() -> Queue:
        """Resume the queue that the disk space guard paused (R-QU-10)."""
        downloader.resume_anyway()
        return Queue.of(downloader.queue_summary())

    def try_folder_again(channel_id: str) -> TryFolderResponse:
        """Look again whether the folder of a channel can be reached (R-QU-11)."""
        return TryFolderResponse(available=downloader.try_folder_again(channel_id))

    router.add_api_route(
        "/queue", get_queue, methods=["GET"], response_model=QueueResponse, operation_id="getQueue"
    )
    router.add_api_route(
        "/queue/pause", pause, methods=["POST"], response_model=Queue, operation_id="pauseQueue"
    )
    router.add_api_route(
        "/queue/resume", resume, methods=["POST"], response_model=Queue, operation_id="resumeQueue"
    )
    router.add_api_route(
        "/queue/reorder",
        reorder,
        methods=["POST"],
        status_code=_NO_CONTENT,
        response_class=Response,
        operation_id="reorderQueue",
    )
    router.add_api_route(
        "/queue/clear-waiting",
        clear_waiting,
        methods=["POST"],
        response_model=ClearWaitingResponse,
        operation_id="clearWaiting",
    )
    router.add_api_route(
        "/queue/speed-limit",
        speed_limit,
        methods=["POST"],
        response_model=Queue,
        operation_id="setSpeedLimit",
    )
    router.add_api_route(
        "/queue/resume-anyway",
        resume_anyway,
        methods=["POST"],
        response_model=Queue,
        operation_id="resumeAnyway",
    )
    router.add_api_route(
        "/queue/folders/{channel_id}/try-again",
        try_folder_again,
        methods=["POST"],
        response_model=TryFolderResponse,
        operation_id="tryFolderAgain",
    )
    return router
