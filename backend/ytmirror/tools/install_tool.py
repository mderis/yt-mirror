"""Installs one downloaded tool into a folder, the way the app does.

CI uses it to put the ffmpeg of each source (D-053) into a folder of its own
for the media tests, with the pinned version, address and checksum of the
tool manifest, and the self-check of the app. It never touches the tools of
the app folder unless that folder is given (TESTING rule 9).

Run: python -m ytmirror.tools.install_tool <tool> <folder> [--source <name>]

Tests: backend/tests/integration/tools/test_install_tool.py
"""

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from ytmirror.adapters.system_clock import SystemClock
from ytmirror.adapters.system_probe import MacSystemProbe
from ytmirror.adapters.tool_box import LocalToolBox
from ytmirror.app.config import DEFAULT_TOOL_MANIFEST
from ytmirror.core.models import ToolName, ToolSpec, ToolStatus
from ytmirror.core.toolchain import parse_manifest
from ytmirror.ports.system_probe import SystemProbe
from ytmirror.ports.tool_box import ToolBox
from ytmirror.services.events import EventBus
from ytmirror.services.toolchain import ToolchainService


class _NothingRemembered:
    """App facts that are not kept: this program has no database."""

    def get(self, key: str) -> str | None:
        """Know nothing."""
        return None

    def put(self, key: str, value: str) -> None:
        """Keep nothing."""


def install(
    tool: ToolName,
    folder: Path,
    source: str | None = None,
    *,
    specs: Sequence[ToolSpec] | None = None,
    tool_box: Callable[[Path], ToolBox] = LocalToolBox,
    probe: SystemProbe | None = None,
) -> bool:
    """Install a tool into a folder and return whether it is in order afterwards.

    Args:
        tool: The tool.
        folder: The tools folder to install into.
        source: The one source to use, or None to try them in order.
        specs: The tools of the manifest. Default: the tool manifest of the app.
        tool_box: Makes the tool box of a folder. For tests.
        probe: Tells about this Mac. For tests.
    """
    service = ToolchainService(
        specs=specs
        if specs is not None
        else parse_manifest(DEFAULT_TOOL_MANIFEST.read_text(encoding="utf-8")),
        tool_box=tool_box(folder),
        probe=probe if probe is not None else MacSystemProbe(),
        meta=_NothingRemembered(),
        events=EventBus(),
        clock=SystemClock(),
        run_in_background=lambda work: work(),
        only_source=source,
    )
    service.start_install(tool)
    report = next(report for report in service.reports() if report.name is tool)
    return report.status is ToolStatus.OK


def main(arguments: Sequence[str] | None = None) -> int:
    """Install the tool named on the command line.

    Args:
        arguments: The command line, without the program name.

    Returns:
        0 when the tool is in order, 1 otherwise.
    """
    parser = argparse.ArgumentParser(description="Install one downloaded tool into a folder.")
    parser.add_argument("tool", choices=[ToolName.FFMPEG.value, ToolName.DENO.value])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--source", default=None)
    chosen = parser.parse_args(arguments)
    if install(ToolName(chosen.tool), chosen.folder, chosen.source):
        print(f"{chosen.tool} is in order in {chosen.folder}")  # noqa: T201
        return 0
    print(f"{chosen.tool} could not be installed into {chosen.folder}", file=sys.stderr)  # noqa: T201
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
