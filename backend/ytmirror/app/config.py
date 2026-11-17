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
ENV_WINDOW_REPORT = "YTM_WINDOW_REPORT"
ENV_TOOL_DIR = "YTM_TOOL_DIR"
ENV_TOOL_MANIFEST = "YTM_TOOL_MANIFEST"
ENV_TOOL_SOURCE = "YTM_TOOL_SOURCE"
ENV_FAKE_YOUTUBE = "YTM_FAKE_YOUTUBE"
ENV_LIBRARY_DIR = "YTM_LIBRARY_DIR"
ENV_TRASH_DIR = "YTM_TRASH_DIR"
ENV_FAKE_LOOKUPS_PER_HOUR = "YTM_FAKE_LOOKUPS_PER_HOUR"
ENV_FAKE_HOLD_DOWNLOADS = "YTM_FAKE_HOLD_DOWNLOADS"

DEFAULT_DEV_FRONTEND_URL = "http://127.0.0.1:5173/"
DEFAULT_TOOL_MANIFEST = Path(__file__).resolve().parents[1] / "services" / "toolchain_manifest.json"
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
        tool_dir: The folder the downloaded tools are kept in.
        cache_dir: Pictures of the catalogue and other things that can be fetched again.
        default_library: What the default of the library setting means on this Mac.
        tool_manifest: The file that pins the downloadable tools.
        only_tool_source: The one tool source to use, or None for all. For automated tests.
        fake_youtube: A folder with a recorded world of channels, or None for the real YouTube.
        trash_dir: A folder that stands for the Trash of macOS, or None for the real one.
        fake_lookups_per_hour: The budget of lookups of the fake YouTube instead of 300
            (D-084), 0 for none without a key, or None. For tests only.
        fake_hold_downloads: Whether the fake YouTube holds the downloads of the videos
            that name a hold (``hold_after_report``), for a screenshot in the middle of a
            download. For tests only.
            For tests, so that no test fills the Trash of the person who runs it.
    """

    code_root: Path
    home_dir: Path
    data_dir: Path
    logs_dir: Path
    database_file: Path
    frontend_dir: Path
    uv_executable: Path
    tool_dir: Path
    cache_dir: Path
    default_library: Path
    tool_manifest: Path = DEFAULT_TOOL_MANIFEST
    only_tool_source: str | None = None
    fake_youtube: Path | None = None
    trash_dir: Path | None = None
    fake_lookups_per_hour: int | None = None
    fake_hold_downloads: bool = False


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
        window_report: A file to write what the window shows to, or None. For automated tests.
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
    window_report: Path | None = None


def resolve_paths(env: Mapping[str, str]) -> AppPaths:
    """Return the paths of this installation.

    Args:
        env: The environment variables. ``YTM_HOME`` and ``YTM_DATA_DIR`` override the
            defaults. ``YTM_TOOL_DIR``, ``YTM_TOOL_MANIFEST``, ``YTM_TOOL_SOURCE``,
            ``YTM_LIBRARY_DIR`` and ``YTM_TRASH_DIR`` are for tests. ``YTM_FAKE_YOUTUBE``
            names a folder with a recorded world of channels to use in place of the
            real YouTube. ``YTM_TRASH_DIR``, ``YTM_FAKE_LOOKUPS_PER_HOUR`` and
            ``YTM_FAKE_HOLD_DOWNLOADS`` count
            only together with ``YTM_FAKE_YOUTUBE``.

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
        tool_dir=Path(env[ENV_TOOL_DIR]) if env.get(ENV_TOOL_DIR) else home_dir / "tools",
        tool_manifest=Path(env[ENV_TOOL_MANIFEST])
        if env.get(ENV_TOOL_MANIFEST)
        else DEFAULT_TOOL_MANIFEST,
        only_tool_source=env.get(ENV_TOOL_SOURCE) or None,
        cache_dir=data_dir / "cache",
        default_library=Path(env[ENV_LIBRARY_DIR])
        if env.get(ENV_LIBRARY_DIR)
        else Path.home() / "Movies" / "YouTube",
        fake_youtube=Path(env[ENV_FAKE_YOUTUBE]) if env.get(ENV_FAKE_YOUTUBE) else None,
        # A Trash of its own is for tests only: an app on the real YouTube uses
        # the Trash of macOS whatever the environment says (R-CH-32).
        trash_dir=Path(env[ENV_TRASH_DIR])
        if env.get(ENV_TRASH_DIR) and env.get(ENV_FAKE_YOUTUBE)
        else None,
        # Another pace of exact-date lookups is for tests only: an app on the real
        # YouTube keeps to the budget of D-084 whatever the environment says.
        fake_lookups_per_hour=_whole_number(env.get(ENV_FAKE_LOOKUPS_PER_HOUR))
        if env.get(ENV_FAKE_YOUTUBE)
        else None,
        # Held downloads are for the screenshot of a row in the middle of a download:
        # a hand run on the fake YouTube never waits for them.
        fake_hold_downloads=env.get(ENV_FAKE_HOLD_DOWNLOADS) == "1"
        and bool(env.get(ENV_FAKE_YOUTUBE)),
    )


def _whole_number(text: str | None) -> int | None:
    """Return a number of the environment, or None when it is missing or not a whole number."""
    if text is None or not text.strip().isdigit():
        return None
    return int(text)


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
        window_report=Path(env[ENV_WINDOW_REPORT]) if env.get(ENV_WINDOW_REPORT) else None,
    )
