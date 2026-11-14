"""The snapshot of the app, and what the window tells the app about itself.

Implements the HTTP side of R-UI-01, R-UI-02 and R-ER-05. No logic here.

Tests: backend/tests/api/test_state.py
"""

from fastapi import APIRouter

from ytmirror.api.catalogue_schemas import OpenChannelRequest, StateResponse
from ytmirror.services.state import StateService
from ytmirror.services.youtube_access import YouTubeAccess


def build_router(state: StateService, youtube: YouTubeAccess) -> APIRouter:
    """Return the router for ``/state`` and ``/youtube``.

    Args:
        state: Builds the snapshot and remembers the open channel.
        youtube: The access to YouTube, for ending its pause.

    Returns:
        The router, to be mounted under ``/api``.
    """
    router = APIRouter(tags=["state"])

    def get_state() -> StateResponse:
        """Return the app as it is right now. The window asks when it connects."""
        return StateResponse.of(state.snapshot())

    def set_open_channel(body: OpenChannelRequest) -> StateResponse:
        """Remember which channel the user has open, for the next start (R-UI-02)."""
        state.open_channel(body.channel_id)
        return StateResponse.of(state.snapshot())

    def try_youtube_now() -> StateResponse:
        """End the pause of the app and take up the work that waited (R-ER-05)."""
        youtube.try_now()
        return StateResponse.of(state.snapshot())

    router.add_api_route(
        "/state", get_state, methods=["GET"], response_model=StateResponse, operation_id="getState"
    )
    router.add_api_route(
        "/state/open-channel",
        set_open_channel,
        methods=["PUT"],
        response_model=StateResponse,
        operation_id="setOpenChannel",
    )
    router.add_api_route(
        "/youtube/try-now",
        try_youtube_now,
        methods=["POST"],
        response_model=StateResponse,
        operation_id="tryYouTubeNow",
    )
    return router
