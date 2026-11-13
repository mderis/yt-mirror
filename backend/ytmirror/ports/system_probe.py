"""The SystemProbe port: read-only facts about the Mac the app runs on.

Used by the environment report of ``./start --doctor``.

Tests: backend/tests/integration/test_system_probe_contract.py
"""

from pathlib import Path
from typing import Protocol


class SystemProbe(Protocol):
    """Answers questions about the operating system and the tools on it."""

    def os_version(self) -> str:
        """Return the macOS version, for example ``15.6.1``."""
        ...

    def cpu_architecture(self) -> str:
        """Return the processor architecture, ``arm64`` or ``x86_64`` on a Mac."""
        ...

    def python_version(self) -> str:
        """Return the version of the running Python, for example ``3.14.10``."""
        ...

    def command_version(self, command: str) -> str | None:
        """Return the first line a program prints for ``--version``.

        Args:
            command: A program name to find on PATH, or the path of a program.

        Returns:
            The version line, or None when the program is missing or does not run.
        """
        ...

    def module_available(self, name: str) -> bool:
        """Return whether a Python module can be imported.

        Args:
            name: The module name.
        """
        ...

    def file_exists(self, path: Path) -> bool:
        """Return whether a regular file exists at the path.

        Args:
            path: The path to look at.
        """
        ...

    def can_write_to(self, folder: Path) -> bool:
        """Return whether files can be created in a folder, or in its nearest existing parent.

        Args:
            folder: The folder. It does not have to exist yet.
        """
        ...

    def free_bytes(self, folder: Path) -> int:
        """Return the free space of the volume that holds a folder.

        Args:
            folder: The folder. It does not have to exist yet.
        """
        ...
