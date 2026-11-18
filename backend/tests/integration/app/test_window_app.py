"""The real app with its real window: menu bar and quitting, as macOS sees them.

These tests start ``python -m ytmirror.app.main`` as a child process and let
it open its window for a few seconds. They are the guard of two decisions
that rely on how the pinned window library behaves: the menu bar that
replaces its menus (docs/DECISIONS.md D-049) and the quit path (D-052).
An update of the window library that breaks either one fails here.

The app writes what macOS shows of it to a file (``YTM_WINDOW_REPORT``).
"""

import contextlib
import importlib
import io
import json
import os
import plistlib
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Callable, Generator, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from ytmirror.app.bundle import main as build_the_bundle
from ytmirror.app.menus import menu_bar

pytestmark = pytest.mark.window

STARTUP_TIMEOUT_S = 60.0
QUIT_TIMEOUT_S = 30
CLONE_NAME = "yt-mirror (dev)"
"""The tests run from a clone, so the app names itself as a clone does (R-NA-01)."""
TOKEN = "window-test-token"
FAKE_YOUTUBE = Path(__file__).resolve().parents[4] / "e2e" / "fixtures" / "youtube"
SMALL_ID = "UCsmallchannel0000000001"
HELD_VIDEO = "small000009"
"""A video of the fake YouTube that holds in the middle of its download (``hold_ms``)."""


@dataclass
class RunningApp:
    """The app in a child process, with its window on the screen."""

    process: subprocess.Popen[bytes]
    shown: dict[str, Any]
    logs_dir: Path
    command: list[str]
    env: dict[str, str]

    def events(self) -> list[str]:
        """Return the event names of the debug log, in order."""
        lines: list[str] = []
        for path in sorted(self.logs_dir.glob("yt-mirror-*.jsonl")):
            lines += path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line)["event"] for line in lines]


@contextlib.contextmanager
def started(
    command: list[str], tmp_path: Path, extra_env: dict[str, str] | None = None
) -> Generator[RunningApp]:
    """Start the app with a window and wait until the window is up."""
    report = tmp_path / "window.json"
    env = {
        **os.environ,
        "YTM_HOME": str(tmp_path),
        "YTM_WINDOW_REPORT": str(report),
        "YTM_SESSION_TOKEN": TOKEN,
    }
    for name in ("YTM_NO_WINDOW", "YTM_PORT", "YTM_DATA_DIR"):
        env.pop(name, None)
    env.update(extra_env or {})
    process = subprocess.Popen(
        command,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + STARTUP_TIMEOUT_S
        while not report.exists() or not report.read_text(encoding="utf-8").endswith("}"):
            assert process.poll() is None, "The app ended before its window was up"
            assert time.monotonic() < deadline, "The window did not come up in time"
            time.sleep(0.1)
        shown: dict[str, Any] = json.loads(report.read_text(encoding="utf-8"))
        yield RunningApp(process, shown, tmp_path / "data" / "logs", command, env)
    finally:
        process.kill()
        process.wait()


@pytest.fixture
def app(tmp_path: Path) -> Iterator[RunningApp]:
    """The app started with its Python directly, as the tests of M0 did."""
    with started([sys.executable, "-m", "ytmirror.app.main"], tmp_path) as running:
        yield running


@pytest.fixture
def bundled_app(tmp_path: Path) -> Iterator[RunningApp]:
    """The app started through its app bundle, as ``./start`` and Finder start it."""
    launcher = io.StringIO()
    assert build_the_bundle([], {"YTM_HOME": str(tmp_path)}, launcher) == 0
    with started([launcher.getvalue().strip()], tmp_path) as running:
        yield running


def _press_ctrl_c(running: RunningApp) -> None:
    running.process.send_signal(signal.SIGINT)


def _send_the_termination_signal(running: RunningApp) -> None:
    running.process.send_signal(signal.SIGTERM)


def _quit_like_the_dock_does(running: RunningApp) -> None:
    """Send the quit request of macOS, which Cmd+Q, the Quit item and the Dock all end in."""
    appkit: Any = importlib.import_module("AppKit")
    target: Any = appkit.NSRunningApplication.runningApplicationWithProcessIdentifier_(
        running.process.pid
    )
    assert target is not None, "macOS does not know the app's process"
    assert target.terminate()


def test_the_real_menu_bar_is_ours_and_nothing_of_the_window_library_is_left(
    app: RunningApp,
) -> None:
    """R-NA-03: the menu bar of the real window has exactly our menus, items and shortcuts."""
    expected = [
        (
            menu.title,
            [
                (
                    item.title,
                    item.action.value,
                    item.shortcut and item.shortcut.key,
                    item.command and item.command.value,
                )
                for group in menu.groups
                for item in group
            ],
        )
        for menu in menu_bar(CLONE_NAME)
    ]

    shown = [
        (
            menu["title"],
            [
                (
                    item["title"],
                    item["action"],
                    item["shortcut"] and item["shortcut"]["key"],
                    item["command"],
                )
                for item in menu["items"]
                if item["action"] is not None
            ],
        )
        for menu in app.shown["menu_bar"]
    ]
    every_title = [item["title"] for menu in app.shown["menu_bar"] for item in menu["items"]]

    assert shown == expected
    assert not [title for title in every_title if title.startswith(("About", "Services"))]
    assert not [title for title in every_title if "Full Screen" in title or "Fullscreen" in title]


def test_quit_is_enabled_in_the_real_menu_bar(app: RunningApp) -> None:
    """R-NA-03: Quit can be chosen as soon as the window is up."""
    app_menu = app.shown["menu_bar"][0]
    quit_item = next(item for item in app_menu["items"] if item["action"] == "quit")

    assert quit_item["title"] == f"Quit {CLONE_NAME}"
    assert quit_item["enabled"] is True


@pytest.mark.parametrize(
    "quit_the_app",
    [_quit_like_the_dock_does, _press_ctrl_c, _send_the_termination_signal],
    ids=["quit request of macOS", "Ctrl+C", "termination signal"],
)
def test_the_real_app_shuts_down_cleanly_however_it_is_asked_to_quit(
    app: RunningApp, quit_the_app: Callable[[RunningApp], None]
) -> None:
    """R-PL-13: Quit, Ctrl+C and a termination signal all run the shutdown work first.

    In milestone M0 only closing the window did. Quit ends the process inside
    macOS, and the last log line and the stop of the server were skipped.
    """
    quit_the_app(app)

    exit_code = app.process.wait(timeout=QUIT_TIMEOUT_S)

    assert exit_code == 0
    assert app.events()[-1] == "app.stopping"
    assert app.events().count("app.stopping") == 1


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@dataclass
class Api:
    """The HTTP API of the app in the child process, signed in with the session token."""

    base: str

    def send(self, method: str, path: str, body: object | None = None) -> Any:
        """Send one request and return its JSON answer, or None for an empty one."""
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(f"{self.base}/api{path}", data=data, method=method)
        request.add_header("Authorization", f"Bearer {TOKEN}")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read()
        return json.loads(text) if text else None

    def wait_for(self, path: str, holds: Callable[[Any], bool]) -> Any:
        """Ask again until the answer holds, as a window waits for the app."""
        deadline = time.monotonic() + STARTUP_TIMEOUT_S
        while True:
            answer = self.send("GET", path)
            if holds(answer):
                return answer
            assert time.monotonic() < deadline, f"{path} did not get there: {answer}"
            time.sleep(0.2)


class EventStream:
    """The event stream, read as the interface reads it: an interface the app can ask."""

    def __init__(self, api: Api) -> None:
        """Open the stream and wait until the app listens to it."""
        self.names: list[str] = []
        self._connected = threading.Event()
        self._api = api
        threading.Thread(target=self._read, daemon=True).start()
        assert self._connected.wait(timeout=STARTUP_TIMEOUT_S), "The stream did not open"

    def _read(self) -> None:
        request = urllib.request.Request(f"{self._api.base}/api/events")
        request.add_header("Authorization", f"Bearer {TOKEN}")
        try:
            with urllib.request.urlopen(request, timeout=QUIT_TIMEOUT_S) as response:
                for raw in response:
                    line = raw.decode().strip()
                    if line.startswith(": connected"):
                        self._connected.set()
                    if line.startswith("event: "):
                        self.names.append(line.removeprefix("event: "))
        except OSError:
            return  # The app ended.

    def wait_for(self, name: str) -> None:
        """Wait until an event of this name arrived."""
        deadline = time.monotonic() + QUIT_TIMEOUT_S
        while name not in self.names:
            assert time.monotonic() < deadline, f"No {name} arrived: {self.names}"
            time.sleep(0.1)


@pytest.fixture
def served_app(tmp_path: Path) -> Iterator[tuple[RunningApp, Api]]:
    """The app with its window, on a port of the test, over the fake YouTube."""
    port = _free_port()
    free_space = tmp_path / "free-space"
    free_space.write_text(str(500 * 10**9), encoding="utf-8")
    extra = {
        "YTM_PORT": str(port),
        "YTM_FAKE_YOUTUBE": str(FAKE_YOUTUBE),
        "YTM_FAKE_HOLD_DOWNLOADS": "1",
        "YTM_LIBRARY_DIR": str(tmp_path / "library"),
        "YTM_TRASH_DIR": str(tmp_path / "trash"),
        "YTM_FAKE_FREE_SPACE_FILE": str(free_space),
    }
    command = [sys.executable, "-m", "ytmirror.app.main"]
    with started(command, tmp_path, extra) as running:
        yield running, Api(f"http://127.0.0.1:{port}")


def _start_a_held_download(api: Api) -> None:
    """Add the small channel and mirror the video that holds in the middle of its download."""
    api.send("POST", "/channels/lookup", {"text": "@samplechannelone"})
    api.send("POST", "/channels", {"channel_id": SMALL_ID, "auto_mirror": False})
    api.wait_for(f"/channels/{SMALL_ID}", lambda channel: channel["status"] != "checking")
    api.send("POST", "/videos/mirror", {"ids": [HELD_VIDEO]})
    api.wait_for("/queue", lambda queue: queue["queue"]["downloading"] == 1)


def test_a_quit_while_downloading_is_held_until_the_user_confirms_it(
    served_app: tuple[RunningApp, Api],
) -> None:
    """R-NA-06, R-QU-12: the quit request of macOS waits for the question; "Quit" ends the app."""
    running, api = served_app
    _start_a_held_download(api)
    stream = EventStream(api)

    _quit_like_the_dock_does(running)
    stream.wait_for("quit.asked")
    time.sleep(1)

    assert running.process.poll() is None, "The quit was not held"
    assert api.send("GET", "/queue")["queue"]["downloading"] == 1, "The download stopped"
    assert "app.quit_held" in running.events()

    api.send("POST", "/ui/quit")
    exit_code = running.process.wait(timeout=QUIT_TIMEOUT_S)

    assert exit_code == 0
    events = running.events()
    assert "app.quit_confirmed" in events
    assert events.count("app.stopping") == 1
    # The download stops and keeps what it has, to continue at the next start (D-091).
    assert events.index("download.stopped") > events.index("app.stopping")


@pytest.mark.parametrize("stop", [signal.SIGINT, signal.SIGTERM], ids=["Ctrl+C", "SIGTERM"])
def test_a_stop_signal_while_downloading_is_never_held(
    served_app: tuple[RunningApp, Api], stop: signal.Signals
) -> None:
    """R-NA-06: Ctrl+C and a termination signal quit at once: there is nobody to ask."""
    running, api = served_app
    _start_a_held_download(api)
    EventStream(api)

    running.process.send_signal(stop)
    exit_code = running.process.wait(timeout=QUIT_TIMEOUT_S)

    assert exit_code == 0
    events = running.events()
    assert "app.quit_passed" in events
    assert "app.quit_held" not in events
    assert events.count("app.stopping") == 1
    assert events.index("download.stopped") > events.index("app.stopping")


def _read_report(running: RunningApp) -> dict[str, Any] | None:
    try:
        shown: dict[str, Any] = json.loads(
            Path(running.env["YTM_WINDOW_REPORT"]).read_text(encoding="utf-8")
        )
    except OSError, ValueError:
        return None  # Written right now.
    return shown


def test_the_real_menu_bar_follows_the_state_the_interface_reports(
    served_app: tuple[RunningApp, Api],
) -> None:
    """R-NA-04, D-094: Check Now is off for a paused channel, which reads "Resume Channel"."""
    running, api = served_app
    state = {
        "channel_open": True,
        "paused": True,
        "checking": False,
        "has_missing": False,
        "folder_available": True,
        "view": "grid",
        "any_unpaused": False,
    }

    api.send("PUT", "/ui/state", state)

    deadline = time.monotonic() + QUIT_TIMEOUT_S
    while True:
        shown = _read_report(running)
        items = {
            item["command"]: item
            for menu in (shown or {}).get("menu_bar", [])
            for item in menu["items"]
            if item["command"] is not None
        }
        if items.get("toggle_pause", {}).get("title") == "Resume Channel":
            break
        assert time.monotonic() < deadline, "The menu bar did not follow the report"
        time.sleep(0.1)
    assert items["check_now"]["enabled"] is False
    assert items["check_all"]["enabled"] is False
    assert items["mirror_missing"]["enabled"] is False
    assert items["open_folder"]["enabled"] is True
    assert items["view_grid"]["checked"] is True
    assert items["add_channel"]["enabled"] is True


def test_started_through_its_bundle_the_app_is_yt_mirror_to_macos(bundled_app: RunningApp) -> None:
    """R-NA-01: the running app appears under its own name, never as "Python".

    Checked where macOS keeps the name: what the app itself is told, the
    process list that Activity Monitor shows, and the record of Launch
    Services that the Dock and the app switcher use.
    """
    pid = str(bundled_app.process.pid)
    in_process_list = subprocess.run(
        ["/bin/ps", "-c", "-o", "comm=", "-p", pid], capture_output=True, text=True, check=True
    ).stdout.strip()
    record_id = subprocess.run(
        ["/usr/bin/lsappinfo", "find", f"pid={pid}"], capture_output=True, text=True, check=True
    ).stdout.strip()
    record = subprocess.run(
        ["/usr/bin/lsappinfo", "info", "-only", "name,bundleid", record_id],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    assert bundled_app.shown["identity"] == {
        "name": CLONE_NAME,
        "bundle_identifier": "io.github.mderis.yt-mirror.dev",
    }
    assert in_process_list == CLONE_NAME
    assert f'"{CLONE_NAME}"' in record
    assert '"io.github.mderis.yt-mirror.dev"' in record
    assert "python" not in (in_process_list + record).lower()


def test_started_through_its_bundle_the_app_has_its_menu_bar_and_stops_cleanly(
    bundled_app: RunningApp,
) -> None:
    """R-NA-03, R-PL-13: what holds for the plain start holds inside the bundle too."""
    titles = [menu["title"] for menu in bundled_app.shown["menu_bar"]]

    _quit_like_the_dock_does(bundled_app)
    exit_code = bundled_app.process.wait(timeout=QUIT_TIMEOUT_S)

    assert titles == [CLONE_NAME, "File", "Edit", "View", "Channel", "Window", "Help"]
    assert exit_code == 0
    assert bundled_app.events()[-1] == "app.stopping"


def _lsappinfo(*arguments: str) -> str:
    return subprocess.run(
        ["/usr/bin/lsappinfo", *arguments], capture_output=True, text=True, check=True
    ).stdout.strip()


def _record_number(text: str) -> str:
    """Return the number of a Launch Services record from the ways ``lsappinfo`` writes it."""
    found = re.search(r"ASN:(0x[0-9a-f]+-0x[0-9a-f]+)", text)
    assert found is not None, f"no Launch Services record in {text!r}"
    return found.group(1)


def _is_in_front(running: RunningApp) -> bool:
    """Return whether macOS has the app in front, by its record in Launch Services."""
    mine = _record_number(_lsappinfo("find", f"pid={running.process.pid}"))
    return _record_number(_lsappinfo("front")) == mine


def _skip_when_the_screen_is_locked() -> None:
    """Skip a test about the front app while the login window covers the screen.

    On a locked screen the login window is the front app, and macOS brings no
    other app forward until the user unlocks it. The automated checks run on
    an unlocked screen.
    """
    state = subprocess.run(
        ["/usr/sbin/ioreg", "-n", "Root", "-d1", "-a"], capture_output=True, check=True
    ).stdout
    if plistlib.loads(state).get("IOConsoleLocked"):
        pytest.skip("The screen is locked: macOS brings no app to the front right now")


def _put_another_app_in_front(running: RunningApp) -> None:
    _skip_when_the_screen_is_locked()
    subprocess.run(["/usr/bin/open", "-a", "Finder"], check=True)
    deadline = time.monotonic() + QUIT_TIMEOUT_S
    while _is_in_front(running):
        assert time.monotonic() < deadline, "The other app did not come to the front"
        time.sleep(0.1)


def _wait_until_in_front(running: RunningApp) -> bool:
    deadline = time.monotonic() + QUIT_TIMEOUT_S
    while not _is_in_front(running):
        if time.monotonic() > deadline:
            return False
        time.sleep(0.1)
    return True


def test_a_second_start_starts_no_second_app(bundled_app: RunningApp) -> None:
    """R-NA-08: only one instance can run. A second start ends and leaves the first alone."""
    second = subprocess.run(
        bundled_app.command, env=bundled_app.env, capture_output=True, text=True, timeout=60
    )

    assert second.returncode == 0
    assert "already running" in second.stderr
    assert bundled_app.process.poll() is None
    assert bundled_app.events().count("app.started") == 1


def test_a_second_start_brings_the_first_window_forward(bundled_app: RunningApp) -> None:
    """R-NA-08: starting the app again focuses the existing window."""
    _put_another_app_in_front(bundled_app)

    subprocess.run(
        bundled_app.command, env=bundled_app.env, capture_output=True, text=True, timeout=60
    )

    assert _wait_until_in_front(bundled_app)


def test_opening_the_running_app_again_brings_its_window_forward(bundled_app: RunningApp) -> None:
    """R-NA-07: the request a click on the Dock icon sends brings the window to the front.

    A click on the Dock icon of a running app and ``open`` on its bundle send
    the app the same "reopen" request. The click itself is on the manual
    checklist (docs/TESTING.md section 8).
    """
    bundle = Path(bundled_app.command[0]).parents[2]
    _put_another_app_in_front(bundled_app)

    subprocess.run(["/usr/bin/open", str(bundle)], check=True)

    assert _wait_until_in_front(bundled_app)
    assert bundled_app.process.poll() is None
