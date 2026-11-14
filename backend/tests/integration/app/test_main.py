"""Tests of ``ytmirror.app.main``: a whole run of the app without a window."""

import io
import json
import os
import signal
import subprocess
import sys
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx2
import pytest
from sqlalchemy import text

from tests.fixtures.fakes.clock import FakeClock
from tests.fixtures.fakes.native_app import FakeNativeApp
from ytmirror.adapters.db.engine import create_db_engine
from ytmirror.adapters.db.settings_repository import SqlSettingsRepository
from ytmirror.app import main as main_module
from ytmirror.app.config import AppPaths, RunOptions
from ytmirror.app.container import build_container
from ytmirror.app.main import (
    BROWSER_HINT,
    UPDATE_NOT_AVAILABLE,
    choose_wait,
    main,
    run_app,
    wait_for_stop_signal,
)
from ytmirror.app.menus import menu_bar
from ytmirror.core.models import AppIdentity, LogDetail, Settings

TOKEN = "integration-test-token"


def options(**changes: object) -> RunOptions:
    """Return the options of a windowless test run, with changes."""
    values: dict[str, object] = {
        "dev": False,
        "debug": False,
        "browser": False,
        "doctor": False,
        "update": False,
        "no_window": True,
        "port": None,
        "session_token": TOKEN,
        "frontend_url": None,
        "window_report": None,
    }
    values.update(changes)
    return RunOptions(**values)  # pyright: ignore[reportArgumentType]  (test helper with loose types)


def _no_window_expected(_url: str, **_how: object) -> None:
    pytest.fail("The app window must not open in this mode")


class OpenedWindows:
    """Stands in for ``open_window``: remembers how every window was asked for."""

    def __init__(self) -> None:
        """Start with no window."""
        self.windows: list[dict[str, object]] = []

    def __call__(self, url: str, **how: object) -> None:
        """Remember the window instead of opening it."""
        self.windows.append({"url": url, **how})


def _never() -> None:
    pytest.fail("The shutdown work is not the business of this way of showing the app")


class Visit:
    """Stands in for the window: opens the first URL like a browser and records what it saw."""

    def __init__(self) -> None:
        """Start with nothing seen."""
        self.first_url = ""
        self.redirect_status = 0
        self.page_status = 0
        self.health: dict[str, object] = {}
        self.health_without_session = 0

    def __call__(self, url: str, _before_quit: object = None) -> None:
        """Visit the app the way the window does, then return so the app stops."""
        self.first_url = url
        base = url.split("/?", maxsplit=1)[0]
        with httpx2.Client(follow_redirects=False) as client:
            self.health_without_session = client.get(base + "/api/health").status_code
            self.redirect_status = client.get(url).status_code
            self.page_status = client.get(base + "/").status_code
            self.health = client.get(base + "/api/health").json()


def log_lines(paths: AppPaths) -> list[dict[str, object]]:
    """Return every line of every daily log file."""
    lines: list[dict[str, object]] = []
    for path in sorted(paths.logs_dir.glob("yt-mirror-*.jsonl")):
        lines += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return lines


def test_a_run_serves_the_interface_and_the_api_behind_the_session_token(paths: AppPaths) -> None:
    """R-PL-11, R-PL-10: a start brings up a server that serves the frontend and the API."""
    visit = Visit()

    exit_code = run_app(options(), paths, build_container(paths), wait=visit, console=None)

    assert exit_code == 0
    assert visit.first_url.startswith("http://127.0.0.1:")
    assert visit.first_url.endswith(f"/?token={TOKEN}")
    assert visit.health_without_session == 401
    assert visit.redirect_status == 303
    assert visit.page_status == 200
    assert visit.health["status"] == "ok"
    assert visit.health["schema_version"] == "0002"


def test_the_first_run_creates_the_database_through_the_migrations(paths: AppPaths) -> None:
    """R-QA-07: a fresh clone gets its database from the migrations at the first start."""
    run_app(options(), paths, build_container(paths), wait=Visit(), console=None)

    engine = create_db_engine(paths.database_file)
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert version == "0002"


def test_a_run_logs_its_start_configuration_and_stop(paths: AppPaths) -> None:
    """R-LG-06: ``app.started``, ``app.config`` and ``app.stopping`` frame every run."""
    run_app(options(), paths, build_container(paths), wait=Visit(), console=None)

    lines = log_lines(paths)
    events = [line["event"] for line in lines]
    assert events == [
        "db.migration.started",
        "db.migration.finished",
        "app.started",
        "app.config",
        "api.error",
        "app.stopping",
    ]
    assert len({line["run_id"] for line in lines}) == 1
    config = next(line for line in lines if line["event"] == "app.config")
    assert config["data_dir"] == str(paths.data_dir)
    assert config["install_kind"] == "archive"
    assert config["app_version"]
    assert config["python_version"]
    started = next(line for line in lines if line["event"] == "app.started")
    assert started["mode"] == "no_window"


def test_the_session_token_never_reaches_the_log_or_the_console(paths: AppPaths) -> None:
    """R-LG-07: secrets are redacted on every line (docs/LOGGING.md section 1, rule 4)."""
    console = io.StringIO()

    run_app(options(debug=True), paths, build_container(paths), wait=Visit(), console=console)

    written = "".join(path.read_text(encoding="utf-8") for path in paths.logs_dir.glob("*.jsonl"))
    assert "api.request" in written
    assert TOKEN not in written
    assert TOKEN not in console.getvalue()
    assert "app.started" in console.getvalue()


def test_without_a_fixed_token_every_run_gets_a_new_random_one(paths: AppPaths) -> None:
    """R-PL-10: a random session token is created at start."""
    first, second = Visit(), Visit()

    run_app(options(session_token=None), paths, build_container(paths), wait=first, console=None)
    run_app(options(session_token=None), paths, build_container(paths), wait=second, console=None)

    first_token = first.first_url.split("token=")[1]
    second_token = second.first_url.split("token=")[1]
    assert first_token != second_token
    assert len(first_token) >= 40
    assert first.health["status"] == "ok"


def test_normal_log_detail_leaves_requests_out_and_verbose_puts_them_in(paths: AppPaths) -> None:
    """R-LG-08: the stored "Log detail" setting decides whether debug lines are written."""
    container = build_container(paths)
    run_app(options(), paths, container, wait=Visit(), console=None)
    normal_events = {line["event"] for line in log_lines(paths)}
    engine = create_db_engine(paths.database_file)
    SqlSettingsRepository(engine, container.clock).save(Settings(log_detail=LogDetail.VERBOSE))

    run_app(options(), paths, build_container(paths), wait=Visit(), console=None)

    assert "api.request" not in normal_events
    assert "api.request" in {line["event"] for line in log_lines(paths)}


def test_old_log_files_are_removed_at_start(paths: AppPaths) -> None:
    """R-LG-01: files older than 14 days are deleted at start."""
    now = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    paths.logs_dir.mkdir(parents=True)
    old = paths.logs_dir / f"yt-mirror-{(now - timedelta(days=15)).date()}.jsonl"
    recent = paths.logs_dir / f"yt-mirror-{(now - timedelta(days=14)).date()}.jsonl"
    old.write_text("{}\n", encoding="utf-8")
    recent.write_text("{}\n", encoding="utf-8")

    run_app(
        options(), paths, build_container(paths, clock=FakeClock(now)), wait=Visit(), console=None
    )

    assert not old.exists()
    assert recent.exists()
    assert (paths.logs_dir / "yt-mirror-2026-11-20.jsonl").exists()


def test_quit_runs_the_shutdown_work_once_before_macos_ends_the_process(paths: AppPaths) -> None:
    """R-PL-13: on Quit the app stops its server and writes its last log line first.

    Quit ends the process inside macOS: the window never returns to the app.
    The window is given the shutdown work, and the work runs exactly once
    even when the window returns afterwards.
    """
    seen: dict[str, object] = {}

    def window_in_which_the_user_quits(url: str, before_quit: Callable[[], None]) -> None:
        base = url.split("/?", maxsplit=1)[0]
        before_quit()
        seen["events"] = [line["event"] for line in log_lines(paths)]
        try:
            httpx2.get(base + "/api/health", timeout=2)
        except httpx2.HTTPError as error:
            seen["server"] = type(error).__name__
        before_quit()

    run_app(
        options(), paths, build_container(paths), wait=window_in_which_the_user_quits, console=None
    )

    assert seen["events"] == [
        "db.migration.started",
        "db.migration.finished",
        "app.started",
        "app.config",
        "app.stopping",
    ]
    assert seen["server"] == "ConnectError"
    assert [line["event"] for line in log_lines(paths)].count("app.stopping") == 1


def test_a_crash_is_logged_with_its_stack_trace_and_passed_on(paths: AppPaths) -> None:
    """R-LG-06: ``app.crashed`` records an unexpected end, and the error is not swallowed."""

    def broken_window(_url: str, _before_quit: object) -> None:
        raise RuntimeError("window library exploded")

    with pytest.raises(RuntimeError, match="window library exploded"):
        run_app(options(), paths, build_container(paths), wait=broken_window, console=None)

    lines = log_lines(paths)
    crashed = next(line for line in lines if line["event"] == "app.crashed")
    assert crashed["level"] == "error"
    assert crashed["error_code"] == "INTERNAL"
    assert "window library exploded" in str(crashed["exception"])
    assert [line["event"] for line in lines][-2:] == ["app.stopping", "app.crashed"]


def test_update_says_it_is_not_available_yet(capsys: pytest.CaptureFixture[str]) -> None:
    """infra: ``--update`` exists but the updater arrives in milestone M9, and it says so."""
    exit_code = main(["--update"], {})

    assert exit_code == 2
    assert capsys.readouterr().err == UPDATE_NOT_AVAILABLE


def test_doctor_prints_the_report_and_creates_no_data(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """R-LG-05, R-IN-06: ``./start --doctor`` reports the environment without changing it."""
    exit_code = main(["--doctor"], {"YTM_HOME": str(tmp_path)})

    output = capsys.readouterr().out
    assert exit_code in (0, 1)
    assert output.startswith("yt-mirror environment report\n")
    assert "macOS:" in output
    assert "Database: not created yet" in output
    assert list(tmp_path.iterdir()) == []


def test_the_default_way_to_show_the_app_is_the_window(
    monkeypatch: pytest.MonkeyPatch, paths: AppPaths
) -> None:
    """R-PL-02: the UI runs in a dedicated app window, not a browser tab."""
    opened = OpenedWindows()
    monkeypatch.setattr(main_module, "open_window", opened)
    container = build_container(paths, native=FakeNativeApp())

    choose_wait(options(no_window=False, debug=True), container)(
        "http://127.0.0.1:1/?token=t", _never
    )

    (window,) = opened.windows
    assert window["url"] == "http://127.0.0.1:1/?token=t"
    assert window["debug"] is True
    assert window["native"] is container.native
    assert window["before_quit"] is _never


def test_the_window_carries_the_name_and_the_menu_bar_of_this_installation(
    monkeypatch: pytest.MonkeyPatch, paths: AppPaths
) -> None:
    """R-NA-01, R-NA-03: an installed copy is "yt-mirror", a clone "yt-mirror (dev)"."""
    opened = OpenedWindows()
    monkeypatch.setattr(main_module, "open_window", opened)

    choose_wait(options(no_window=False), build_container(paths))("http://127.0.0.1:1/", _never)
    (paths.code_root / ".git").mkdir()
    choose_wait(options(no_window=False), build_container(paths))("http://127.0.0.1:1/", _never)

    installed, clone = opened.windows
    assert installed["title"] == "yt-mirror"
    assert installed["menus"] == menu_bar("yt-mirror")
    assert clone["title"] == "yt-mirror (dev)"
    assert clone["menus"] == menu_bar("yt-mirror (dev)")
    assert installed["when_shown"] is None


def test_asked_for_a_window_report_the_app_writes_what_macos_shows(
    monkeypatch: pytest.MonkeyPatch, paths: AppPaths, tmp_path: Path
) -> None:
    """infra: tests read the name and the menu bar of the real window from a file."""
    report = tmp_path / "window.json"
    native = FakeNativeApp(AppIdentity("yt-mirror (dev)", "io.github.mderis.yt-mirror.dev"))
    native.show_menu_bar(menu_bar("yt-mirror (dev)"))
    opened = OpenedWindows()
    monkeypatch.setattr(main_module, "open_window", opened)
    container = build_container(paths, native=native)

    choose_wait(options(no_window=False, window_report=report), container)("http://x/", _never)
    when_shown = opened.windows[0]["when_shown"]
    assert callable(when_shown)
    when_shown()

    shown = json.loads(report.read_text(encoding="utf-8"))
    assert shown["identity"] == {
        "name": "yt-mirror (dev)",
        "bundle_identifier": "io.github.mderis.yt-mirror.dev",
    }
    assert [menu["title"] for menu in shown["menu_bar"]] == ["yt-mirror (dev)", "Edit"]
    assert shown["menu_bar"][1]["items"][1] == {
        "title": "Redo",
        "action": "redo",
        "shortcut": {"key": "z", "shift": True, "option": False},
        "enabled": True,
    }


def test_the_browser_flag_opens_the_default_browser_instead(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], paths: AppPaths
) -> None:
    """R-PL-02: a ``--browser`` flag opens the UI in the default browser instead."""
    opened: list[str] = []
    waited: list[bool] = []
    monkeypatch.setattr(main_module.webbrowser, "open", opened.append)
    monkeypatch.setattr(main_module, "wait_for_stop_signal", lambda: waited.append(True))
    monkeypatch.setattr(main_module, "open_window", _no_window_expected)

    container = build_container(paths)
    choose_wait(options(no_window=False, browser=True), container)(
        "http://127.0.0.1:1/?token=t", _never
    )

    assert opened == ["http://127.0.0.1:1/?token=t"]
    assert waited == [True]
    assert capsys.readouterr().err == BROWSER_HINT


def test_without_a_window_the_app_just_waits_for_a_stop_signal(
    monkeypatch: pytest.MonkeyPatch, paths: AppPaths
) -> None:
    """infra: automated tests run the server alone and stop it with a signal."""
    waited: list[bool] = []
    monkeypatch.setattr(main_module, "wait_for_stop_signal", lambda: waited.append(True))
    monkeypatch.setattr(main_module, "open_window", _no_window_expected)

    choose_wait(options(no_window=True, browser=True), build_container(paths))(
        "http://127.0.0.1:1/", _never
    )

    assert waited == [True]


@pytest.mark.parametrize("stop_signal", [signal.SIGINT, signal.SIGTERM])
def test_a_stop_signal_ends_the_wait_and_old_handlers_come_back(
    monkeypatch: pytest.MonkeyPatch, stop_signal: signal.Signals
) -> None:
    """R-PL-13: Ctrl+C or a termination signal ends the app. Nothing keeps running."""

    class EventThatGetsTheSignal(threading.Event):
        def wait(self, timeout: float | None = None) -> bool:
            signal.raise_signal(stop_signal)
            return super().wait(timeout=5)

    monkeypatch.setattr(main_module.threading, "Event", EventThatGetsTheSignal)
    before = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)}

    wait_for_stop_signal()

    after = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)}
    assert after == before


def test_started_as_a_program_it_serves_logs_under_its_module_name_and_stops_on_a_signal(
    paths: AppPaths, tmp_path: Path
) -> None:
    """R-PL-13: ``python -m ytmirror.app.main`` runs until it is told to stop."""
    env = {
        **os.environ,
        "YTM_HOME": str(paths.home_dir),
        "YTM_NO_WINDOW": "1",
        "YTM_SESSION_TOKEN": TOKEN,
    }
    env.pop("YTM_PORT", None)
    env.pop("YTM_DATA_DIR", None)
    process = subprocess.Popen(
        [sys.executable, "-m", "ytmirror.app.main"],
        env=env,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stderr is not None
    try:
        console = ""
        while "app.config" not in console:
            line = process.stderr.readline()
            assert line, f"The app ended before it was ready:\n{console}"
            console += line
        process.send_signal(signal.SIGTERM)
        exit_code = process.wait(timeout=30)
        console += process.stderr.read()
    finally:
        process.kill()
        process.stderr.close()

    lines = log_lines(paths)
    assert exit_code == 0
    assert [line["event"] for line in lines][-3:] == ["app.started", "app.config", "app.stopping"]
    assert {line["component"] for line in lines} == {"services.schema", "app.main"}
    assert TOKEN not in console
