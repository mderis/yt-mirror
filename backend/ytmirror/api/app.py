"""Builds the FastAPI app: routes, security, error mapping and the interface files.

This module wires the HTTP layer together and must not contain business
logic. Which services exist is decided in ``app/container.py``.

Tests: backend/tests/api/
"""

from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from starlette.responses import FileResponse, RedirectResponse, Response
from starlette.staticfiles import StaticFiles

from ytmirror import __version__
from ytmirror.api.errors import error_response, install_error_handlers
from ytmirror.api.request_log import RequestLogMiddleware
from ytmirror.api.routers import health
from ytmirror.api.schemas import ErrorResponse
from ytmirror.api.security import API_PREFIX, SESSION_COOKIE, SecurityMiddleware, SecurityPolicy
from ytmirror.core.errors import ErrorCode
from ytmirror.ports.clock import Clock
from ytmirror.services.diagnostics import DiagnosticsService

LOCAL_FRONTEND = "/"


@dataclass(frozen=True, slots=True)
class ApiConfig:
    """What the HTTP layer needs to know about this run.

    Attributes:
        security: The security policy.
        frontend_dir: The folder with the built interface.
        frontend_url: Where the interface is served: ``/`` normally, the address
            of the development server in ``--dev`` mode.
    """

    security: SecurityPolicy
    frontend_dir: Path
    frontend_url: str = LOCAL_FRONTEND


def create_app(config: ApiConfig, diagnostics: DiagnosticsService, clock: Clock) -> FastAPI:
    """Return the FastAPI app.

    Args:
        config: Security policy and interface location.
        diagnostics: The service behind the health endpoint.
        clock: Used to measure request durations.

    Returns:
        The app, ready to be served.
    """
    app = FastAPI(
        title="yt-mirror",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        responses={
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
        },
    )
    app.include_router(health.build_router(diagnostics), prefix=API_PREFIX)
    _add_frontend(app, config)
    install_error_handlers(app)
    # The middleware added last runs first: the request log wraps the security checks.
    app.add_middleware(SecurityMiddleware, policy=config.security)
    app.add_middleware(RequestLogMiddleware, clock=clock)
    return app


def _add_frontend(app: FastAPI, config: ApiConfig) -> None:
    """Serve the interface and exchange the token of the first URL for the session cookie."""
    index_file = config.frontend_dir / "index.html"
    serves_frontend_itself = config.frontend_url == LOCAL_FRONTEND

    def open_frontend(token: str | None = None) -> Response:
        if token is not None:
            if not config.security.token_matches(token):
                return error_response(ErrorCode.UNAUTHORIZED)
            response = RedirectResponse(config.frontend_url, status_code=303)
            response.set_cookie(
                SESSION_COOKIE, config.security.token, httponly=True, samesite="strict", path="/"
            )
            return response
        if not serves_frontend_itself:
            return RedirectResponse(config.frontend_url, status_code=303)
        if not index_file.is_file():
            return error_response(ErrorCode.NOT_FOUND, {"missing": "the built interface"})
        return FileResponse(index_file, headers={"Cache-Control": "no-cache"})

    app.add_api_route("/", open_frontend, methods=["GET"], include_in_schema=False)
    if serves_frontend_itself:
        files = StaticFiles(directory=config.frontend_dir, check_dir=False)
        app.mount("/", files, name="frontend")
