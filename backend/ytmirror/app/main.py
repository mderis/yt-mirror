"""The entry point of yt-mirror: ``python -m ytmirror.app.main``.

``./start`` prepares the environment and then runs this module. It reads the
options, builds the container, brings the database up to date, starts the
HTTP server in a thread and shows the window on the main thread. When the
window closes, the app stops (docs/DECISIONS.md D-020).

This module must not contain rules. It only orders the steps of a run.

Tests: backend/tests/integration/app/test_main.py
"""

import os
import secrets
import signal
import sys
import threading
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from types import FrameType
from typing import TextIO

import structlog
from structlog.typing import FilteringBoundLogger

from ytmirror.api.app import LOCAL_FRONTEND, ApiConfig, create_app
from ytmirror.api.security import SecurityPolicy
from ytmirror.app.config import AppPaths, RunOptions, parse_options, resolve_paths
from ytmirror.app.container import Container, build_container
from ytmirror.app.doctor import run_doctor
from ytmirror.app.logging_setup import (
    SecretRedactor,
    configure_logging,
    new_run_id,
    remove_old_logs,
    set_verbose,
)
from ytmirror.app.server import BackgroundServer, bind_local_socket
from ytmirror.app.window import open_window
from ytmirror.core.errors import ErrorCode
from ytmirror.core.models import LogDetail

_log: FilteringBoundLogger = structlog.get_logger(__name__)

EXIT_OK = 0
EXIT_USAGE = 2
_TOKEN_BYTES = 32

UPDATE_NOT_AVAILABLE = (
    "Updating from inside yt-mirror is not available yet.\n"
    "If you run from a clone, update it with: git pull\n"
)
BROWSER_HINT = "yt-mirror is open in your browser. Press Ctrl+C here to quit.\n"

type Wait = Callable[[str], None]
"""Shows the app at the given address and returns when the app should stop."""


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    """Run yt-mirror once.

    Args:
        argv: The command line arguments without the program name. Default: the real ones.
        env: The environment variables. Default: the real ones.

    Returns:
        The process exit code.
    """
    used_env = os.environ if env is None else env
    options = parse_options(sys.argv[1:] if argv is None else argv, used_env)
    if options.update:
        sys.stderr.write(UPDATE_NOT_AVAILABLE)
        return EXIT_USAGE
    paths = resolve_paths(used_env)
    container = build_container(paths)
    if options.doctor:
        return run_doctor(container.diagnostics, sys.stdout)
    return run_app(options, paths, container, wait=choose_wait(options), console=sys.stderr)


def choose_wait(options: RunOptions) -> Wait:
    """Return how this run shows the app: window, browser, or nothing.

    Implements R-PL-02.

    Args:
        options: The options of this run.

    Returns:
        A function that shows the app and returns when the app should stop.
    """
    if options.no_window:
        return lambda _url: wait_for_stop_signal()
    if options.browser:
        return _wait_in_browser
    return lambda url: open_window(url, debug=options.debug)


def run_app(
    options: RunOptions,
    paths: AppPaths,
    container: Container,
    *,
    wait: Wait,
    console: TextIO | None,
) -> int:
    """Start the server, show the app, and stop when ``wait`` returns.

    Args:
        options: The options of this run.
        paths: Where the parts of this installation are.
        container: The wired adapters and services.
        wait: Shows the app at a given address and returns when the app should stop.
        console: Where readable log lines go, or None.

    Returns:
        The process exit code.
    """
    token = options.session_token or secrets.token_urlsafe(_TOKEN_BYTES)
    redactor = SecretRedactor()
    redactor.register(token)
    writer = configure_logging(
        logs_dir=paths.logs_dir,
        verbose=options.debug,
        clock=container.clock,
        run_id=new_run_id(container.clock),
        redactor=redactor,
        console=console,
    )
    try:
        remove_old_logs(paths.logs_dir, container.clock.now().date())
        container.schema.bring_up_to_date()
        if container.settings.current().log_detail is LogDetail.VERBOSE:
            set_verbose(True)
        server = _start_server(options, paths, container, token)
        _log_start(options, paths, container, server.url)
        try:
            wait(f"{server.url}/?token={token}")
        finally:
            _log.info("app.stopping", msg="yt-mirror is stopping")
            server.stop()
    except Exception:
        _log.error(
            "app.crashed",
            msg="yt-mirror stopped because of an unexpected error",
            error_code=ErrorCode.INTERNAL.value,
            exc_info=True,
        )
        raise
    finally:
        writer.close()
    return EXIT_OK


def wait_for_stop_signal() -> None:
    """Block until the process is asked to stop with Ctrl+C or a termination signal."""
    stop = threading.Event()

    def request_stop(_signal_number: int, _frame: FrameType | None) -> None:
        stop.set()

    watched = (signal.SIGINT, signal.SIGTERM)
    previous = {number: signal.signal(number, request_stop) for number in watched}
    try:
        stop.wait()
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def _wait_in_browser(url: str) -> None:
    webbrowser.open(url)
    sys.stderr.write(BROWSER_HINT)
    wait_for_stop_signal()


def _start_server(
    options: RunOptions, paths: AppPaths, container: Container, token: str
) -> BackgroundServer:
    sock = bind_local_socket(options.port)
    port: int = sock.getsockname()[1]
    config = ApiConfig(
        security=SecurityPolicy.for_local_server(token, port, extra_origin=options.frontend_url),
        frontend_dir=paths.frontend_dir,
        frontend_url=options.frontend_url or LOCAL_FRONTEND,
    )
    server = BackgroundServer(create_app(config, container.diagnostics, container.clock), sock)
    server.start()
    return server


def _log_start(options: RunOptions, paths: AppPaths, container: Container, url: str) -> None:
    if options.no_window:
        mode = "no_window"
    elif options.browser:
        mode = "browser"
    else:
        mode = "window"
    _log.info(
        "app.started",
        msg="yt-mirror started",
        version=container.info.version,
        url=url,
        mode=mode,
        dev=options.dev,
    )
    _log.info(
        "app.config",
        msg="Paths, versions and install kind of this run",
        install_kind=container.info.install_kind.value,
        home_dir=str(paths.home_dir),
        data_dir=str(paths.data_dir),
        database_file=str(paths.database_file),
        frontend_dir=str(paths.frontend_dir),
        app_version=container.info.version,
        python_version=container.probe.python_version(),
        macos_version=container.probe.os_version(),
        cpu_architecture=container.probe.cpu_architecture(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
