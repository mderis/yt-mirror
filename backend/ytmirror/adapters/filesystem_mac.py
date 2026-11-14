"""The FileSystem port on macOS.

From milestone M2: folders of channels, the count of video files, showing a
folder in Finder, and the name and free space of a disk. File dates, the
Trash and safe moves arrive in milestone M3 (docs/ARCHITECTURE.md section 7.5).

This module must not delete or overwrite anything.

Tests: backend/tests/integration/test_file_system_contract.py
"""

import errno
import importlib
import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.ports.file_system import VIDEO_FILE_ENDINGS, Disk

type Run = Callable[[Sequence[str]], object]
"""Starts a program of macOS with its arguments."""

_OPEN = "/usr/bin/open"
_DENIED = (errno.EACCES, errno.EPERM, errno.EROFS)


class MacFileSystem:
    """Works on the real file system of the Mac."""

    def __init__(self, run: Run | None = None) -> None:
        """Create the adapter.

        Args:
            run: A stand-in for starting a program of macOS. For tests.
        """
        self._run = run if run is not None else _start

    def make_folder(self, folder: Path) -> None:
        """Create a folder and its parents. An existing folder is left as it is.

        Args:
            folder: The folder.

        Raises:
            AppError: ``PERMISSION_DENIED`` or ``FOLDER_UNAVAILABLE``.
        """
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            code = (
                ErrorCode.PERMISSION_DENIED
                if error.errno in _DENIED
                else ErrorCode.FOLDER_UNAVAILABLE
            )
            raise AppError(code, {"folder": str(folder), "reason": str(error)}) from error

    def folder_exists(self, folder: Path) -> bool:
        """Return whether a folder exists.

        Args:
            folder: The folder.
        """
        return folder.is_dir()

    def count_video_files(self, folder: Path) -> int:
        """Return how many video files lie directly in a folder (R-CH-06).

        Args:
            folder: The folder.
        """
        try:
            return sum(
                1
                for entry in folder.iterdir()
                if not entry.name.startswith(".")
                and entry.name.lower().endswith(VIDEO_FILE_ENDINGS)
                and entry.is_file()
            )
        except OSError:
            return 0

    def open_folder(self, folder: Path) -> None:
        """Show a folder in Finder (R-CH-30).

        Args:
            folder: The folder.

        Raises:
            AppError: ``FOLDER_UNAVAILABLE`` when the folder does not exist.
        """
        if not folder.is_dir():
            raise AppError(ErrorCode.FOLDER_UNAVAILABLE, {"folder": str(folder)})
        self._run([_OPEN, str(folder)])

    def disk_of(self, folder: Path) -> Disk:
        """Return the disk that holds a folder, or its nearest existing parent.

        Args:
            folder: The folder. It does not have to exist yet.
        """
        existing = folder
        while not existing.exists() and existing != existing.parent:
            existing = existing.parent
        return Disk(name=_volume_name(existing), free_bytes=shutil.disk_usage(existing).free)


def _start(command: Sequence[str]) -> object:  # pragma: no cover  (it opens a Finder window)
    return subprocess.run(list(command), check=False)


def _volume_name(path: Path) -> str:
    """Return the name of the volume a path is on, as Finder shows it."""
    foundation: Any = importlib.import_module("Foundation")
    url = foundation.NSURL.fileURLWithPath_(str(path))
    found, name, _error = url.getResourceValue_forKey_error_(
        None, foundation.NSURLVolumeNameKey, None
    )
    return str(name) if found and name else path.anchor
