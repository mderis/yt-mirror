"""The FileSystem port on macOS.

From milestone M2: folders of channels, the count of video files, showing a
folder in Finder, and the name and free space of a disk. From milestone M3
(docs/ARCHITECTURE.md section 7.5): file dates through ``setattrlist``
(D-077), moves that never overwrite through ``renamex_np``, the Trash of
macOS, and showing or opening a file.

This module deletes nothing for good except the temp folder of one job, and
it overwrites only when it is told to.

Tests: backend/tests/integration/test_file_system_contract.py
"""

import contextlib
import ctypes
import ctypes.util
import errno
import importlib
import os
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.ports.file_system import (
    JOB_ID,
    JOB_LOG_FOLDER,
    JOB_LOG_NAME,
    TEMP_FOLDER_PARTS,
    VIDEO_FILE_ENDINGS,
    Disk,
    FileDates,
)

type Run = Callable[[Sequence[str]], object]
"""Starts a program of macOS with its arguments."""

type Trash = Callable[[Path], None]
"""Moves a file or folder to the Trash of macOS."""

_OPEN = "/usr/bin/open"
_DENIED = (errno.EACCES, errno.EPERM, errno.EROFS)
_FULL = (errno.ENOSPC, errno.EDQUOT)

# setattrlist(2) and renamex_np(2) of macOS, through ctypes.
_ATTR_BIT_MAP_COUNT = 5
_ATTR_CMN_CRTIME = 0x00000200
_FSOPT_NOFOLLOW = 0x00000001
_RENAME_EXCL = 0x00000004
_RENAME_SWAP = 0x00000002


class _AttrList(ctypes.Structure):
    _fields_ = [
        ("bitmapcount", ctypes.c_ushort),
        ("reserved", ctypes.c_uint16),
        ("commonattr", ctypes.c_uint32),
        ("volattr", ctypes.c_uint32),
        ("dirattr", ctypes.c_uint32),
        ("fileattr", ctypes.c_uint32),
        ("forkattr", ctypes.c_uint32),
    ]


class _TimeSpec(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_nsec", ctypes.c_long)]


_libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
_libc.setattrlist.argtypes = [
    ctypes.c_char_p,
    ctypes.POINTER(_AttrList),
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.c_ulong,
]
_libc.renamex_np.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]


class MacFileSystem:
    """Works on the real file system of the Mac."""

    def __init__(
        self,
        run: Run | None = None,
        trash: Trash | None = None,
        free_bytes: Callable[[], int | None] | None = None,
    ) -> None:
        """Create the adapter.

        Args:
            run: A stand-in for starting a program of macOS. For tests.
            trash: A stand-in for the Trash of macOS. For tests, so that no
                test fills the Trash of the person who runs it.
            free_bytes: A stand-in for the free space of every disk, when it gives
                a number. For tests of the disk space guard, so that they never
                depend on the Mac that runs them (R-QU-10).
        """
        self._run = run if run is not None else _start
        self._trash = trash if trash is not None else _to_trash
        self._free_bytes = free_bytes

    def make_folder(self, folder: Path, *, inside: Path | None = None) -> None:
        """Create a folder and its parents. An existing folder is left as it is.

        Args:
            folder: The folder.
            inside: A folder that must be there and is never created. The
                folders below it are created one level at a time, so a folder
                that goes away meanwhile makes this fail instead of coming back.

        Raises:
            AppError: ``PERMISSION_DENIED`` or ``FOLDER_UNAVAILABLE``.
            ValueError: When ``folder`` is not inside ``inside``.
        """
        try:
            if inside is None:
                folder.mkdir(parents=True, exist_ok=True)
                return
            levels = folder.relative_to(inside).parts
            if not inside.is_dir():
                raise FileNotFoundError(2, "No such folder", str(inside))
            current = inside
            for level in levels:
                current = current / level
                current.mkdir(exist_ok=True)
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

    def drive_connected(self, path: Path) -> bool:
        """Return whether the drive of a path is connected: for /Volumes/<name>, it is mounted.

        Args:
            path: A file or folder, which need not exist.
        """
        parts = path.absolute().parts
        if len(parts) >= _VOLUME_PARTS and parts[1] == "Volumes":
            return os.path.ismount(Path(*parts[:_VOLUME_PARTS]))
        return True

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
        given = None if self._free_bytes is None else self._free_bytes()
        free = shutil.disk_usage(existing).free if given is None else given
        return Disk(name=_volume_name(existing), free_bytes=free)

    def file_names(self, folder: Path, *, hidden: bool = False) -> list[str]:
        """Return the names of the files and folders directly in a folder, sorted.

        Args:
            folder: The folder.
            hidden: Whether hidden names are given too.
        """
        try:
            return sorted(
                entry.name for entry in folder.iterdir() if hidden or not entry.name.startswith(".")
            )
        except OSError:
            return []

    def list_folder(self, folder: Path) -> list[str]:
        """Return every name directly in a folder, or raise when it cannot be listed.

        Args:
            folder: The folder.

        Raises:
            AppError: ``FOLDER_UNAVAILABLE`` for any error of the listing.
        """
        try:
            return [entry.name for entry in folder.iterdir()]
        except OSError as error:
            raise AppError(
                ErrorCode.FOLDER_UNAVAILABLE, {"folder": str(folder), "error": type(error).__name__}
            ) from error

    def exists(self, path: Path) -> bool:
        """Return whether a file or folder exists, without following a last symlink.

        Args:
            path: The file or folder.
        """
        return os.path.lexists(path)

    def is_gone(self, path: Path) -> bool:
        """Return whether a file is clearly not there, in a folder that is.

        Args:
            path: The file.
        """
        try:
            os.lstat(path)
        except FileNotFoundError:
            try:
                return stat.S_ISDIR(path.parent.stat().st_mode)
            except OSError:
                return False
        except OSError:
            return False
        return False

    def size_of(self, path: Path) -> int:
        """Return the size of a file, or of a folder with everything in it, in bytes.

        Args:
            path: The file or folder.
        """
        try:
            facts = path.lstat()
        except OSError:
            return 0
        if path.is_symlink() or not path.is_dir():
            return facts.st_size
        total = 0
        for root, _folders, names in os.walk(path):
            for name in names:
                with contextlib.suppress(OSError):
                    total += (Path(root) / name).lstat().st_size
        return total

    def read_bytes(self, path: Path) -> bytes | None:
        """Return the content of a file, or None when it cannot be read.

        Args:
            path: The file.
        """
        try:
            return path.read_bytes()
        except OSError:
            return None

    def is_inside(self, path: Path, folder: Path) -> bool:
        """Return whether a path stays inside a folder once every symlink is followed.

        Args:
            path: The file or folder.
            folder: The folder it must stay in.
        """
        return path.resolve().is_relative_to(folder.resolve())

    def write_file(self, path: Path, data: bytes, *, overwrite: bool, inside: Path) -> bool:
        """Write a whole file at once, so that no half-written file is ever seen.

        Args:
            path: The file. Its folder is created when missing, but only below ``inside``.
            data: The content.
            overwrite: Whether a file that is there may be replaced.
            inside: The folder the file belongs in. It must be there.

        Returns:
            False when the file is there and ``overwrite`` is false.

        Raises:
            AppError: ``PERMISSION_DENIED``, ``DISK_FULL`` or ``FOLDER_UNAVAILABLE``.
        """
        if not overwrite and os.path.lexists(path):
            return False
        self.make_folder(path.parent, inside=inside)
        try:
            handle, name = tempfile.mkstemp(dir=path.parent, prefix=".ytm-", suffix=".part")
            written = Path(name)
            try:
                with os.fdopen(handle, "wb") as file:
                    file.write(data)
                if overwrite:
                    written.replace(path)
                elif not _renamed(written, path):
                    return False
            finally:
                if os.path.lexists(written):
                    written.unlink()  # our own unfinished temp file, never the target
        except OSError as error:
            raise _error_of(error, path) from error
        return True

    def move(self, source: Path, target: Path) -> bool:
        """Move a file to its place in one step, on the same volume, never overwriting.

        Args:
            source: The file.
            target: Where it goes. It must not exist.

        Returns:
            False when something is at the target already.

        Raises:
            AppError: ``PERMISSION_DENIED`` or ``FOLDER_UNAVAILABLE``.
        """
        try:
            return _renamed(source, target)
        except OSError as error:
            raise _error_of(error, target) from error

    def swap(self, first: Path, second: Path) -> None:
        """Let two files on one volume swap places in one step (R-QL-06, D-093).

        Args:
            first: A file.
            second: Another file.

        Raises:
            AppError: ``PERMISSION_DENIED`` or ``FOLDER_UNAVAILABLE``.
        """
        if _libc.renamex_np(os.fsencode(first), os.fsencode(second), _RENAME_SWAP) != 0:
            number = ctypes.get_errno()
            error = OSError(number, os.strerror(number), str(first))
            raise _error_of(error, second) from error

    def file_id(self, path: Path) -> int:
        """Return what identifies a file on its volume (its inode); a move keeps it.

        Args:
            path: The file.

        Raises:
            AppError: ``FOLDER_UNAVAILABLE`` when it cannot be read.
        """
        try:
            return path.stat().st_ino
        except OSError as error:
            raise _error_of(error, path) from error

    def set_dates(self, path: Path, moment: int) -> None:
        """Set the creation and the modification date of a file to one moment (D-077).

        Args:
            path: The file.
            moment: Seconds since the epoch, UTC.

        Raises:
            AppError: ``DATES_NOT_APPLIED`` when macOS refuses.
        """
        attributes = _AttrList(_ATTR_BIT_MAP_COUNT, 0, _ATTR_CMN_CRTIME, 0, 0, 0, 0)
        created = _TimeSpec(moment, 0)
        if (
            _libc.setattrlist(
                os.fsencode(path),
                ctypes.byref(attributes),
                ctypes.byref(created),
                ctypes.sizeof(created),
                _FSOPT_NOFOLLOW,
            )
            != 0
        ):
            number = ctypes.get_errno()
            raise AppError(
                ErrorCode.DATES_NOT_APPLIED,
                {"file": str(path), "reason": os.strerror(number), "step": "creation date"},
            )
        try:
            os.utime(path, (moment, moment), follow_symlinks=False)
        except OSError as error:
            raise AppError(
                ErrorCode.DATES_NOT_APPLIED,
                {"file": str(path), "reason": str(error), "step": "modification date"},
            ) from error

    def read_dates(self, path: Path) -> FileDates:
        """Read the creation and the modification date of a file back.

        Args:
            path: The file.
        """
        facts = path.stat(follow_symlinks=False)
        return FileDates(created=int(facts.st_birthtime), modified=int(facts.st_mtime))

    def trash(self, path: Path) -> None:
        """Move a file or folder to the Trash of macOS, never deleting it for good.

        Args:
            path: The file or folder.

        Raises:
            AppError: ``PERMISSION_DENIED`` or ``FOLDER_UNAVAILABLE``.
        """
        try:
            self._trash(path)
        except OSError as error:
            raise _error_of(error, path) from error
        except Exception as error:
            # The file manager of macOS can fail in ways that are no OSError.
            raise AppError(
                ErrorCode.FOLDER_UNAVAILABLE, {"file": str(path), "reason": str(error)}
            ) from error

    def remove_temp_folder(self, folder: Path) -> None:
        """Delete the temp folder of one job with everything in it (R-FI-03).

        Args:
            folder: The temp folder of the job.

        Raises:
            ValueError: When the folder is not the temp folder of a job.
        """
        if (
            not JOB_ID.fullmatch(folder.name)
            or folder.parent.parts[-2:] != TEMP_FOLDER_PARTS
            or folder.is_symlink()
        ):
            raise ValueError(f"not the temp folder of a job: {folder}")
        shutil.rmtree(folder, ignore_errors=True)

    def remove_job_log(self, path: Path) -> None:
        """Delete the log of one job for good (R-LG-01).

        Args:
            path: The log file.

        Raises:
            ValueError: When the file is not the log of a job.
        """
        if (
            path.parent.name != JOB_LOG_FOLDER
            or not JOB_LOG_NAME.fullmatch(path.name)
            or path.is_symlink()
            or not path.is_file()
        ):
            raise ValueError(f"not the log of a job: {path}")
        path.unlink()

    def reveal(self, path: Path) -> None:
        """Show a file selected in Finder (R-UI-10).

        Args:
            path: The file.

        Raises:
            AppError: ``FILE_MISSING`` when the file is not in its folder, or
                ``FOLDER_UNAVAILABLE`` when its folder cannot be reached.
        """
        _must_be_there(path)
        self._run([_OPEN, "-R", str(path)])

    def open_file(self, path: Path) -> None:
        """Open a file with the default app of macOS (R-UI-10).

        Args:
            path: The file.

        Raises:
            AppError: ``FILE_MISSING`` when the file is not in its folder, or
                ``FOLDER_UNAVAILABLE`` when its folder cannot be reached.
        """
        _must_be_there(path)
        self._run([_OPEN, str(path)])


def _renamed(source: Path, target: Path) -> bool:
    """Rename in one step unless the target exists. Returns whether it was renamed."""
    if _libc.renamex_np(os.fsencode(source), os.fsencode(target), _RENAME_EXCL) == 0:
        return True
    number = ctypes.get_errno()
    if number == errno.EEXIST:
        return False
    raise OSError(number, os.strerror(number), str(target))


def _error_of(error: OSError, path: Path) -> AppError:
    """Return the error code of a failed file operation."""
    if error.errno in _DENIED:
        code = ErrorCode.PERMISSION_DENIED
    elif error.errno in _FULL:
        code = ErrorCode.DISK_FULL
    else:
        code = ErrorCode.FOLDER_UNAVAILABLE
    return AppError(code, {"file": str(path), "reason": str(error)})


def _to_trash(path: Path) -> None:  # pragma: no cover  (fills the real Trash. Tested by hand)
    """Move a file or folder to the Trash with the file manager of macOS."""
    foundation: Any = importlib.import_module("Foundation")
    url = foundation.NSURL.fileURLWithPath_(str(path))
    moved, _result, problem = (
        foundation.NSFileManager.defaultManager().trashItemAtURL_resultingItemURL_error_(
            url, None, None
        )
    )
    if not moved:
        raise OSError(errno.EIO, str(problem), str(path))


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


_VOLUME_PARTS = 3
"""The parts of the mount point of a drive: "/", "Volumes", its name."""


def _must_be_there(path: Path) -> None:
    """Raise the code that says why a file to play or show is not there."""
    if path.is_file():
        return
    if path.parent.is_dir():
        raise AppError(ErrorCode.FILE_MISSING, {"file": str(path)})
    raise AppError(ErrorCode.FOLDER_UNAVAILABLE, {"file": str(path)})
