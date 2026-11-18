"""The bridge endpoints: the interface reports its state, and confirms a quit.

Implements the HTTP side of D-094 and R-QU-12 (docs/ARCHITECTURE.md
sections 7.10 and 8). No logic here.

Tests: backend/tests/api/test_ui.py
"""

from fastapi import APIRouter
from starlette.responses import Response

from ytmirror.api.ui_schemas import UiStateRequest
from ytmirror.services.ui_bridge import UiBridge

_NO_CONTENT = 204


def build_router(bridge: UiBridge) -> APIRouter:
    """Return the router for the bridge.

    Args:
        bridge: Keeps the state and decides about a quit.

    Returns:
        The router, to be mounted under ``/api``.
    """
    router = APIRouter(tags=["ui"])

    def report_state(body: UiStateRequest) -> Response:
        """Tell the app what applies now, so the menu bar is enabled from it (R-NA-04)."""
        bridge.report(body.to_state())
        return Response(status_code=_NO_CONTENT)

    def confirm_quit() -> Response:
        """Quit although downloads run: the user chose "Quit" in the question (R-QU-12)."""
        bridge.confirm_quit()
        return Response(status_code=_NO_CONTENT)

    router.add_api_route(
        "/ui/state",
        report_state,
        methods=["PUT"],
        operation_id="reportUiState",
        status_code=_NO_CONTENT,
        response_class=Response,
    )
    router.add_api_route(
        "/ui/quit",
        confirm_quit,
        methods=["POST"],
        operation_id="confirmQuit",
        status_code=_NO_CONTENT,
        response_class=Response,
    )
    return router
