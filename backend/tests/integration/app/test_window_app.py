"""The real app with its real window: menu bar and quitting, as macOS sees them.

These tests start ``python -m ytmirror.app.main`` as a child process and let
it open its window for a few seconds. They are the guard of two decisions
that rely on how the pinned window library behaves: the menu bar that
replaces its menus (docs/DECISIONS.md D-049) and the quit path (D-052).
An update of the window library that breaks either one fails here.

The app writes what macOS shows of it to a file (``YTM_WINDOW_REPORT``).
"""

import importlib
import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from ytmirror.app.menus import menu_bar

pytestmark = pytest.mark.window

STARTUP_TIMEOUT_S = 60.0
QUIT_TIMEOUT_S = 30
CLONE_NAME = "yt-mirror (dev)"
"""The tests run from a clone, so the app names itself as a clone does (R-NA-01)."""


@dataclass
class RunningApp:
    """The app in a child process, with its window on the screen."""

    process: subprocess.Popen[bytes]
    shown: dict[str, Any]
    logs_dir: Path

    def events(self) -> list[str]:
        """Return the event names of the debug log, in order."""
        lines: list[str] = []
        for path in sorted(self.logs_dir.glob("yt-mirror-*.jsonl")):
            lines += path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line)["event"] for line in lines]


@pytest.fixture
def app(tmp_path: Path) -> Iterator[RunningApp]:
    """Start the app with a window and wait until the window is up."""
    report = tmp_path / "window.json"
    env = {
        **os.environ,
        "YTM_HOME": str(tmp_path),
        "YTM_WINDOW_REPORT": str(report),
        "YTM_SESSION_TOKEN": "window-test-token",
    }
    for name in ("YTM_NO_WINDOW", "YTM_PORT", "YTM_DATA_DIR"):
        env.pop(name, None)
    process = subprocess.Popen(
        [sys.executable, "-m", "ytmirror.app.main"],
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
        yield RunningApp(process, shown, tmp_path / "data" / "logs")
    finally:
        process.kill()
        process.wait()


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
                (item.title, item.action.value, item.shortcut and item.shortcut.key)
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
                (item["title"], item["action"], item["shortcut"] and item["shortcut"]["key"])
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
