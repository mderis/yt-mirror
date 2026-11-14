"""The ToolBox port: where downloaded tools are fetched to, kept and run.

The tools are ffmpeg with ffprobe, and Deno (R-IN-03, R-IN-04). They live in
``tools/`` inside the app folder (docs/DECISIONS.md D-018). A tool is
fetched and unpacked into a staging area first and only then put in place,
so a tool that is in place was always complete.

Tests: backend/tests/integration/test_tool_box_contract.py
"""

from collections.abc import Callable, Sequence
from typing import Protocol

from ytmirror.core.models import InstalledTool, ToolFile, ToolName

type Progress = Callable[[int, int | None], None]
"""Called while a file arrives: the bytes received so far, and the size of the file
or None when the server did not say."""


class ToolBox(Protocol):
    """Fetches, unpacks, keeps and runs the tools."""

    def installed(self, tool: ToolName) -> InstalledTool | None:
        """Return what was written down when a tool was put in place, or None.

        Args:
            tool: The tool.
        """
        ...

    def run(self, tool: ToolName, program: str, arguments: Sequence[str]) -> str | None:
        """Run a program of a tool that is in place and return its first line of output.

        Args:
            tool: The tool.
            program: The name of the program.
            arguments: Its arguments.

        Returns:
            The first line it printed, or None when the program is missing,
            cannot be run, or ends with an error.
        """
        ...

    def fetch(self, tool: ToolName, file: ToolFile, on_progress: Progress) -> str:
        """Download a file of a tool into the staging area.

        Args:
            tool: The tool.
            file: The file to download.
            on_progress: Called while the file arrives.

        Returns:
            The SHA-256 of what arrived, in lower-case hexadecimal.

        Raises:
            AppError: ``NETWORK_UNREACHABLE`` when the file cannot be downloaded,
                ``DISK_FULL`` when there is no room for it.
        """
        ...

    def unpack(self, tool: ToolName, file: ToolFile) -> None:
        """Take the programs of a fetched file out of its archive, into the staging area.

        Args:
            tool: The tool.
            file: A file that was fetched before.

        Raises:
            AppError: ``DISK_FULL`` when there is no room for the programs.
            ValueError: When the archive does not hold the programs.
        """
        ...

    def commit(self, tool: ToolName, installed: InstalledTool) -> None:
        """Put the unpacked programs in place of the tool and write down where they came from.

        Args:
            tool: The tool.
            installed: The source and the version of what was unpacked.
        """
        ...

    def clear(self, tool: ToolName) -> None:
        """Empty the staging area of a tool. A tool that is in place stays.

        Args:
            tool: The tool.
        """
        ...
