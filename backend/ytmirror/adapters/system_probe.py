"""Reads facts about the Mac: implements the SystemProbe port.

This module only reads. It must never change anything on the system.

Tests: backend/tests/integration/test_system_probe_contract.py
"""

import importlib.util
import os
import platform
import shutil
import subprocess
from pathlib import Path

_VERSION_TIMEOUT_S = 10


class MacSystemProbe:
    """Answers questions about the operating system and the tools on it."""

    def os_version(self) -> str:
        """Return the macOS version, for example ``15.6.1``."""
        return platform.mac_ver()[0]

    def cpu_architecture(self) -> str:
        """Return the processor architecture, ``arm64`` or ``x86_64`` on a Mac."""
        return platform.machine()

    def python_version(self) -> str:
        """Return the version of the running Python."""
        return platform.python_version()

    def command_version(self, command: str) -> str | None:
        """Return the first line a program prints for ``--version``.

        Args:
            command: A program name to find on PATH, or the path of a program.

        Returns:
            The version line, or None when the program is missing or does not run.
        """
        executable = shutil.which(command)
        if executable is None:
            return None
        try:
            result = subprocess.run(
                [executable, "--version"],
                capture_output=True,
                text=True,
                timeout=_VERSION_TIMEOUT_S,
                check=False,
            )
        except OSError, subprocess.TimeoutExpired:
            return None
        lines = (result.stdout or result.stderr).strip().splitlines()
        if result.returncode != 0 or not lines:
            return None
        return lines[0].strip()

    def module_available(self, name: str) -> bool:
        """Return whether a Python module can be imported.

        Args:
            name: The module name.
        """
        return importlib.util.find_spec(name) is not None

    def file_exists(self, path: Path) -> bool:
        """Return whether a regular file exists at the path.

        Args:
            path: The path to look at.
        """
        return path.is_file()

    def can_write_to(self, folder: Path) -> bool:
        """Return whether files can be created in a folder, or in its nearest existing parent.

        Args:
            folder: The folder. It does not have to exist yet.
        """
        return os.access(_nearest_existing(folder), os.W_OK | os.X_OK)

    def free_bytes(self, folder: Path) -> int:
        """Return the free space of the volume that holds a folder.

        Args:
            folder: The folder. It does not have to exist yet.
        """
        return shutil.disk_usage(_nearest_existing(folder)).free


def _nearest_existing(folder: Path) -> Path:
    """Return the folder itself, or its closest parent that exists."""
    current = folder
    while not current.exists() and current != current.parent:
        current = current.parent
    return current
