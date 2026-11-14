"""Builds the FastAPI app: routes, security, error mapping and the interface files.

This module wires the HTTP layer together and must not contain business
logic. Which services exist is decided in ``app/container.py``.

Tests: backend/tests/api/
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from starlette.responses import FileResponse, RedirectResponse, Response
from starlette.staticfiles import StaticFiles

from ytmirror import __version__
from ytmirror.api import sse
from ytmirror.api.errors import error_response, install_error_handlers
from ytmirror.api.request_log import RequestLogMiddleware
from ytmirror.api.routers import channels, health, state, tools, videos
from ytmirror.api.schemas import ErrorResponse
from ytmirror.api.security import API_PREFIX, SESSION_COOKIE, SecurityMiddleware, SecurityPolicy
from ytmirror.core.errors import ErrorCode
from ytmirror.ports.clock import Clock
from ytmirror.services.catalogue import CatalogueService
from ytmirror.services.channel_views import ChannelViews
from ytmirror.services.channels import ChannelsService
from ytmirror.services.diagnostics import DiagnosticsService
from ytmirror.services.events import EventBus
from ytmirror.services.state import StateService
from ytmirror.services.thumbnails import ThumbnailService
from ytmirror.services.toolchain import ToolchainService
from ytmirror.services.youtube_access import YouTubeAccess

LOCAL_FRONTEND = "/"


@dataclass(frozen=True, slots=True)
class ApiConfig:
    """What the HTTP layer needs to know about this run.

    Attributes:
        security: The security policy.
        frontend_dir: The folder with the built interface.
        frontend_url: Where the interface is served: ``/`` normally, the address
            of the development server in ``--dev`` mode.
        favicon_svg: The app icon as SVG text, coloured from the tokens, or None
            when the icon source is not there (docs/DECISIONS.md D-064).
        favicon_png: Draws the same icon as PNG, for browsers that take no SVG icon.
    """

    security: SecurityPolicy
    frontend_dir: Path
    frontend_url: str = LOCAL_FRONTEND
    favicon_svg: str | None = None
    favicon_png: Callable[[], bytes] | None = None


@dataclass(frozen=True, slots=True)
class ApiServices:
    """The services the HTTP layer talks to.

    Attributes:
        diagnostics: Behind the health endpoint.
        toolchain: Behind the tool endpoints.
        events: The bus whose events the event stream passes on.
        state: Behind the snapshot of the app.
        youtube: The access to YouTube, for ending its pause.
        channels: Behind the channel endpoints.
        catalogue: Runs the checks.
        views: The channels and videos as the interface shows them.
        thumbnails: The cached pictures.
    """

    diagnostics: DiagnosticsService
    toolchain: ToolchainService
    events: EventBus
    state: StateService
    youtube: YouTubeAccess
    channels: ChannelsService
    catalogue: CatalogueService
    views: ChannelViews
    thumbnails: ThumbnailService


def create_app(config: ApiConfig, services: ApiServices, clock: Clock) -> FastAPI:
    """Return the FastAPI app.

    Args:
        config: Security policy and interface location.
        services: The services behind the endpoints.
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
    app.include_router(health.build_router(services.diagnostics), prefix=API_PREFIX)
    app.include_router(tools.build_router(services.toolchain), prefix=API_PREFIX)
    app.include_router(
        sse.build_router(services.events, services.toolchain.setup_required), prefix=API_PREFIX
    )
    app.include_router(state.build_router(services.state, services.youtube), prefix=API_PREFIX)
    app.include_router(
        channels.build_router(
            services.channels, services.catalogue, services.views, services.thumbnails
        ),
        prefix=API_PREFIX,
    )
    app.include_router(videos.build_router(services.views, services.thumbnails), prefix=API_PREFIX)
    _add_favicon(app, config)
    _add_frontend(app, config)
    install_error_handlers(app)
    # The middleware added last runs first: the request log wraps the security checks.
    app.add_middleware(SecurityMiddleware, policy=config.security)
    app.add_middleware(RequestLogMiddleware, clock=clock)
    return app


def _add_favicon(app: FastAPI, config: ApiConfig) -> None:
    """Serve the app icon, made from the icon source file (docs/DESIGN.md section 5, D-064)."""
    drawn: list[bytes] = []

    def favicon_svg() -> Response:
        if config.favicon_svg is None:
            return error_response(ErrorCode.NOT_FOUND, {"missing": "the icon source"})
        return Response(
            config.favicon_svg, media_type="image/svg+xml", headers={"Cache-Control": "no-cache"}
        )

    def favicon_png() -> Response:
        if config.favicon_png is None:
            return error_response(ErrorCode.NOT_FOUND, {"missing": "the icon source"})
        if not drawn:
            drawn.append(config.favicon_png())
        return Response(drawn[0], media_type="image/png", headers={"Cache-Control": "no-cache"})

    app.add_api_route("/favicon.svg", favicon_svg, methods=["GET"], include_in_schema=False)
    app.add_api_route("/favicon.png", favicon_png, methods=["GET"], include_in_schema=False)


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
