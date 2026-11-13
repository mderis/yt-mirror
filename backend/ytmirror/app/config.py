"""Paths, environment variables and command line options.

This is the only module that reads environment variables. It must not create
folders or files: it only says where things are.

Tests: backend/tests/unit/app/test_config.py
"""

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ytmirror.core.models import InstallKind

ENV_HOME = "YTM_HOME"
ENV_DATA_DIR = "YTM_DATA_DIR"
ENV_PORT = "YTM_PORT"
ENV_SESSION_TOKEN = "YTM_SESSION_TOKEN"
ENV_NO_WINDOW = "YTM_NO_WINDOW"
ENV_FRONTEND_URL = "YTM_FRONTEND_URL"

DEFAULT_DEV_FRONTEND_URL = "http://127.0.0.1:5173/"
_MAX_PORT = 65535


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Where the parts of this installation are.

    Attributes:
        code_root: The folder with ``backend/``, ``frontend/`` and ``start``.
        home_dir: The folder that holds ``data/`` and ``tools/``.
        data_dir: Database, logs, backups and caches.
        logs_dir: The debug logs.
        database_file: The SQLite database.
        frontend_dir: The built interface.
        uv_executable: The bundled uv program.
    """

    code_root: Path
    home_dir: Path
    data_dir: Path
    logs_dir: Path
    database_file: Path
    frontend_dir: Path
    uv_executable: Path


@dataclass(frozen=True, slots=True)
class RunOptions:
    """How this run was started.

    Attributes:
        dev: Use the development server for the interface (``--dev``).
        debug: Verbose logs and developer tools in the window (``--debug``).
        browser: Open the default browser instead of the app window (``--browser``).
        doctor: Print the environment report and exit (``--doctor``).
        update: The user asked for an update (``--update``).
        no_window: Serve without opening anything. For automated tests.
        port: A fixed port, or None for any free port.
        session_token: A fixed session token, or None for a random one. For automated tests.
        frontend_url: The address of the development server, or None.
    """

    dev: bool
    debug: bool
    browser: bool
    doctor: bool
    update: bool
    no_window: bool
    port: int | None
    session_token: str | None
    frontend_url: str | None


def resolve_paths(env: Mapping[str, str]) -> AppPaths:
    """Return the paths of this installation.

    Args:
        env: The environment variables. ``YTM_HOME`` and ``YTM_DATA_DIR`` override the defaults.

    Returns:
        The paths. Nothing is created.
    """
    code_root = Path(__file__).resolve().parents[3]
    home_dir = Path(env[ENV_HOME]) if env.get(ENV_HOME) else code_root
    data_dir = Path(env[ENV_DATA_DIR]) if env.get(ENV_DATA_DIR) else home_dir / "data"
    return AppPaths(
        code_root=code_root,
        home_dir=home_dir,
        data_dir=data_dir,
        logs_dir=data_dir / "logs",
        database_file=data_dir / "yt-mirror.db",
        frontend_dir=code_root / "frontend" / "dist",
        uv_executable=home_dir / "tools" / "uv" / "uv",
    )


def detect_install_kind(code_root: Path) -> InstallKind:
    """Return how this copy was installed.

    Args:
        code_root: The folder with the app code.

    Returns:
        ``clone`` when the folder is a git repository, otherwise ``archive``.
    """
    return InstallKind.CLONE if (code_root / ".git").exists() else InstallKind.ARCHIVE


def parse_options(argv: Sequence[str], env: Mapping[str, str]) -> RunOptions:
    """Read the command line flags and the environment variables of a run.

    Args:
        argv: The command line arguments, without the program name.
        env: The environment variables.

    Returns:
        The options of this run.

    Raises:
        SystemExit: For an unknown flag or an invalid ``YTM_PORT``, with exit code 2.
    """
    parser = argparse.ArgumentParser(prog="./start", description="Start yt-mirror.")
    parser.add_argument("--dev", action="store_true", help="hot reload of the interface")
    parser.add_argument("--debug", action="store_true", help="verbose logs and developer tools")
    parser.add_argument("--browser", action="store_true", help="open in the default browser")
    parser.add_argument("--doctor", action="store_true", help="check the environment and report")
    parser.add_argument("--update", action="store_true", help="update yt-mirror")
    flags = parser.parse_args(list(argv))
    port_text = env.get(ENV_PORT)
    port: int | None = None
    if port_text:
        if not port_text.isdigit() or not 0 < int(port_text) <= _MAX_PORT:
            parser.error(f"{ENV_PORT} must be a port number, not {port_text!r}")
        port = int(port_text)
    frontend_url: str | None = None
    if flags.dev:
        frontend_url = env.get(ENV_FRONTEND_URL) or DEFAULT_DEV_FRONTEND_URL
    return RunOptions(
        dev=flags.dev,
        debug=flags.debug,
        browser=flags.browser,
        doctor=flags.doctor,
        update=flags.update,
        no_window=env.get(ENV_NO_WINDOW, "") not in ("", "0"),
        port=port,
        session_token=env.get(ENV_SESSION_TOKEN) or None,
        frontend_url=frontend_url,
    )
