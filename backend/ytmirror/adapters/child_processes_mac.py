"""The ChildProcesses port on macOS, through libproc.

libproc lists the child processes of this process and the program each one
runs. Only those are looked at, so a process the app did not start is never
signalled, and only those whose program is one of the given ones are stopped.
A child is never reaped here: the code that started it (yt-dlp) waits for it
and must see that it was stopped. A process that ended has no program path,
so the program is read again before it is killed.

Tests: backend/tests/integration/test_child_processes.py
"""

import ctypes
import os
import signal
import time
from collections.abc import Collection
from pathlib import Path

import structlog
from structlog.typing import FilteringBoundLogger

_log: FilteringBoundLogger = structlog.get_logger(__name__)

_MOST_CHILDREN = 1024
_PATH_SIZE = 4096  # PROC_PIDPATHINFO_MAXSIZE
_POLL_S = 0.02
_CTL_KERN = 1
_KERN_PROCARGS2 = 49
_ARGUMENTS_SIZE = 1024 * 1024
"""More than the longest command line macOS accepts (kern.argmax is 1 MiB)."""


def names_folder(arguments: list[str], folder: Path) -> bool:
    """Whether one of the arguments is a path in the folder, or the folder itself."""
    places = {str(folder), str(folder.resolve())}
    return any(place in argument for argument in arguments for place in places)


class MacChildProcesses:
    """Stops child processes of this app by their program."""

    def __init__(self) -> None:
        """Load libproc."""
        self._libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        self._libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)

    def stop(
        self, programs: Collection[Path], wait_s: float, *, mentioning: Path | None = None
    ) -> list[int]:
        """Stop the child processes of this app that run one of these programs.

        Args:
            programs: The programs.
            wait_s: How long a process may take to end before it is killed.
            mentioning: When given, only a child whose arguments name this folder.

        Returns:
            The process IDs that were stopped.
        """
        wanted = {str(program.resolve()) for program in programs}
        found = [
            pid
            for pid in self._children()
            if self._program_of(pid) in wanted
            and (mentioning is None or names_folder(self._arguments(pid), mentioning))
        ]
        for pid in found:
            self._signal(pid, signal.SIGTERM)
        deadline = time.monotonic() + wait_s
        left = list(found)
        while left and time.monotonic() < deadline:
            time.sleep(_POLL_S)
            left = [pid for pid in left if self._program_of(pid) in wanted]
        for pid in left:
            self._signal(pid, signal.SIGKILL)
        for pid in found:
            _log.info(
                "app.child_stopped",
                msg="A program the app started was stopped",
                pid=pid,
                killed=pid in left,
            )
        return found

    def _children(self) -> list[int]:
        pids = (ctypes.c_int * _MOST_CHILDREN)()
        count = self._libproc.proc_listchildpids(os.getpid(), pids, ctypes.sizeof(pids))
        return [pid for pid in pids[: max(count, 0)] if pid > 0]

    def _program_of(self, pid: int) -> str | None:
        path = ctypes.create_string_buffer(_PATH_SIZE)
        if self._libproc.proc_pidpath(pid, path, _PATH_SIZE) <= 0:
            return None
        return str(Path(os.fsdecode(path.value)).resolve())

    def _arguments(self, pid: int) -> list[str]:
        """Return the arguments of a process, through sysctl(KERN_PROCARGS2), or none."""
        size = ctypes.c_size_t(_ARGUMENTS_SIZE)
        found = ctypes.create_string_buffer(_ARGUMENTS_SIZE)
        names = (ctypes.c_int * 3)(_CTL_KERN, _KERN_PROCARGS2, pid)
        if self._libc.sysctl(names, 3, found, ctypes.byref(size), None, 0) != 0:
            return []
        raw = found.raw[: size.value]
        count = int.from_bytes(raw[:4], "little")
        # The program path comes first, then padding, then the arguments, each ended by NUL.
        parts = [part for part in raw[4:].split(b"\0")[1:] if part]
        return [os.fsdecode(part) for part in parts[:count]]

    def _signal(self, pid: int, number: signal.Signals) -> None:
        try:
            os.kill(pid, number)
        except ProcessLookupError:
            return
