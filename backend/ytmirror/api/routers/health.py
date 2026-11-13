"""The health endpoint: tells that the server runs, and which versions it has.

Tests: backend/tests/api/test_health.py
"""

from fastapi import APIRouter

from ytmirror.api.schemas import HealthResponse
from ytmirror.services.diagnostics import DiagnosticsService


def build_router(diagnostics: DiagnosticsService) -> APIRouter:
    """Return the router for ``/health``.

    Args:
        diagnostics: The service that knows the versions.

    Returns:
        The router, to be mounted under ``/api``.
    """
    router = APIRouter(tags=["health"])

    def get_health() -> HealthResponse:
        """Return the app version and the database schema version."""
        health = diagnostics.health()
        return HealthResponse(
            status="ok", version=health.version, schema_version=health.schema_version
        )

    router.add_api_route(
        "/health",
        get_health,
        methods=["GET"],
        response_model=HealthResponse,
        operation_id="getHealth",
    )
    return router
