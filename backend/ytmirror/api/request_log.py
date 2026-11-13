"""Logs every request and turns unhandled exceptions into the INTERNAL error.

This is the task boundary of the HTTP layer: the one place where a broad
``except`` is allowed (docs/CODING-STANDARDS.md section 3). The exception is
logged here once, with its stack trace, and never anywhere else.

Tests: backend/tests/api/test_request_log.py
"""

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from structlog.typing import FilteringBoundLogger

from ytmirror.api.errors import error_response
from ytmirror.core.errors import ErrorCode
from ytmirror.ports.clock import Clock

_log: FilteringBoundLogger = structlog.get_logger(__name__)


class RequestLogMiddleware:
    """Writes ``api.request`` for every request and ``api.error`` for a crash."""

    def __init__(self, app: ASGIApp, clock: Clock) -> None:
        """Create the middleware.

        Args:
            app: The next ASGI app.
            clock: Used to measure the duration of a request.
        """
        self._app = app
        self._clock = clock

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle one request."""
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        started = self._clock.monotonic()
        method: str = scope["method"]
        path: str = scope["path"]
        status = 0

        async def send_and_note_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self._app(scope, receive, send_and_note_status)
        except Exception:  # noqa: BLE001  (task boundary: log once and answer INTERNAL)
            _log.error(
                "api.error",
                msg="Unhandled error in a request",
                error_code=ErrorCode.INTERNAL.value,
                method=method,
                path=path,
                exc_info=True,
            )
            if status == 0:
                await error_response(ErrorCode.INTERNAL)(scope, receive, send_and_note_status)
        _log.debug(
            "api.request",
            msg="Request handled",
            method=method,
            path=path,
            status=status,
            duration_ms=round((self._clock.monotonic() - started) * 1000),
        )
