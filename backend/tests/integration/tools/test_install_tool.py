"""Tests of ``python -m ytmirror.tools.install_tool``."""

from pathlib import Path

from tests.fixtures.builders import healthy_probe, standard_specs, tool_box_with
from tests.fixtures.fakes.tool_box import FakeToolBox
from ytmirror.core.models import InstalledTool, ToolName
from ytmirror.tools.install_tool import install, main


def test_a_tool_is_installed_from_the_chosen_source(tmp_path: Path) -> None:
    """infra: CI installs the ffmpeg of each source with the app's own installation code."""
    box = tool_box_with(installed=())

    done = install(
        ToolName.FFMPEG,
        tmp_path,
        "jellyfin-ffmpeg",
        specs=standard_specs(),
        tool_box=lambda _folder: box,
        probe=healthy_probe(),
    )

    assert done is True
    assert box.installed(ToolName.FFMPEG) == InstalledTool("jellyfin-ffmpeg", "8.1.3-2")


def test_an_unknown_source_installs_nothing(tmp_path: Path) -> None:
    """infra: a source name that the manifest does not have fails instead of falling back."""
    box = FakeToolBox()

    done = install(
        ToolName.FFMPEG,
        tmp_path,
        "no-such-source",
        specs=standard_specs(),
        tool_box=lambda _folder: box,
        probe=healthy_probe(),
    )

    assert done is False
    assert box.installed(ToolName.FFMPEG) is None


def test_the_command_line_says_when_it_failed(tmp_path: Path) -> None:
    """infra: the program ends with 1 when the tool is not in order, so CI stops."""
    assert main(["ffmpeg", str(tmp_path / "tools"), "--source", "no-such-source"]) == 1
    assert not (tmp_path / "tools" / "ffmpeg").exists()
