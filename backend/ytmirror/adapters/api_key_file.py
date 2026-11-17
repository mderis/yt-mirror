"""The ApiKeyStore port as a file of its own in the data folder.

Implements D-085 (R-DT-12, R-SE-03). The key is kept in
``data/youtube-api-key``, readable and writable only by the user (mode 0600).
A new key is written to a new file created with mode 0600 in the same
folder, flushed to disk, and renamed over the old one, so the file is
never half written and never readable by others, not even for a moment.
Removing the key deletes the file; it does not go to the Trash.

The key is never written to a log or into an error by this module.

Tests: backend/tests/integration/test_api_key_store_contract.py
"""

import os
import secrets
import stat
from pathlib import Path

from ytmirror.core.errors import AppError, ErrorCode

FILE_NAME = "youtube-api-key"
_ONLY_THE_USER = 0o600


class ApiKeyFile:
    """Keeps the API key in one file that only the user can read."""

    def __init__(self, data_dir: Path) -> None:
        """Keep the key in a data folder.

        Args:
            data_dir: The data folder of the app.
        """
        self._folder = data_dir
        self.path = data_dir / FILE_NAME

    def read(self) -> str | None:
        """Return the saved key, or None when there is no file.

        A file that others could read is made private again first.

        Raises:
            AppError: ``API_KEY_UNREADABLE`` when the file is there but cannot be
                read, or holds no key.
        """
        try:
            if stat.S_IMODE(self.path.stat().st_mode) != _ONLY_THE_USER:
                self.path.chmod(_ONLY_THE_USER)
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except (OSError, UnicodeDecodeError) as error:
            raise AppError(ErrorCode.API_KEY_UNREADABLE, {"error": type(error).__name__}) from error
        key = text.strip()
        if not key:
            raise AppError(ErrorCode.API_KEY_UNREADABLE, {"error": "the file is empty"})
        return key

    def write(self, key: str) -> None:
        """Save a key all at once, in a file only the user can read.

        Raises:
            AppError: ``API_KEY_UNREADABLE`` when it cannot be written.
        """
        temp = self._folder / f".{FILE_NAME}.{secrets.token_hex(8)}.tmp"
        try:
            self._folder.mkdir(parents=True, exist_ok=True)
            handle = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, _ONLY_THE_USER)
            try:
                os.write(handle, f"{key}\n".encode())
                os.fsync(handle)
            finally:
                os.close(handle)
            temp.replace(self.path)
            folder = os.open(self._folder, os.O_RDONLY)
            try:
                os.fsync(folder)
            finally:
                os.close(folder)
        except OSError as error:
            temp.unlink(missing_ok=True)
            raise AppError(ErrorCode.API_KEY_UNREADABLE, {"error": type(error).__name__}) from error

    def remove(self) -> None:
        """Delete the file of the key, if there is one."""
        self.path.unlink(missing_ok=True)
