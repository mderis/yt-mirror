"""Contract of the ToolBox port, run against the fake and the real adapter.

The real adapter downloads from a small web server on this Mac and unpacks
real archives of tiny shell scripts, so no test touches the network.
"""

import functools
import hashlib
import http.server
import io
import tarfile
import threading
import zipfile
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.fixtures.fakes.tool_box import FakeToolBox, fake_archive
from ytmirror.adapters.tool_box import LocalToolBox
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.models import ArchiveKind, InstalledTool, ToolFile, ToolName
from ytmirror.ports.tool_box import ToolBox

FFMPEG = ToolName.FFMPEG
RIEDL = InstalledTool(source="martin-riedl", version="9.0.2")


@dataclass
class World:
    """A tool box, and the two things a test does to its surroundings."""

    box: ToolBox
    offer: Callable[[str, ArchiveKind, Mapping[str, str]], ToolFile]
    """Put an archive at an address: its name, its format, and what each program prints."""
    stop_running: Callable[[ToolName, str], None]
    """Make a program that is in place end with an error."""


def _script(output: str) -> bytes:
    return f"#!/bin/sh\necho '{output}'\n".encode()


def real_archive(kind: ArchiveKind, programs: Mapping[str, str]) -> bytes:
    """Return a real archive of shell scripts that print the given lines."""
    buffer = io.BytesIO()
    if kind is ArchiveKind.ZIP:
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, output in programs.items():
                archive.writestr(name, _script(output))
    else:
        with tarfile.open(fileobj=buffer, mode="w:xz") as archive:
            for name, output in programs.items():
                member = tarfile.TarInfo(name)
                member.size = len(_script(output))
                archive.addfile(member, io.BytesIO(_script(output)))
    return buffer.getvalue()


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        """Keep the test output clean."""


@pytest.fixture
def web_folder(tmp_path: Path) -> Iterator[tuple[Path, str]]:
    """A folder that is served on 127.0.0.1, and the address it is served at."""
    folder = tmp_path / "web"
    folder.mkdir()
    handler = functools.partial(_QuietHandler, directory=str(folder))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, args=(0.01,), daemon=True)
    thread.start()
    yield folder, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture(params=["fake", "local"])
def world(request: pytest.FixtureRequest, tmp_path: Path, web_folder: tuple[Path, str]) -> World:
    """The fake and the real tool box, each with a way to offer downloads."""
    folder, base = web_folder
    if request.param == "fake":
        fake = FakeToolBox()

        def offer_fake(name: str, kind: ArchiveKind, programs: Mapping[str, str]) -> ToolFile:
            content = fake_archive(kind, programs)
            fake.downloads[f"{base}/{name}"] = content
            return ToolFile(
                f"{base}/{name}", hashlib.sha256(content).hexdigest(), kind, tuple(programs)
            )

        return World(fake, offer_fake, lambda _tool, program: fake.refusing.add(program))

    tools_dir = tmp_path / "tools"

    def offer_real(name: str, kind: ArchiveKind, programs: Mapping[str, str]) -> ToolFile:
        content = real_archive(kind, programs)
        (folder / name).write_bytes(content)
        return ToolFile(
            f"{base}/{name}", hashlib.sha256(content).hexdigest(), kind, tuple(programs)
        )

    def stop_running(tool: ToolName, program: str) -> None:
        (tools_dir / tool.value / program).write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")

    return World(LocalToolBox(tools_dir), offer_real, stop_running)


def install(world: World, *files: ToolFile, marker: InstalledTool = RIEDL) -> None:
    """Fetch, unpack and put in place the given files as ffmpeg."""
    for file in files:
        world.box.fetch(FFMPEG, file, lambda _done, _total: None)
        world.box.unpack(FFMPEG, file)
    world.box.commit(FFMPEG, marker)


def test_a_tool_that_was_never_installed_is_not_there(world: World) -> None:
    """R-IN-04: a missing tool is seen as missing, not as an error."""
    assert world.box.installed(FFMPEG) is None
    assert world.box.run(FFMPEG, "ffmpeg", ["-version"]) is None


def test_a_download_reports_its_progress_and_its_checksum(world: World) -> None:
    """R-IN-03: tools are downloaded with visible progress, and their checksum is known."""
    file = world.offer("ffmpeg.zip", ArchiveKind.ZIP, {"ffmpeg": "ffmpeg version 9.0.2"})
    steps: list[tuple[int, int | None]] = []

    checksum = world.box.fetch(FFMPEG, file, lambda done, total: steps.append((done, total)))

    assert checksum == file.sha256
    total = steps[-1][1]
    assert total is not None and total > 0
    assert steps[0] == (0, total)
    assert steps[-1] == (total, total)
    assert [done for done, _total in steps] == sorted(done for done, _total in steps)


def test_a_fetched_tool_is_not_in_place_before_it_is_committed(world: World) -> None:
    """R-IN-03: a half-installed tool never counts as installed."""
    file = world.offer("ffmpeg.zip", ArchiveKind.ZIP, {"ffmpeg": "ffmpeg version 9.0.2"})

    world.box.fetch(FFMPEG, file, lambda _done, _total: None)
    world.box.unpack(FFMPEG, file)

    assert world.box.installed(FFMPEG) is None
    assert world.box.run(FFMPEG, "ffmpeg", ["-version"]) is None


def test_a_committed_tool_runs_and_remembers_where_it_came_from(world: World) -> None:
    """R-IN-03, R-IN-04: an installed tool works and names its source and version."""
    install(
        world,
        world.offer("ffmpeg.zip", ArchiveKind.ZIP, {"ffmpeg": "ffmpeg version 9.0.2 Copyright"}),
        world.offer("ffprobe.zip", ArchiveKind.ZIP, {"ffprobe": "ffprobe version 9.0.2"}),
    )

    assert world.box.installed(FFMPEG) == RIEDL
    assert world.box.run(FFMPEG, "ffmpeg", ["-version"]) == "ffmpeg version 9.0.2 Copyright"
    assert world.box.run(FFMPEG, "ffprobe", ["-version"]) == "ffprobe version 9.0.2"


def test_an_archive_of_the_other_format_holds_both_programs(world: World) -> None:
    """R-IN-03: the second source ships one compressed tar archive with both programs."""
    both = {"ffmpeg": "ffmpeg version 8.1.3-Jellyfin", "ffprobe": "ffprobe version 8.1.3-Jellyfin"}

    install(
        world,
        world.offer("portable.tar.xz", ArchiveKind.TAR_XZ, both),
        marker=InstalledTool("jellyfin-ffmpeg", "8.1.3-2"),
    )

    assert world.box.installed(FFMPEG) == InstalledTool("jellyfin-ffmpeg", "8.1.3-2")
    assert world.box.run(FFMPEG, "ffprobe", ["-version"]) == "ffprobe version 8.1.3-Jellyfin"


def test_a_new_installation_replaces_the_old_tool_completely(world: World) -> None:
    """R-IN-03: installing again leaves nothing of the earlier tool behind."""
    install(world, world.offer("old.zip", ArchiveKind.ZIP, {"ffmpeg": "old", "ffprobe": "old"}))

    install(
        world,
        world.offer("new.zip", ArchiveKind.ZIP, {"ffmpeg": "new"}),
        marker=InstalledTool("jellyfin-ffmpeg", "8.1.3-2"),
    )

    assert world.box.run(FFMPEG, "ffmpeg", []) == "new"
    assert world.box.run(FFMPEG, "ffprobe", []) is None
    assert world.box.installed(FFMPEG) == InstalledTool("jellyfin-ffmpeg", "8.1.3-2")


def test_clearing_drops_an_unfinished_installation_and_keeps_the_tool(world: World) -> None:
    """R-IN-03: a failed step can be retried without harm to a tool that works."""
    install(world, world.offer("good.zip", ArchiveKind.ZIP, {"ffmpeg": "good"}))
    unfinished = world.offer("next.zip", ArchiveKind.ZIP, {"ffmpeg": "next"})
    world.box.fetch(FFMPEG, unfinished, lambda _done, _total: None)
    world.box.unpack(FFMPEG, unfinished)

    world.box.clear(FFMPEG)

    assert world.box.run(FFMPEG, "ffmpeg", []) == "good"
    assert world.box.installed(FFMPEG) == RIEDL
    with pytest.raises(ValueError, match="does not hold"):
        world.box.unpack(FFMPEG, unfinished)


def test_an_address_that_does_not_answer_is_a_network_failure(world: World) -> None:
    """R-IN-03: a failed download is reported with its error code, not as a crash."""
    missing = ToolFile(
        world.offer("there.zip", ArchiveKind.ZIP, {"ffmpeg": "x"}).url.replace("there", "gone"),
        "0" * 64,
        ArchiveKind.ZIP,
        ("ffmpeg",),
    )

    with pytest.raises(AppError) as failure:
        world.box.fetch(FFMPEG, missing, lambda _done, _total: None)

    assert failure.value.code is ErrorCode.NETWORK_UNREACHABLE
    assert failure.value.details["url"] == missing.url


def test_an_archive_without_the_promised_program_is_refused(world: World) -> None:
    """R-IN-03: what is unpacked is exactly what the manifest names."""
    offered = world.offer("ffmpeg.zip", ArchiveKind.ZIP, {"ffmpeg": "ffmpeg version 9.0.2"})
    wrong = ToolFile(offered.url, offered.sha256, ArchiveKind.ZIP, ("ffprobe",))
    world.box.fetch(FFMPEG, wrong, lambda _done, _total: None)

    with pytest.raises(ValueError, match="does not hold"):
        world.box.unpack(FFMPEG, wrong)


def test_an_archive_in_another_format_than_stated_is_refused(world: World) -> None:
    """R-IN-03: a file that is not the stated kind of archive is not unpacked."""
    offered = world.offer("ffmpeg.zip", ArchiveKind.ZIP, {"ffmpeg": "ffmpeg version 9.0.2"})
    wrong = ToolFile(offered.url, offered.sha256, ArchiveKind.TAR_XZ, ("ffmpeg",))
    world.box.fetch(FFMPEG, wrong, lambda _done, _total: None)

    with pytest.raises(ValueError, match="does not hold"):
        world.box.unpack(FFMPEG, wrong)


def test_a_program_that_ends_with_an_error_does_not_count_as_working(world: World) -> None:
    """R-IN-04: on every start the app verifies the tools still work."""
    install(world, world.offer("ffmpeg.zip", ArchiveKind.ZIP, {"ffmpeg": "ffmpeg version 9.0.2"}))

    world.stop_running(FFMPEG, "ffmpeg")

    assert world.box.run(FFMPEG, "ffmpeg", ["-version"]) is None
    assert world.box.installed(FFMPEG) == RIEDL


def test_tools_live_in_the_app_folder_and_only_named_programs_are_unpacked(
    tmp_path: Path, web_folder: tuple[Path, str]
) -> None:
    """R-IN-03: tools go into the app folder, and nothing else comes out of an archive."""
    folder, base = web_folder
    content = real_archive(ArchiveKind.ZIP, {"ffmpeg": "ok", "../escape": "no", "README": "no"})
    (folder / "ffmpeg.zip").write_bytes(content)
    file = ToolFile(
        f"{base}/ffmpeg.zip", hashlib.sha256(content).hexdigest(), ArchiveKind.ZIP, ("ffmpeg",)
    )
    box = LocalToolBox(tmp_path / "tools")

    box.fetch(FFMPEG, file, lambda _done, _total: None)
    box.unpack(FFMPEG, file)
    box.commit(FFMPEG, RIEDL)

    in_place = sorted(path.name for path in (tmp_path / "tools" / "ffmpeg").iterdir())
    assert in_place == ["ffmpeg", "installed.json"]
    assert (tmp_path / "tools" / "ffmpeg" / "ffmpeg").stat().st_mode & 0o111
    assert not (tmp_path / "tools" / ".staging" / "ffmpeg").exists()
    assert not (tmp_path / "escape").exists()


def test_a_server_that_cannot_be_reached_is_a_network_failure(tmp_path: Path) -> None:
    """R-IN-03: without a connection the download fails with ``NETWORK_UNREACHABLE``."""
    file = ToolFile("http://127.0.0.1:9/ffmpeg.zip", "0" * 64, ArchiveKind.ZIP, ("ffmpeg",))

    with pytest.raises(AppError) as failure:
        LocalToolBox(tmp_path / "tools").fetch(FFMPEG, file, lambda _done, _total: None)

    assert failure.value.code is ErrorCode.NETWORK_UNREACHABLE
    assert failure.value.details["reason"] == "ConnectError"


@pytest.mark.parametrize("content", ["", "not json", '{"source": "x"}', "[1]"])
def test_a_damaged_note_about_an_installed_tool_counts_as_no_note(
    tmp_path: Path, content: str
) -> None:
    """R-IN-04: a tool whose record is damaged is treated as missing, never as a crash."""
    place = tmp_path / "tools" / "ffmpeg"
    place.mkdir(parents=True)
    (place / "installed.json").write_text(content, encoding="utf-8")

    assert LocalToolBox(tmp_path / "tools").installed(FFMPEG) is None


def test_a_folder_that_cannot_be_written_is_reported_with_a_code(
    tmp_path: Path, web_folder: tuple[Path, str]
) -> None:
    """R-IN-03: a download that cannot be stored fails with a code, not with a crash."""
    folder, base = web_folder
    content = real_archive(ArchiveKind.ZIP, {"ffmpeg": "ok"})
    (folder / "ffmpeg.zip").write_bytes(content)
    file = ToolFile(f"{base}/ffmpeg.zip", "0" * 64, ArchiveKind.ZIP, ("ffmpeg",))
    blocked = tmp_path / "tools"
    blocked.write_text("a file where the folder should be", encoding="utf-8")

    with pytest.raises(AppError) as failure:
        LocalToolBox(blocked).fetch(FFMPEG, file, lambda _done, _total: None)

    assert failure.value.code is ErrorCode.INTERNAL
