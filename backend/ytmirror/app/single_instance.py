"""One running app per data folder (R-NA-08, docs/DECISIONS.md D-050).

A running app holds a lock on a file in its data folder, in every mode. Two
apps on one database would run every check and every download twice. The
lock belongs to the process: macOS releases it when the process ends, also
after a crash, so a stale lock cannot block a start.

A second start must decide before the window library is loaded, or a
second icon would show up in the Dock. So this module uses nothing of
macOS but the ``open`` program: asked to open the bundle of a running app,
macOS brings its window to the front, exactly as a click on the Dock icon
does (R-NA-07).

Tests: backend/tests/integration/app/test_single_instance.py
"""

import fcntl
import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO

LOCK_FILE = "instance.lock"
INFO_FILE = "instance.json"
_BUNDLE_SUFFIX = ".app"
_OPEN_PROGRAM = "/usr/bin/open"
_POLL_S = 0.1
_BUNDLE_DEPTH = 3
"""A program inside a bundle lies at ``<name>.app/Contents/MacOS/<program>``."""


@dataclass(frozen=True, slots=True)
class RunningInstance:
    """What the app that holds the lock wrote down about itself.

    Attributes:
        pid: Its process ID.
        bundle: The app bundle it runs in, or None for a run without a window.
        window_is_up: Whether its window is on the screen already.
    """

    pid: int
    bundle: Path | None
    window_is_up: bool = False


class InstanceLock:
    """The lock of one data folder."""

    def __init__(self, data_dir: Path) -> None:
        """Create the lock object. Nothing is touched yet.

        Args:
            data_dir: The data folder of this installation.
        """
        self._data_dir = data_dir
        self._file: IO[str] | None = None

    def acquire(self) -> bool:
        """Try to become the one running app of this data folder.

        Returns:
            True when this process holds the lock now, False when another process does.
        """
        self._data_dir.mkdir(parents=True, exist_ok=True)
        file = (self._data_dir / LOCK_FILE).open("a", encoding="utf-8")
        try:
            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            file.close()
            return False
        self._file = file
        return True

    def describe(self, pid: int, bundle: Path | None, *, window_is_up: bool = False) -> None:
        """Write down who holds the lock, for a second start to read.

        Args:
            pid: The process ID of this app.
            bundle: The app bundle this app runs in, or None.
            window_is_up: Whether the window of this app is on the screen already.
        """
        info = {
            "pid": pid,
            "bundle": None if bundle is None else str(bundle),
            "window_is_up": window_is_up,
        }
        (self._data_dir / INFO_FILE).write_text(json.dumps(info), encoding="utf-8")

    def running_instance(self) -> RunningInstance | None:
        """Return what the holder of the lock wrote down, or None when that cannot be read."""
        try:
            info = json.loads((self._data_dir / INFO_FILE).read_text(encoding="utf-8"))
            bundle = info["bundle"]
            return RunningInstance(
                pid=int(info["pid"]),
                bundle=Path(bundle) if bundle else None,
                window_is_up=info.get("window_is_up") is True,
            )
        except OSError, ValueError, KeyError, TypeError, AttributeError:
            return None

    def wait_for_the_window(self, seconds: float, pause: Callable[[float], None]) -> None:
        """Wait until the app that holds the lock has its window up, but not for long.

        macOS knows a running app only once its window is up. Asked to open the
        bundle before that, it would start the app once more instead of bringing
        it forward.

        Args:
            seconds: How long to wait at most.
            pause: Waits for the given number of seconds.
        """
        waited = 0.0
        while waited < seconds:
            running = self.running_instance()
            if running is None or running.bundle is None or running.window_is_up:
                return
            pause(_POLL_S)
            waited += _POLL_S

    def release(self) -> None:
        """Give the lock back. Does nothing when this process does not hold it."""
        if self._file is not None:
            self._file.close()
            self._file = None


def bundle_of(program: Path) -> Path | None:
    """Return the app bundle a program file lies in, or None.

    Args:
        program: The path of the running program, as it was started.
    """
    if len(program.parents) < _BUNDLE_DEPTH:
        return None
    bundle = program.parents[_BUNDLE_DEPTH - 1]
    inside = program.parent.name == "MacOS" and program.parent.parent.name == "Contents"
    return bundle if inside and bundle.suffix == _BUNDLE_SUFFIX else None


def bring_to_front(bundle: Path) -> bool:
    """Ask macOS to open a bundle again, which brings a running app's window forward.

    Implements the second half of R-NA-08.

    Args:
        bundle: The app bundle of the running app.

    Returns:
        True when macOS accepted the request.
    """
    done = subprocess.run([_OPEN_PROGRAM, str(bundle)], capture_output=True, check=False)
    return done.returncode == 0
