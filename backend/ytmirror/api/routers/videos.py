"""The catalogue endpoints: the videos of a channel and their thumbnails.

Implements the HTTP side of R-CH-10 and R-CH-16. No logic here.

Tests: backend/tests/api/test_videos.py
"""

from fastapi import APIRouter
from starlette.responses import Response

from ytmirror.api.catalogue_schemas import Video, VideosResponse
from ytmirror.api.pictures import picture_response
from ytmirror.services.channel_views import ChannelViews
from ytmirror.services.thumbnails import ThumbnailService


def build_router(views: ChannelViews, thumbnails: ThumbnailService) -> APIRouter:
    """Return the router for the catalogue.

    Args:
        views: The catalogue as the interface shows it.
        thumbnails: The cached pictures.

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
