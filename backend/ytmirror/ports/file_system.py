"""The FileSystem port: what the app does with folders on the Mac.

From milestone M2: the folder of a channel (R-FI-01, R-CH-30), the video
files a folder already has (R-CH-06), and the disk a folder is on (R-UI-01).
From milestone M3: file dates (R-DT-07), moves that never overwrite
(R-FN-05), the Trash (R-CH-32), and showing or opening a file (R-UI-10).
Nothing here deletes a file for good, except the temp folder of a job of
the app's own (R-FI-03).

Tests: backend/tests/integration/test_file_system_contract.py
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ytmirror.core.naming import HIDDEN_DIR, TEMP_DIR

VIDEO_FILE_ENDINGS = (".mkv", ".mp4", ".webm", ".mov", ".m4v", ".avi")
"""What the name of a video file ends in (R-CH-06), compared without regard to case."""


class SwapNotSupportedError(Exception):
    """The volume cannot swap two files in one step (exFAT, many network volumes, D-093).

    Nothing was changed. It never means that a folder cannot be reached.
    """


@dataclass(frozen=True, slots=True)
class Disk:
    """The disk a folder is on (R-UI-01).

    Attributes:
        name: The name of the volume, as Finder shows it.
        free_bytes: How much room is left on it.
    """

    name: str
    free_bytes: int


TEMP_FOLDER_PARTS = (HIDDEN_DIR, TEMP_DIR)
JOB_LOG_FOLDER = "jobs"
"""The folder of the logs of jobs, inside the logs folder (docs/LOGGING.md section 3)."""
JOB_ID = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
"""A job ID: a ULID. The temp folder of a job is named by it, and nothing else is."""
JOB_LOG_NAME = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}\.log$")
"""The name of the log of a job: its ULID and ``.log``. No other file is ever deleted there."""
"""Where the temp folders of jobs are, inside a channel folder (R-FI-03)."""


@dataclass(frozen=True, slots=True)
class FileDates:
    """The creation and modification date of a file, in whole seconds since the epoch, UTC.

    Attributes:
        created: The creation date, as Finder shows it.
        modified: The modification date.
    """

    created: int
    modified: int


class FileSystem(Protocol):
    """Creates, counts and shows folders."""

    def make_folder(self, folder: Path, *, inside: Path | None = None) -> None:
        """Create a folder and its parents. An existing folder is left as it is.

        Args:
            folder: The folder.
            inside: A folder that must be there already and is never created,
                for example the channel folder: only the folders below it are
                created. A removal that moved it to the Trash is never undone.

        Raises:
            AppError: ``PERMISSION_DENIED`` when macOS denies it, ``FOLDER_UNAVAILABLE``
                when it cannot be created for another reason, for example a drive
                that is not connected, or when ``inside`` is not there.
            ValueError: When ``folder`` is not inside ``inside``.
        """
        ...

    def folder_exists(self, folder: Path) -> bool:
        """Return whether a folder exists.

        Args:
            folder: The folder.
        """
        ...

    def list_folder(self, folder: Path) -> list[str]:
        """Return every name directly in a folder, hidden ones too, or fail.

        Unlike ``file_names`` a listing that fails is an error, never an empty
        folder: only a name missing from a listing that worked is missing (R-MI-06).

        Args:
            folder: The folder.

        Raises:
            AppError: ``FOLDER_UNAVAILABLE`` when the folder cannot be listed.
        """
        ...

    def drive_connected(self, path: Path) -> bool:
        """Return whether the drive a path is on is connected (R-QU-11, R-MI-06).

        A folder that is not there on a connected drive was deleted; one on a
        drive that is not connected is only unavailable.

        Args:
            path: A file or folder, which need not exist.
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

    def file_names(self, folder: Path, *, hidden: bool = False) -> list[str]:
        """Return the names of the files and folders directly in a folder, sorted.

        A folder that does not exist or cannot be read has none.

        Args:
            folder: The folder.
            hidden: Whether hidden names (starting with a dot) are given too.
        """
        ...

    def exists(self, path: Path) -> bool:
        """Return whether a file or folder exists, without following a last symlink.

        Args:
            path: The file or folder.
        """
        ...

    def is_gone(self, path: Path) -> bool:
        """Return whether a file is clearly not there, in a folder that is (R-MI-06).

        Only a clear "not found" in a folder that can be reached counts. A file
        that cannot be checked (no permission, a drive that went away) is not gone.

        Args:
            path: The file.
        """
        ...

    def size_of(self, path: Path) -> int:
        """Return the size of a file, or of a folder with everything in it, in bytes.

        Symlinks are not followed. Something that does not exist has 0.

        Args:
            path: The file or folder.
        """
        ...

    def is_inside(self, path: Path, folder: Path) -> bool:
        """Return whether a path stays inside a folder once every symlink is followed.

        Used before anything is moved to the Trash, so that no symlink leads
        out of a channel folder (R-CH-32).

        Args:
            path: The file or folder.
            folder: The folder it must stay in.
        """
        ...

    def read_bytes(self, path: Path) -> bytes | None:
        """Return the content of a file, or None when it cannot be read.

        Args:
            path: The file.
        """
        ...

    def write_file(self, path: Path, data: bytes, *, overwrite: bool, inside: Path) -> bool:
        """Write a whole file at once, so that no half-written file is ever seen (R-QA-06).

        A short-lived hidden temp file is written next to the file, so this is
        for files of the hidden folder. A visible file is written into the
        temp folder of its job and moved (R-FI-03).

        Args:
            path: The file. Its folder is created when missing, but only below ``inside``.
            data: The content.
            overwrite: Whether a file that is there may be replaced. Only files
                of the app's own hidden folder are ever replaced.
            inside: The folder the file belongs in, usually the channel folder.
                It must be there: it is never created (see ``make_folder``).

        Returns:
            False when the file is there and ``overwrite`` is false: nothing was written.

        Raises:
            AppError: ``PERMISSION_DENIED``, ``DISK_FULL`` or ``FOLDER_UNAVAILABLE``.
            ValueError: When ``path`` is not inside ``inside``.
        """
        ...

    def move(self, source: Path, target: Path) -> bool:
        """Move a file to its place in one step, on the same volume, never overwriting.

        Args:
            source: The file.
            target: Where it goes. It must not exist.

        Returns:
            False when something is at the target already: nothing was moved (R-FN-05).

        Raises:
            AppError: ``PERMISSION_DENIED`` or ``FOLDER_UNAVAILABLE``.
        """
        ...

    def swap(self, first: Path, second: Path) -> None:
        """Let two files on one volume swap places in one step (R-QL-06, D-093).

        Args:
            first: A file.
            second: Another file.

        Raises:
            SwapNotSupportedError: The volume cannot swap; nothing was changed.
            AppError: ``PERMISSION_DENIED`` or ``FOLDER_UNAVAILABLE``.
        """
        ...

    def file_id(self, path: Path) -> int:
        """Return what identifies a file on its volume; a move or a swap keeps it.

        Args:
            path: The file.

        Raises:
            AppError: ``FOLDER_UNAVAILABLE`` when it cannot be read.
        """
        ...

    def set_dates(self, path: Path, moment: int) -> None:
        """Set the creation and the modification date of a file to one moment (R-DT-07).

        Args:
            path: The file.
            moment: Seconds since the epoch, UTC.

        Raises:
            AppError: ``DATES_NOT_APPLIED`` when macOS refuses.
        """
        ...

    def read_dates(self, path: Path) -> FileDates:
        """Read the creation and the modification date of a file back (R-DT-07).

        Args:
            path: The file.
        """
        ...

    def trash(self, path: Path) -> None:
        """Move a file or folder to the Trash of macOS, never deleting it for good (R-CH-32).

        Args:
            path: The file or folder.

        Raises:
            AppError: ``PERMISSION_DENIED`` or ``FOLDER_UNAVAILABLE``.
        """
        ...

    def remove_temp_folder(self, folder: Path) -> None:
        """Delete the temp folder of one job with everything in it (R-FI-03).

        Only a folder directly inside ``<channel folder>/.yt-mirror/tmp/`` is
        ever deleted. A folder that is not there is fine.

        Args:
            folder: The temp folder of the job.

        Raises:
            ValueError: When the folder is not the temp folder of a job.
        """
        ...

    def remove_partial_file(self, path: Path) -> None:
        """Delete one partial file of a download from the temp folder of its job (D-091).

        For the parts of formats a download no longer fetches. Only a file
        directly inside the temp folder of a job is ever deleted. One that is not
        there is fine.

        Args:
            path: The file.

        Raises:
            ValueError: When the file is not directly inside the temp folder of a job.
        """
        ...

    def remove_job_log(self, path: Path) -> None:
        """Delete the log of one job for good (R-LG-01).

        Only a file directly in a ``jobs`` folder whose name is a ULID and
        ``.log`` is ever deleted.

        Args:
            path: The log file.

        Raises:
            ValueError: When the file is not the log of a job.
        """
        ...

    def reveal(self, path: Path) -> None:
        """Show a file selected in Finder (R-UI-10).

        Args:
            path: The file.

        Raises:
            AppError: ``FOLDER_UNAVAILABLE`` when the file is not there.
        """
        ...

    def open_file(self, path: Path) -> None:
        """Open a file with the default app of macOS (R-UI-10).

        Args:
            path: The file.

        Raises:
            AppError: ``FOLDER_UNAVAILABLE`` when the file is not there.
        """
        ...
