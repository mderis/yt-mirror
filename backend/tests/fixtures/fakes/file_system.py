"""Folders and files that exist only in memory. Fake of the FileSystem port."""

from dataclasses import dataclass
from pathlib import Path

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

_NEW_FILE_TIME = 1_794_000_000


@dataclass
class FakeFile:
    """A file in memory: its content and its two dates."""

    data: bytes
    created: int = _NEW_FILE_TIME
    modified: int = _NEW_FILE_TIME


class FakeFileSystem:
    """Remembers folders and the files in them, with their contents and dates.

    Attributes:
        opened: The folders that were shown in Finder, in order.
        revealed: The files that were shown selected in Finder, in order.
        played: The files that were opened with their default app, in order.
        trashed: Every file or folder moved to the Trash, in order.
        denied: Folders that macOS does not let the app create.
        unavailable: Folders that cannot be created, as on a drive that is not connected.
        disconnected: Drives, as their mount points, that are not connected: nothing
            under them can be seen.
        refuse_dates: Files whose dates cannot be set.
        drift_dates: Files whose creation date reads back one hour off, as on a volume
            that does not keep it.
        outside: Paths that lead out of their folder through a symlink.
        uncheckable: Files whose presence cannot be checked, as without permission.
        disk: The disk every folder is on.
    """

    def __init__(self) -> None:
        """Start without any folder."""
        self.folders: set[Path] = set()
        self.files: dict[Path, FakeFile] = {}
        self.opened: list[Path] = []
        self.revealed: list[Path] = []
        self.played: list[Path] = []
        self.trashed: list[Path] = []
        self.denied: set[Path] = set()
        self.unavailable: set[Path] = set()
        self.disconnected: set[Path] = set()
        self.unlistable: set[Path] = set()
        """Folders whose listing fails, as one that cannot be read."""
        self.refuse_dates: set[Path] = set()
        self.drift_dates: set[Path] = set()
        self.outside: set[Path] = set()
        self.uncheckable: set[Path] = set()
        self.disk = Disk(name="Macintosh HD", free_bytes=182 * 1000**3)

    def add_files(self, folder: Path, names: list[str], data: bytes = b"x") -> None:
        """Put files into a folder, creating it. For tests."""
        self._add_folder(folder)
        for name in names:
            self.files[folder / name] = FakeFile(data)

    def _add_folder(self, folder: Path) -> None:
        self.folders.update({folder, *folder.parents})

    def make_folder(self, folder: Path, *, inside: Path | None = None) -> None:
        """Remember the folder, or fail as configured. ``inside`` must be there."""
        if inside is not None:
            folder.relative_to(inside)
            if inside not in self.folders:
                raise AppError(ErrorCode.FOLDER_UNAVAILABLE, {"folder": str(inside)})
        if folder in self.denied:
            raise AppError(ErrorCode.PERMISSION_DENIED, {"folder": str(folder)})
        if folder in self.unavailable:
            raise AppError(ErrorCode.FOLDER_UNAVAILABLE, {"folder": str(folder)})
        self._add_folder(folder)

    def folder_exists(self, folder: Path) -> bool:
        """Return whether the folder was created, on a drive that is connected."""
        return folder in self.folders and self.drive_connected(folder)

    def drive_connected(self, path: Path) -> bool:
        """Return whether the path lies on no drive that is disconnected."""
        return not any(path.is_relative_to(drive) for drive in self.disconnected)

    def count_video_files(self, folder: Path) -> int:
        """Count the files of the folder that are video files and not hidden."""
        return sum(
            1
            for name in self.file_names(folder)
            if name.lower().endswith(VIDEO_FILE_ENDINGS) and folder / name in self.files
        )

    def open_folder(self, folder: Path) -> None:
        """Remember that the folder was shown, or fail when it does not exist."""
        if folder not in self.folders:
            raise AppError(ErrorCode.FOLDER_UNAVAILABLE, {"folder": str(folder)})
        self.opened.append(folder)

    def disk_of(self, folder: Path) -> Disk:
        """Return the configured disk."""
        return self.disk

    def file_names(self, folder: Path, *, hidden: bool = False) -> list[str]:
        """Return the names directly in the folder, the hidden ones only when asked."""
        names = {path.name for path in [*self.files, *self.folders] if path.parent == folder}
        return sorted(name for name in names if hidden or not name.startswith("."))

    def list_folder(self, folder: Path) -> list[str]:
        """Return every name in the folder, or fail as an unreadable or missing folder."""
        if not self.folder_exists(folder) or folder in self.unlistable:
            raise AppError(ErrorCode.FOLDER_UNAVAILABLE, {"folder": str(folder)})
        return self.file_names(folder, hidden=True)

    def exists(self, path: Path) -> bool:
        """Return whether a file or folder is there, on a drive that is connected."""
        return (path in self.files or path in self.folders) and self.drive_connected(path)

    def is_gone(self, path: Path) -> bool:
        """Return whether a file is clearly not there, in a folder that is, and can be checked."""
        return (
            path not in self.files
            and path not in self.folders
            and path not in self.uncheckable
            and path.parent in self.folders
            and self.drive_connected(path)
        )

    def size_of(self, path: Path) -> int:
        """Return the size of the file, or of everything in the folder, or 0."""
        return sum(
            len(file.data)
            for place, file in self.files.items()
            if place == path or place.is_relative_to(path)
        )

    def read_bytes(self, path: Path) -> bytes | None:
        """Return the content of the file, or None."""
        file = self.files.get(path)
        return None if file is None else file.data

    def is_inside(self, path: Path, folder: Path) -> bool:
        """Return whether the path is in the folder and not marked as leading out."""
        return path not in self.outside and path.is_relative_to(folder)

    def write_file(self, path: Path, data: bytes, *, overwrite: bool, inside: Path) -> bool:
        """Store the file unless it is there and must not be replaced."""
        if not overwrite and self.exists(path):
            return False
        self.make_folder(path.parent, inside=inside)
        self.files[path] = FakeFile(data)
        return True

    def move(self, source: Path, target: Path) -> bool:
        """Move a file, never onto something that is there."""
        if self.exists(target):
            return False
        if source not in self.files or target.parent not in self.folders:
            raise AppError(ErrorCode.FOLDER_UNAVAILABLE, {"file": str(source)})
        self.files[target] = self.files.pop(source)
        return True

    def swap(self, first: Path, second: Path) -> None:
        """Let two files swap places."""
        if first not in self.files or second not in self.files:
            raise AppError(ErrorCode.FOLDER_UNAVAILABLE, {"file": str(first)})
        self.files[first], self.files[second] = self.files[second], self.files[first]

    def file_id(self, path: Path) -> int:
        """Return the identity of the file object, which a move or a swap keeps."""
        if path not in self.files:
            raise AppError(ErrorCode.FOLDER_UNAVAILABLE, {"file": str(path)})
        return id(self.files[path])

    def set_dates(self, path: Path, moment: int) -> None:
        """Set both dates, or fail as configured."""
        if path in self.refuse_dates or path not in self.files:
            raise AppError(ErrorCode.DATES_NOT_APPLIED, {"file": str(path)})
        self.files[path].created = moment
        self.files[path].modified = moment

    def read_dates(self, path: Path) -> FileDates:
        """Return both dates of the file."""
        file = self.files[path]
        drift = 3600 if path in self.drift_dates else 0
        return FileDates(created=file.created + drift, modified=file.modified)

    def trash(self, path: Path) -> None:
        """Remember the move to the Trash, and take the file or folder away with its content."""
        if not self.exists(path):
            raise AppError(ErrorCode.FOLDER_UNAVAILABLE, {"file": str(path)})
        self.trashed.append(path)
        self._take_away(path)

    def remove_temp_folder(self, folder: Path) -> None:
        """Take the temp folder of a job away, or refuse any other folder."""
        if not JOB_ID.fullmatch(folder.name) or folder.parent.parts[-2:] != TEMP_FOLDER_PARTS:
            raise ValueError(f"not the temp folder of a job: {folder}")
        self._take_away(folder)

    def _take_away(self, path: Path) -> None:
        for file in [file for file in self.files if file == path or file.is_relative_to(path)]:
            del self.files[file]
        self.folders = {
            folder for folder in self.folders if folder != path and not folder.is_relative_to(path)
        }

    def remove_job_log(self, path: Path) -> None:
        """Delete a job log, or refuse any other file."""
        if (
            path.parent.name != JOB_LOG_FOLDER
            or not JOB_LOG_NAME.fullmatch(path.name)
            or path not in self.files
        ):
            raise ValueError(f"not the log of a job: {path}")
        del self.files[path]

    def _must_be_there(self, path: Path) -> None:
        if path in self.files and self.drive_connected(path):
            return
        if self.folder_exists(path.parent):
            raise AppError(ErrorCode.FILE_MISSING, {"file": str(path)})
        raise AppError(ErrorCode.FOLDER_UNAVAILABLE, {"file": str(path)})

    def reveal(self, path: Path) -> None:
        """Remember that the file was shown in Finder."""
        self._must_be_there(path)
        self.revealed.append(path)

    def open_file(self, path: Path) -> None:
        """Remember that the file was opened."""
        self._must_be_there(path)
        self.played.append(path)
