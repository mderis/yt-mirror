"""Tests of ``ytmirror.app.single_instance`` and of a second start of the app."""

import io
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from ytmirror.app import main as main_module
from ytmirror.app.config import RunOptions
from ytmirror.app.main import (
    ALREADY_RUNNING,
    BROUGHT_TO_FRONT,
    leave_it_to_the_running_app,
    main,
)
from ytmirror.app.single_instance import InstanceLock, RunningInstance, bring_to_front, bundle_of


def options(**changes: object) -> RunOptions:
    """Return the options of a start for a window, with changes."""
    values: dict[str, object] = {
        "dev": False,
        "debug": False,
        "browser": False,
        "doctor": False,
        "update": False,
        "no_window": False,
        "port": None,
        "session_token": None,
        "frontend_url": None,
        "window_report": None,
    }
    values.update(changes)
    return RunOptions(**values)  # pyright: ignore[reportArgumentType]  (test helper with loose types)


def test_only_one_process_holds_the_lock_of_a_data_folder(tmp_path: Path) -> None:
    """R-NA-08: only one instance can run per data folder."""
    first = InstanceLock(tmp_path / "data")
    second = InstanceLock(tmp_path / "data")

    assert first.acquire() is True
    assert second.acquire() is False

    first.release()
    assert second.acquire() is True
    second.release()


def test_another_data_folder_is_another_app(tmp_path: Path) -> None:
    """R-NA-08: the rule is per data folder, so a test run is not blocked by an open app."""
    first = InstanceLock(tmp_path / "one")
    second = InstanceLock(tmp_path / "two")

    assert first.acquire() is True
    assert second.acquire() is True

    first.release()
    second.release()


def test_the_lock_creates_the_data_folder_and_survives_a_release_without_a_hold(
    tmp_path: Path,
) -> None:
    """R-NA-08: the very first start, with no data folder yet, can take the lock."""
    lock = InstanceLock(tmp_path / "new" / "data")

    lock.release()
    assert lock.acquire() is True
    lock.release()

    assert (tmp_path / "new" / "data" / "instance.lock").exists()


def test_the_holder_writes_down_who_it_is(tmp_path: Path) -> None:
    """R-NA-08: a second start can find the app bundle of the running app."""
    lock = InstanceLock(tmp_path)
    assert lock.acquire()

    lock.describe(4321, Path("/Applications/yt-mirror.app"))
    with_bundle = InstanceLock(tmp_path).running_instance()
    lock.describe(4321, None)
    without = InstanceLock(tmp_path).running_instance()
    lock.release()

    assert with_bundle == RunningInstance(pid=4321, bundle=Path("/Applications/yt-mirror.app"))
    assert without == RunningInstance(pid=4321, bundle=None)


@pytest.mark.parametrize("content", [None, "", "not json", "{}", '{"pid": "x", "bundle": null}'])
def test_a_missing_or_broken_note_about_the_holder_is_no_note(
    tmp_path: Path, content: str | None
) -> None:
    """R-NA-08: a second start never crashes over what the first one left behind."""
    if content is not None:
        (tmp_path / "instance.json").write_text(content, encoding="utf-8")

    assert InstanceLock(tmp_path).running_instance() is None


@pytest.mark.parametrize(
    ("program", "bundle"),
    [
        (
            "/x/tools/yt-mirror (dev).app/Contents/MacOS/yt-mirror (dev)",
            "/x/tools/yt-mirror (dev).app",
        ),
        (
            "/Users/u/Applications/yt-mirror.app/Contents/MacOS/yt-mirror",
            "/Users/u/Applications/yt-mirror.app",
        ),
        ("/x/tools/venv/bin/python", None),
        ("/x/thing.app/Contents/Resources/python", None),
        ("/x/Contents/MacOS/python", None),
        ("python", None),
    ],
)
def test_the_bundle_is_read_from_the_place_of_the_running_program(
    program: str, bundle: str | None
) -> None:
    """R-NA-08: the app knows its bundle without asking macOS."""
    assert bundle_of(Path(program)) == (Path(bundle) if bundle else None)


def test_a_second_start_for_a_window_brings_the_running_app_forward(tmp_path: Path) -> None:
    """R-NA-08: starting the app again focuses the existing window."""
    lock = InstanceLock(tmp_path)
    assert lock.acquire()
    lock.describe(1, Path("/somewhere/yt-mirror.app"))
    asked: list[Path] = []
    console = io.StringIO()

    def bring_forward(bundle: Path) -> bool:
        asked.append(bundle)
        return True

    exit_code = leave_it_to_the_running_app(
        options(), InstanceLock(tmp_path), console, bring_forward
    )
    lock.release()

    assert exit_code == 0
    assert asked == [Path("/somewhere/yt-mirror.app")]
    assert console.getvalue() == BROUGHT_TO_FRONT


@pytest.mark.parametrize("mode", [{"browser": True}, {"no_window": True}])
def test_a_second_start_without_a_window_only_says_that_the_app_runs(
    tmp_path: Path, mode: dict[str, bool]
) -> None:
    """R-NA-08: a second start with ``--browser`` ends with a plain message."""
    lock = InstanceLock(tmp_path)
    assert lock.acquire()
    lock.describe(1, Path("/somewhere/yt-mirror.app"))
    asked: list[Path] = []
    console = io.StringIO()

    exit_code = leave_it_to_the_running_app(
        options(**mode), InstanceLock(tmp_path), console, lambda bundle: bool(asked.append(bundle))
    )
    lock.release()

    assert exit_code == 1
    assert asked == []
    assert console.getvalue() == ALREADY_RUNNING


@pytest.mark.parametrize("case", ["no window to bring forward", "macos refuses"])
def test_when_no_window_can_come_forward_the_second_start_says_so(
    tmp_path: Path, case: str
) -> None:
    """R-NA-08: the second start never opens a second app, whatever the first one is."""
    lock = InstanceLock(tmp_path)
    assert lock.acquire()
    lock.describe(1, None if case == "no window to bring forward" else Path("/gone/yt-mirror.app"))
    console = io.StringIO()

    exit_code = leave_it_to_the_running_app(
        options(), InstanceLock(tmp_path), console, lambda _bundle: False
    )
    lock.release()

    assert exit_code == 1
    assert console.getvalue() == ALREADY_RUNNING


def test_macos_is_asked_to_open_the_bundle_again(tmp_path: Path) -> None:
    """R-NA-08: a bundle that does not exist cannot be brought forward, and that is reported."""
    assert bring_to_front(tmp_path / "no-such.app") is False


def test_a_second_app_on_the_same_data_folder_does_not_start(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-NA-08: while one app runs, a second start serves nothing and touches no data."""
    env = {**os.environ, "YTM_HOME": str(tmp_path), "YTM_NO_WINDOW": "1"}
    for name in ("YTM_PORT", "YTM_DATA_DIR", "YTM_WINDOW_REPORT"):
        env.pop(name, None)
    first = subprocess.Popen(
        [sys.executable, "-m", "ytmirror.app.main"], env=env, stderr=subprocess.PIPE, text=True
    )
    assert first.stderr is not None

    def no_second_app(*_args: object, **_how: object) -> int:
        pytest.fail("a second app ran")

    monkeypatch.setattr(main_module, "run_app", no_second_app)
    try:
        console = ""
        while "app.config" not in console:
            line = first.stderr.readline()
            assert line, f"The first app ended before it was ready:\n{console}"
            console += line

        exit_code = main(["--browser"], {"YTM_HOME": str(tmp_path)})

        note = json.loads((tmp_path / "data" / "instance.json").read_text(encoding="utf-8"))
        assert exit_code == 1
        assert capsys.readouterr().err == ALREADY_RUNNING
        assert note == {"pid": first.pid, "bundle": None}
    finally:
        first.send_signal(signal.SIGTERM)
        first.wait(timeout=30)
        first.stderr.close()


def test_after_the_app_ended_the_next_start_is_the_first_one_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-NA-08: the lock ends with the app, so nothing stale blocks the next start."""
    ran: list[bool] = []

    def fake_run_app(*_args: object, **_how: object) -> int:
        ran.append(True)
        return 0

    monkeypatch.setattr(main_module, "run_app", fake_run_app)

    assert main([], {"YTM_HOME": str(tmp_path), "YTM_NO_WINDOW": "1"}) == 0
    assert main([], {"YTM_HOME": str(tmp_path), "YTM_NO_WINDOW": "1"}) == 0

    assert ran == [True, True]
