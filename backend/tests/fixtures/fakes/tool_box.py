"""Tools that exist only in memory. Fake of the ToolBox port.

A download is described by ``fake_archive``: which programs the archive
holds and what each prints when it is run. A test can also make an address
fail, or make a program refuse to run.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence

from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.models import ArchiveKind, InstalledTool, ToolFile, ToolName
from ytmirror.ports.tool_box import Progress


def fake_archive(kind: ArchiveKind, programs: Mapping[str, str]) -> bytes:
    """Return the bytes of a pretend archive: program name to what the program prints."""
    return json.dumps({"kind": kind.value, "programs": dict(programs)}).encode("utf-8")


class FakeToolBox:
    """Keeps downloads, staging areas and installed tools in dictionaries."""

    def __init__(self) -> None:
        """Start with no tools and nothing to download."""
        self.downloads: dict[str, bytes] = {}
        self.unreachable: set[str] = set()
        self.full_disk = False
        self.refusing: set[str] = set()
        self.fetched: list[str] = []
        self._fetched: dict[ToolName, dict[str, bytes]] = {}
        self._staged: dict[ToolName, dict[str, str]] = {}
        self._in_place: dict[ToolName, dict[str, str]] = {}
        self._markers: dict[ToolName, InstalledTool] = {}

    def installed(self, tool: ToolName) -> InstalledTool | None:
        """Return the marker of a tool that is in place, or None."""
        return self._markers.get(tool)

    def run(self, tool: ToolName, program: str, arguments: Sequence[str]) -> str | None:
        """Return what the program prints, or None when it is missing or refuses to run."""
        output = self._in_place.get(tool, {}).get(program)
        if output is None or program in self.refusing:
            return None
        return output.splitlines()[0]

    def fetch(self, tool: ToolName, file: ToolFile, on_progress: Progress) -> str:
        """Hand over the configured bytes of an address in two steps, or fail as configured."""
        self.fetched.append(file.url)
        if file.url in self.unreachable or file.url not in self.downloads:
            raise AppError(ErrorCode.NETWORK_UNREACHABLE, {"url": file.url})
        if self.full_disk:
            raise AppError(ErrorCode.DISK_FULL, {"reason": "No space left on device"})
        content = self.downloads[file.url]
        on_progress(0, len(content))
        on_progress(len(content) // 2, len(content))
        on_progress(len(content), len(content))
        self._fetched.setdefault(tool, {})[file.url] = content
        return hashlib.sha256(content).hexdigest()

    def unpack(self, tool: ToolName, file: ToolFile) -> None:
        """Take the programs out of a pretend archive."""
        try:
            archive = json.loads(self._fetched[tool][file.url])
            if archive["kind"] != file.kind.value:
                raise KeyError(file.kind.value)
            taken = {program: str(archive["programs"][program]) for program in file.programs}
        except (KeyError, ValueError, TypeError) as error:
            raise ValueError(
                f"The archive of {file.url} does not hold {list(file.programs)}"
            ) from error
        self._staged.setdefault(tool, {}).update(taken)

    def commit(self, tool: ToolName, installed: InstalledTool) -> None:
        """Put the staged programs in place of the tool."""
        self._in_place[tool] = self._staged.pop(tool)
        self._markers[tool] = installed
        self.clear(tool)

    def clear(self, tool: ToolName) -> None:
        """Forget what was fetched and staged for a tool."""
        self._fetched.pop(tool, None)
        self._staged.pop(tool, None)

    def lose(self, tool: ToolName, program: str) -> None:
        """Play a user who deleted a program of a tool that was in place."""
        self._in_place.get(tool, {}).pop(program, None)

    def staging_is_empty(self, tool: ToolName) -> bool:
        """Return whether nothing of an installation is left over."""
        return tool not in self._fetched and tool not in self._staged
