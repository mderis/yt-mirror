"""The FileSystem port: what the app does with folders on the Mac.

From milestone M2: the folder of a channel (R-FI-01, R-CH-30), the video
files a folder already has (R-CH-06), and the disk a folder is on (R-UI-01).
File dates, safe moves and the Trash arrive in milestone M3.

Tests: backend/tests/integration/test_file_system_contract.py
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

VIDEO_FILE_ENDINGS = (".mkv", ".mp4", ".webm", ".mov", ".m4v", ".avi")
"""What the name of a video file ends in (R-CH-06), compared without regard to case."""


@dataclass(frozen=True, slots=True)
class Disk:
    """The disk a folder is on (R-UI-01).

    Attributes:
        name: The name of the volume, as Finder shows it.
        free_bytes: How much room is left on it.
    """

    name: str
    free_bytes: int


class FileSystem(Protocol):
    """Creates, counts and shows folders."""

    def make_folder(self, folder: Path) -> None:
        """Create a folder and its parents. An existing folder is left as it is.

        Args:
            folder: The folder.

        Raises:
            AppError: ``PERMISSION_DENIED`` when macOS denies it, ``FOLDER_UNAVAILABLE``
                when it cannot be created for another reason, for example a drive
                that is not connected.
        """
        ...

    def folder_exists(self, folder: Path) -> bool:
        """Return whether a folder exists.

        Args:
            folder: The folder.
        """
        ...

    def count_video_files(self, folder: Path) -> int:
        """Return how many video files lie directly in a folder (R-CH-06).

        Hidden files and files in subfolders are not counted. A folder that
        does not exist or cannot be read has none.

        Args:
            folder: The folder.
        """
        ...

    def open_folder(self, folder: Path) -> None:
        """Show a folder in Finder (R-CH-30).

        Args:
            folder: The folder.

        Raises:
            AppError: ``FOLDER_UNAVAILABLE`` when the folder does not exist.
        """
        ...

    def disk_of(self, folder: Path) -> Disk:
        """Return the disk that holds a folder, or its nearest existing parent.

        Args:
            folder: The folder. It does not have to exist yet.
        """
        ...
