"""Rules about the tools the app needs (R-IN-03, R-IN-04).

Reads the tool manifest, decides when the first-run screen is shown, and
turns byte counts into progress. The manifest pins, for every tool the app
downloads, one or two sources with version, address and checksum
(docs/DECISIONS.md D-053). This module must not download, run or store
anything: the toolchain service does that through its ports. The manifest
is JSON, so its parts are handled as ``Any`` until they are checked.

Tests: backend/tests/unit/core/test_toolchain.py
"""

import json
from collections.abc import Sequence
from typing import Any, cast

from ytmirror.core.models import (
    ArchiveKind,
    ToolFile,
    ToolName,
    ToolReport,
    ToolSource,
    ToolSpec,
    ToolStatus,
)

ARCHITECTURES = ("arm64", "x86_64")
SETUP_AGAIN_FROM = 2
"""With this many tools missing at a start, the first-run screen is shown again (R-IN-03)."""

_SHA256_LENGTH = 64
_HEX_DIGITS = frozenset("0123456789abcdef")


def parse_manifest(text: str) -> tuple[ToolSpec, ...]:
    """Read the tool manifest.

    Args:
        text: The JSON text of ``toolchain_manifest.json``.

    Returns:
        One entry per downloadable tool, in the order of the manifest.

    Raises:
        ValueError: When the manifest is not what this module expects. The
            message names the place.
    """
    try:
        tools: Any = json.loads(text)["tools"]
        return tuple(_tool(str(name), entry) for name, entry in tools.items())
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError(f"The tool manifest is malformed: {error!r}") from error


def setup_required(setup_completed: bool, reports: Sequence[ToolReport]) -> bool:
    """Return whether the first-run screen must be shown at this start.

    Implements the rule of R-IN-03: the screen is shown until setup has
    completed once, and again whenever two or more tools are missing. One
    missing tool gets the banner of R-IN-04 instead.

    Args:
        setup_completed: Whether every tool was in order at some earlier time.
        reports: The state of every tool at this start.
    """
    not_usable = sum(1 for report in reports if report.status is not ToolStatus.OK)
    return not setup_completed or not_usable >= SETUP_AGAIN_FROM


def download_progress(done_bytes: int, total_bytes: int | None) -> float | None:
    """Return the share of a download that is done, from 0 to 1.

    Args:
        done_bytes: The bytes received so far, over all files of the tool.
        total_bytes: The size of all files, or None when a server did not say.

    Returns:
        The share, or None when the total is unknown.
    """
    if total_bytes is None or total_bytes <= 0:
        return None
    return min(done_bytes / total_bytes, 1.0)


def _tool(name: str, entry: Any) -> ToolSpec:
    programs = _texts(entry["programs"], f"{name}: programs")
    sources: Any = entry["sources"]
    if not isinstance(sources, list) or not sources:
        raise ValueError(f"The tool manifest is malformed: {name} has no source")
    return ToolSpec(
        name=ToolName(name),
        programs=programs,
        check=_texts(entry["check"], f"{name}: check"),
        sources=tuple(_source(name, programs, source) for source in cast(list[Any], sources)),
    )


def _source(tool: str, programs: tuple[str, ...], entry: Any) -> ToolSource:
    name = str(entry["name"])
    files = {
        architecture: tuple(_file(f"{tool} from {name}", file) for file in entry[architecture])
        for architecture in ARCHITECTURES
    }
    for architecture, parts in files.items():
        provided = sorted(program for part in parts for program in part.programs)
        if provided != sorted(programs):
            raise ValueError(
                f"The tool manifest is malformed: {tool} from {name} for {architecture} "
                f"provides {provided}, not {sorted(programs)}"
            )
    return ToolSource(name=name, version=str(entry["version"]), files=files)


def _file(place: str, entry: Any) -> ToolFile:
    url = str(entry["url"])
    sha256 = str(entry["sha256"])
    if not url.startswith(("https://", "http://127.0.0.1:")):
        raise ValueError(f"The tool manifest is malformed: {place} has the address {url!r}")
    if len(sha256) != _SHA256_LENGTH or not set(sha256) <= _HEX_DIGITS:
        raise ValueError(f"The tool manifest is malformed: {place} has no SHA-256 for {url}")
    return ToolFile(
        url=url,
        sha256=sha256,
        kind=ArchiveKind(str(entry["kind"])),
        programs=_texts(entry["programs"], f"{place}: programs"),
    )


def _texts(value: Any, place: str) -> tuple[str, ...]:
    items = cast(list[Any], value) if isinstance(value, list) else None
    if items is None or not all(isinstance(item, str) for item in items):
        raise ValueError(f"The tool manifest is malformed: {place} is not a list of texts")
    return tuple(str(item) for item in items)
