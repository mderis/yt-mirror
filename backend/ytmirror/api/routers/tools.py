"""The tool endpoints: what the app needs, and "Install now".

Implements the HTTP side of R-IN-03 and R-IN-04. No logic here: the
toolchain service decides.

Tests: backend/tests/api/test_tools.py
"""

from fastapi import APIRouter

from ytmirror.api.schemas import Tool, ToolsResponse
from ytmirror.core.models import ToolName
from ytmirror.services.toolchain import ToolchainService

_ACCEPTED = 202


def build_router(toolchain: ToolchainService) -> APIRouter:
    """Return the router for ``/tools``.

    Args:
        toolchain: The service that knows and installs the tools.

    Returns:
        The router, to be mounted under ``/api``.
    """
    router = APIRouter(tags=["tools"])

    def get_tools() -> ToolsResponse:
        """Return the state of every tool, and whether the first-run screen is needed."""
        return ToolsResponse(
            tools=[Tool.of(report) for report in toolchain.reports()],
            setup_required=toolchain.setup_required(),
        )

    def install_tool(name: ToolName) -> Tool:
        """Start installing a tool in the background and return its state."""
        return Tool.of(toolchain.start_install(name))

    router.add_api_route(
        "/tools", get_tools, methods=["GET"], response_model=ToolsResponse, operation_id="getTools"
    )
    router.add_api_route(
        "/tools/{name}/install",
        install_tool,
        methods=["POST"],
        response_model=Tool,
        status_code=_ACCEPTED,
        operation_id="installTool",
    )
    return router
