"""Folders that exist only in memory. Fake of the FileSystem port."""

from pathlib import Path

from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.ports.file_system import VIDEO_FILE_ENDINGS, Disk


class FakeFileSystem:
    """Remembers folders and the names of the files in them.

    Attributes:
        opened: The folders that were shown in Finder, in order.
        denied: Folders that macOS does not let the app create.
        unavailable: Folders that cannot be created, as on a drive that is not connected.
        disk: The disk every folder is on.
    """

    def __init__(self) -> None:
        """Start without any folder."""
        self._files: dict[Path, list[str]] = {}
        self.opened: list[Path] = []
        self.denied: set[Path] = set()
        self.unavailable: set[Path] = set()
        self.disk = Disk(name="Macintosh HD", free_bytes=182 * 1000**3)

    def add_files(self, folder: Path, names: list[str]) -> None:
        """Put files into a folder, creating it. For tests."""
        self._files.setdefault(folder, []).extend(names)

    def make_folder(self, folder: Path) -> None:
        """Remember the folder, or fail as configured."""
        if folder in self.denied:
            raise AppError(ErrorCode.PERMISSION_DENIED, {"folder": str(folder)})
        if folder in self.unavailable:
            raise AppError(ErrorCode.FOLDER_UNAVAILABLE, {"folder": str(folder)})
        self._files.setdefault(folder, [])

    def folder_exists(self, folder: Path) -> bool:
        """Return whether the folder was created."""
        return folder in self._files

    def count_video_files(self, folder: Path) -> int:
        """Count the remembered names that are video files and not hidden."""
        return sum(
            1
            for name in self._files.get(folder, [])
            if not name.startswith(".") and name.lower().endswith(VIDEO_FILE_ENDINGS)
        )

    def open_folder(self, folder: Path) -> None:
        """Remember that the folder was shown, or fail when it does not exist."""
        if folder not in self._files:
            raise AppError(ErrorCode.FOLDER_UNAVAILABLE, {"folder": str(folder)})
        self.opened.append(folder)

    def disk_of(self, folder: Path) -> Disk:
        """Return the configured disk."""
        return self.disk
