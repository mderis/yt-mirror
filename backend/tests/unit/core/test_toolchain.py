"""Tests of ``ytmirror.core.toolchain``."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from ytmirror.core.models import ArchiveKind, ToolName, ToolReport, ToolStatus
from ytmirror.core.toolchain import download_progress, parse_manifest, setup_required

MANIFEST_FILE = (
    Path(__file__).resolve().parents[3] / "ytmirror" / "services" / "toolchain_manifest.json"
)
SHA = "ab" * 32


def small_manifest() -> dict[str, Any]:
    """Return a manifest with one tool that has two sources."""

    def file(name: str, programs: list[str]) -> dict[str, object]:
        return {
            "url": f"https://example.org/{name}",
            "sha256": SHA,
            "kind": "zip",
            "programs": programs,
        }

    return {
        "tools": {
            "ffmpeg": {
                "programs": ["ffmpeg", "ffprobe"],
                "check": ["-version"],
                "sources": [
                    {
                        "name": "first",
                        "version": "9.0.2",
                        "arm64": [
                            file("a-ffmpeg.zip", ["ffmpeg"]),
                            file("a-ffprobe.zip", ["ffprobe"]),
                        ],
                        "x86_64": [file("x-both.zip", ["ffmpeg", "ffprobe"])],
                    },
                    {
                        "name": "second",
                        "version": "8.1.3-2",
                        "arm64": [file("a2.zip", ["ffprobe", "ffmpeg"])],
                        "x86_64": [file("x2.zip", ["ffmpeg", "ffprobe"])],
                    },
                ],
            }
        }
    }


def reports(*statuses: ToolStatus) -> list[ToolReport]:
    """Return one report per status, for the tools in their usual order."""
    return [ToolReport(name, status) for name, status in zip(ToolName, statuses, strict=False)]


def test_a_tool_has_its_sources_in_the_order_they_are_tried() -> None:
    """R-IN-03: a downloaded tool can have a second source, tried after the first."""
    (tool,) = parse_manifest(json.dumps(small_manifest()))

    assert tool.name is ToolName.FFMPEG
    assert tool.programs == ("ffmpeg", "ffprobe")
    assert tool.check == ("-version",)
    assert [(source.name, source.version) for source in tool.sources] == [
        ("first", "9.0.2"),
        ("second", "8.1.3-2"),
    ]


def test_each_source_pins_its_own_files_per_processor() -> None:
    """R-IN-03: each source has its own pinned version, address and checksum."""
    (tool,) = parse_manifest(json.dumps(small_manifest()))
    first = tool.sources[0]

    assert [file.url for file in first.files["arm64"]] == [
        "https://example.org/a-ffmpeg.zip",
        "https://example.org/a-ffprobe.zip",
    ]
    assert first.files["arm64"][0].programs == ("ffmpeg",)
    assert first.files["x86_64"][0].programs == ("ffmpeg", "ffprobe")
    assert first.files["x86_64"][0].sha256 == SHA
    assert first.files["x86_64"][0].kind is ArchiveKind.ZIP


def break_it(change: str) -> dict[str, Any]:
    """Return the small manifest with one thing wrong."""
    manifest = copy.deepcopy(small_manifest())
    tool = manifest["tools"]["ffmpeg"]
    file = tool["sources"][0]["arm64"][0]
    if change == "no checksum":
        file["sha256"] = ""
    elif change == "checksum that is no checksum":
        file["sha256"] = "z" * 64
    elif change == "address that is not https":
        file["url"] = "ftp://example.org/ffmpeg.zip"
    elif change == "unknown archive format":
        file["kind"] = "rar"
    elif change == "a program is missing":
        tool["sources"][0]["arm64"].pop()
    elif change == "no sources":
        tool["sources"] = []
    elif change == "no processor":
        del tool["sources"][1]["x86_64"]
    elif change == "programs are not texts":
        tool["programs"] = ["ffmpeg", 3]
    elif change == "unknown tool":
        manifest["tools"]["winamp"] = manifest["tools"].pop("ffmpeg")
    else:
        del manifest["tools"]
    return manifest


@pytest.mark.parametrize(
    "change",
    [
        "no checksum",
        "checksum that is no checksum",
        "address that is not https",
        "unknown archive format",
        "a program is missing",
        "no sources",
        "no processor",
        "programs are not texts",
        "unknown tool",
        "no tools",
    ],
)
def test_a_manifest_with_something_wrong_is_refused(change: str) -> None:
    """R-IN-03: nothing is downloaded from a manifest without a pinned address and checksum."""
    with pytest.raises(ValueError, match=r"malformed|is not a valid"):
        parse_manifest(json.dumps(break_it(change)))


def test_a_test_manifest_may_point_at_a_server_on_this_mac() -> None:
    """infra: the end-to-end tests serve small stand-ins for the tools from 127.0.0.1."""
    manifest = small_manifest()
    manifest["tools"]["ffmpeg"]["sources"][0]["arm64"][0]["url"] = "http://127.0.0.1:5175/f.zip"

    (tool,) = parse_manifest(json.dumps(manifest))

    assert tool.sources[0].files["arm64"][0].url == "http://127.0.0.1:5175/f.zip"


def test_the_manifest_of_the_app_pins_ffmpeg_with_two_sources_and_deno() -> None:
    """R-IN-03: ffmpeg and Deno are downloaded from pinned addresses with checksums (D-053)."""
    tools = {tool.name: tool for tool in parse_manifest(MANIFEST_FILE.read_text(encoding="utf-8"))}

    assert list(tools) == [ToolName.FFMPEG, ToolName.DENO]
    assert [source.name for source in tools[ToolName.FFMPEG].sources] == [
        "martin-riedl",
        "jellyfin-ffmpeg",
    ]
    assert tools[ToolName.FFMPEG].programs == ("ffmpeg", "ffprobe")
    assert [source.name for source in tools[ToolName.DENO].sources] == ["deno"]
    every_file = [
        file
        for tool in tools.values()
        for source in tool.sources
        for files in source.files.values()
        for file in files
    ]
    assert len(every_file) == 8
    assert all(file.url.startswith("https://") for file in every_file)
    assert len({file.sha256 for file in every_file}) == len(every_file)
    assert all(
        source.version in file.url
        for tool in tools.values()
        for source in tool.sources
        for files in source.files.values()
        for file in files
    )


def test_the_first_run_screen_is_shown_until_setup_completed_once() -> None:
    """R-IN-03: on first start the app shows which tools it needs."""
    all_ok = reports(ToolStatus.OK, ToolStatus.OK, ToolStatus.OK, ToolStatus.OK)

    assert setup_required(False, all_ok) is True
    assert setup_required(True, all_ok) is False


def test_one_missing_tool_later_gets_the_banner_not_the_first_run_screen() -> None:
    """R-IN-04: a missing or broken tool produces a banner with an "Install now" button."""
    one_missing = reports(ToolStatus.OK, ToolStatus.OK, ToolStatus.MISSING, ToolStatus.OK)
    one_broken = reports(ToolStatus.OK, ToolStatus.OK, ToolStatus.OK, ToolStatus.BROKEN)

    assert setup_required(True, one_missing) is False
    assert setup_required(True, one_broken) is False


def test_two_missing_tools_bring_the_first_run_screen_back() -> None:
    """R-IN-03: the first-run screen is shown again when two or more tools are missing."""
    two = reports(ToolStatus.OK, ToolStatus.OK, ToolStatus.MISSING, ToolStatus.BROKEN)
    three = reports(ToolStatus.OK, ToolStatus.FAILED, ToolStatus.MISSING, ToolStatus.MISSING)

    assert setup_required(True, two) is True
    assert setup_required(True, three) is True


@pytest.mark.parametrize(
    ("done", "total", "share"),
    [
        (0, 100, 0.0),
        (64, 100, 0.64),
        (100, 100, 1.0),
        (120, 100, 1.0),
        (5, None, None),
        (5, 0, None),
    ],
)
def test_progress_is_the_share_of_the_bytes_received(
    done: int, total: int | None, share: float | None
) -> None:
    """R-IN-03: a download shows its progress, and none when the size is unknown."""
    assert download_progress(done, total) == share
