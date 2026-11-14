"""Builders for test data and for services wired with fakes (CODING-STANDARDS section 5)."""

import hashlib
from collections.abc import Callable, Iterable, Sequence

from tests.fixtures.fakes.app_meta_repository import InMemoryAppMetaRepository
from tests.fixtures.fakes.clock import FakeClock
from tests.fixtures.fakes.system_probe import FakeSystemProbe
from tests.fixtures.fakes.tool_box import FakeToolBox, fake_archive
from ytmirror.core.models import (
    ArchiveKind,
    InstalledTool,
    ToolFile,
    ToolName,
    ToolSource,
    ToolSpec,
)
from ytmirror.ports.system_probe import SystemProbe
from ytmirror.services.events import EventBus
from ytmirror.services.toolchain import ToolchainService

YTDLP_VERSION = "2026.10.26"
FFMPEG_URL = "https://first.example/ffmpeg.zip"
FFMPEG_FALLBACK_URL = "https://second.example/ffmpeg.tar.xz"
DENO_URL = "https://deno.example/deno.zip"
_FFMPEG = fake_archive(
    ArchiveKind.ZIP, {"ffmpeg": "ffmpeg version 9.0.2", "ffprobe": "ffprobe version 9.0.2"}
)
_FFMPEG_FALLBACK = fake_archive(
    ArchiveKind.TAR_XZ, {"ffmpeg": "ffmpeg version 8.1.3", "ffprobe": "ffprobe version 8.1.3"}
)
_DENO = fake_archive(ArchiveKind.ZIP, {"deno": "deno 2.9.8"})


def _file(url: str, content: bytes, kind: ArchiveKind, programs: tuple[str, ...]) -> ToolFile:
    return ToolFile(url, hashlib.sha256(content).hexdigest(), kind, programs)


def standard_specs() -> tuple[ToolSpec, ...]:
    """Return a manifest shaped like the real one: ffmpeg from two sources, Deno from one."""
    both = ("ffmpeg", "ffprobe")
    first = (_file(FFMPEG_URL, _FFMPEG, ArchiveKind.ZIP, both),)
    second = (_file(FFMPEG_FALLBACK_URL, _FFMPEG_FALLBACK, ArchiveKind.TAR_XZ, both),)
    deno = (_file(DENO_URL, _DENO, ArchiveKind.ZIP, ("deno",)),)
    return (
        ToolSpec(
            ToolName.FFMPEG,
            both,
            ("-version",),
            (
                ToolSource("martin-riedl", "9.0.2", {"arm64": first, "x86_64": first}),
                ToolSource("jellyfin-ffmpeg", "8.1.3-2", {"arm64": second, "x86_64": second}),
            ),
        ),
        ToolSpec(
            ToolName.DENO,
            ("deno",),
            ("--version",),
            (ToolSource("deno", "2.9.8", {"arm64": deno, "x86_64": deno}),),
        ),
    )


def tool_box_with(installed: Iterable[ToolName] = (ToolName.FFMPEG, ToolName.DENO)) -> FakeToolBox:
    """Return a tool box that offers every download of ``standard_specs``.

    Args:
        installed: The tools that are in place already, from their first source.
    """
    box = FakeToolBox()
    box.downloads.update(
        {FFMPEG_URL: _FFMPEG, FFMPEG_FALLBACK_URL: _FFMPEG_FALLBACK, DENO_URL: _DENO}
    )
    wanted = set(installed)
    for spec in standard_specs():
        if spec.name in wanted:
            source = spec.sources[0]
            for file in source.files["arm64"]:
                box.fetch(spec.name, file, lambda _done, _total: None)
                box.unpack(spec.name, file)
            box.commit(spec.name, InstalledTool(source.name, source.version))
    box.fetched.clear()
    return box


def healthy_probe(**changes: object) -> FakeSystemProbe:
    """Return a Mac with yt-dlp installed, with changes."""
    values: dict[str, object] = {"packages": {"yt-dlp": YTDLP_VERSION}}
    values.update(changes)
    return FakeSystemProbe(**values)  # pyright: ignore[reportArgumentType]  (test helper with loose types)


def make_toolchain(
    *,
    specs: Sequence[ToolSpec] | None = None,
    tool_box: FakeToolBox | None = None,
    probe: SystemProbe | None = None,
    meta: InMemoryAppMetaRepository | None = None,
    events: EventBus | None = None,
    clock: FakeClock | None = None,
    run_in_background: Callable[[Callable[[], None]], None] | None = None,
) -> ToolchainService:
    """Return a toolchain service over fakes, on a Mac where every tool is in place.

    By default background work runs at once, inside the call that starts it.
    """

    def at_once(work: Callable[[], None]) -> None:
        work()

    return ToolchainService(
        specs=standard_specs() if specs is None else specs,
        tool_box=tool_box if tool_box is not None else tool_box_with(),
        probe=probe if probe is not None else healthy_probe(),
        meta=meta if meta is not None else InMemoryAppMetaRepository(),
        events=events if events is not None else EventBus(),
        clock=clock if clock is not None else FakeClock(),
        run_in_background=run_in_background or at_once,
    )
