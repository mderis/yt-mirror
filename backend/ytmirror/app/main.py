"""The entry point of yt-mirror: ``python -m ytmirror.app.main``.

``./start`` prepares the environment and then runs this module. It reads the
options, builds the container, brings the database up to date, starts the
HTTP server in a thread and shows the window on the main thread. When the
window closes, the app stops (docs/DECISIONS.md D-020).

However the app is asked to quit, its shutdown work runs once before the
process ends (R-PL-13, docs/DECISIONS.md D-052). Closing the window returns
to this module. Quit, a logout and a stop signal end the process inside
macOS, so the same work is also handed to the window as ``before_quit``.

This module must not contain rules. It only orders the steps of a run.

Tests: backend/tests/integration/app/test_main.py
"""

import dataclasses
import json
import os
import secrets
import signal
import sys
import threading
import time
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import FrameType
from typing import TextIO

import structlog
from structlog.typing import FilteringBoundLogger

from ytmirror.api.app import LOCAL_FRONTEND, ApiConfig, ApiServices, create_app
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
from ytmirror.app.menus import menu_bar
from ytmirror.app.server import BackgroundServer, bind_local_socket
from ytmirror.app.single_instance import InstanceLock, bring_to_front, bundle_of
from ytmirror.app.window import open_window
from ytmirror.core.errors import ErrorCode
from ytmirror.core.identity import app_identity
from ytmirror.core.models import LogDetail
from ytmirror.ports.native_app import NativeApp

# Not __name__: started with "python -m" this module is called __main__.
_log: FilteringBoundLogger = structlog.get_logger("ytmirror.app.main")

EXIT_OK = 0
EXIT_ALREADY_RUNNING = 1
EXIT_USAGE = 2
_TOKEN_BYTES = 32
WINDOW_WAIT_S = 20.0
"""How long a second start waits for the window of a first one that is still starting."""

UPDATE_NOT_AVAILABLE = (
    "Updating from inside yt-mirror is not available yet.\n"
    "If you run from a clone, update it with: git pull\n"
)
BROWSER_HINT = "yt-mirror is open in your browser. Press Ctrl+C here to quit.\n"
ALREADY_RUNNING = "yt-mirror is already running.\n"
BROUGHT_TO_FRONT = "yt-mirror is already running. Its window was brought to the front.\n"

type Wait = Callable[[str, Callable[[], None]], None]
"""Shows the app at the given address and returns when the app should stop.

The second argument is the shutdown work of the app. A way of showing the app
in which macOS can end the process by itself must make it run before that.
"""


class _Once:
    """Runs a piece of work the first time it is asked, and never again."""

    def __init__(self, work: Callable[[], None]) -> None:
        self._work = work
        self._lock = threading.Lock()
        self._done = False

    def run(self) -> None:
        """Do the work, unless it was done before. A second caller waits for the first."""
        with self._lock:
            if self._done:
                return
            self._done = True
            self._work()


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
    instance = InstanceLock(paths.data_dir)
    if not instance.acquire():
        return leave_it_to_the_running_app(options, instance, sys.stderr)
    with_window = not options.no_window and not options.browser
    bundle = bundle_of(Path(sys.executable)) if with_window else None
    instance.describe(os.getpid(), bundle)
    try:
        wait = choose_wait(
            options,
            container,
            window_is_up=lambda: instance.describe(os.getpid(), bundle, window_is_up=True),
        )
        return run_app(options, paths, container, wait=wait, console=sys.stderr)
    finally:
        instance.release()


def leave_it_to_the_running_app(
    options: RunOptions,
    instance: InstanceLock,
    console: TextIO,
    bring_forward: Callable[[Path], bool] = bring_to_front,
    pause: Callable[[float], None] = time.sleep,
) -> int:
    """End a second start: only one app runs per data folder.

    Implements R-NA-08. A start for a window brings the window of the running
    app to the front. A start for the browser or without a window says that
    yt-mirror runs already. Nothing of macOS is loaded for this, so no second
    icon appears in the Dock.

    Args:
        options: The options of this second start.
        instance: The lock that another process holds.
        console: Where the message goes.
        bring_forward: Brings the window of an app bundle forward. For tests.
        pause: Waits for the given number of seconds. For tests.

    Returns:
        The process exit code: 0 when the running app came forward, otherwise 1.
    """
    wants_window = not options.no_window and not options.browser
    if wants_window:
        instance.wait_for_the_window(WINDOW_WAIT_S, pause)
    running = instance.running_instance()
    bundle = running.bundle if wants_window and running is not None else None
    if bundle is not None and bring_forward(bundle):
        console.write(BROUGHT_TO_FRONT)
        return EXIT_OK
    console.write(ALREADY_RUNNING)
    return EXIT_ALREADY_RUNNING


def choose_wait(
    options: RunOptions, container: Container, window_is_up: Callable[[], None] | None = None
) -> Wait:
    """Return how this run shows the app: window, browser, or nothing.

    Implements R-PL-02. The window gets the app's name and its menu bar
    (R-NA-01, R-NA-03).

    Args:
        options: The options of this run.
        container: The wired adapters and services.
        window_is_up: Called once the window is on the screen.

    Returns:
        A function that shows the app and returns when the app should stop.
    """
    if options.no_window:
        return lambda _url, _before_quit: wait_for_stop_signal()
    if options.browser:
        return lambda url, _before_quit: _wait_in_browser(url)
    name = app_identity(container.info.install_kind).name
    native = container.native
    report = options.window_report

    def when_shown() -> None:
        if window_is_up is not None:
            window_is_up()
        if report is not None:
            write_window_report(report, native)

    return lambda url, before_quit: open_window(
        url,
        title=name,
        debug=options.debug,
        native=native,
        menus=menu_bar(name),
        before_quit=before_quit,
        when_shown=when_shown,
    )


def write_window_report(report: Path, native: NativeApp) -> None:
    """Write what macOS shows of the app to a file. For automated tests.

    Args:
        report: The file to write, as JSON.
        native: The app as macOS sees it.
    """
    shown = {
        "identity": dataclasses.asdict(native.identity()),
        "menu_bar": [dataclasses.asdict(menu) for menu in native.shown_menu_bar()],
    }
    report.write_text(json.dumps(shown), encoding="utf-8")


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
        container.toolchain.verify()
        if container.settings.current().log_detail is LogDetail.VERBOSE:
            set_verbose(True)
        server = _start_server(options, paths, container, token)
        _log_start(options, paths, container, server.url)
        stop = _Once(lambda: _stop(server, container))

        def before_quit() -> None:
            stop.run()
            writer.close()

        try:
            wait(f"{server.url}/?token={token}", before_quit)
        finally:
            stop.run()
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


def _stop(server: BackgroundServer, container: Container) -> None:
    """The shutdown work of the app. Later milestones add their workers here."""
    _log.info("app.stopping", msg="yt-mirror is stopping")
    # Ends the event streams of open windows first, or the server would wait for them.
    container.events.close()
    server.stop()


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
    services = ApiServices(
        diagnostics=container.diagnostics, toolchain=container.toolchain, events=container.events
    )
    server = BackgroundServer(create_app(config, services, container.clock), sock)
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
