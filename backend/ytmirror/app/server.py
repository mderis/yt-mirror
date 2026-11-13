"""Runs the HTTP server in a background thread.

The window needs the main thread on macOS, so the server gets its own. The
server listens on 127.0.0.1 only (R-PL-04). This module must not know what
the app serves.

Tests: backend/tests/integration/app/test_server.py
"""

import socket
import threading
import time

import structlog
import uvicorn
from starlette.types import ASGIApp
from structlog.typing import FilteringBoundLogger

from ytmirror.core.errors import ErrorCode

_log: FilteringBoundLogger = structlog.get_logger(__name__)

LOCAL_ADDRESS = "127.0.0.1"
_START_TIMEOUT_S = 15.0
_STOP_TIMEOUT_S = 10.0
_POLL_S = 0.01


def bind_local_socket(port: int | None) -> socket.socket:
    """Open a listening socket on 127.0.0.1.

    The socket is bound before the app is built because the security policy
    needs to know the port.

    Args:
        port: A fixed port, or None for any free port.

    Returns:
        The bound socket. Its port is ``sock.getsockname()[1]``.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((LOCAL_ADDRESS, port or 0))
    return sock


class BackgroundServer:
    """Serves an ASGI app on an already bound socket, in its own thread."""

    def __init__(self, app: ASGIApp, sock: socket.socket) -> None:
        """Create the server. It does not start yet.

        Args:
            app: The ASGI app to serve.
            sock: A socket from ``bind_local_socket``.
        """
        self._sock = sock
        self._port: int = sock.getsockname()[1]
        config = uvicorn.Config(app, log_config=None, access_log=False, lifespan="off")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._run, name="http-server", daemon=True)
        self._error: BaseException | None = None

    @property
    def url(self) -> str:
        """The address of the server, without a trailing slash."""
        return f"http://{LOCAL_ADDRESS}:{self._port}"

    def start(self) -> None:
        """Start serving and return when the server accepts requests.

        Raises:
            RuntimeError: When the server does not come up.
        """
        self._thread.start()
        deadline = time.monotonic() + _START_TIMEOUT_S
        while not self._server.started:
            if self._error is not None or not self._thread.is_alive():
                raise RuntimeError("The HTTP server stopped while starting") from self._error
            if time.monotonic() > deadline:
                raise RuntimeError("The HTTP server did not start in time")
            time.sleep(_POLL_S)

    def stop(self) -> None:
        """Stop serving and wait for the thread to end."""
        self._server.should_exit = True
        self._thread.join(timeout=_STOP_TIMEOUT_S)

    def _run(self) -> None:
        try:
            self._server.run(sockets=[self._sock])
        except BaseException as error:  # noqa: BLE001  (thread boundary: kept for start(), logged below)
            self._error = error
            if self._server.started:
                _log.error(
                    "app.crashed",
                    msg="The HTTP server stopped because of an unexpected error",
                    error_code=ErrorCode.INTERNAL.value,
                    exc_info=error,
                )
