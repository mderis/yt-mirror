"""The ToolBox port on this Mac: downloads with httpx2, files in ``tools/``.

Implements the technical side of R-IN-03 and R-IN-04. The layout:

    tools/<tool>/<program>        a tool that is in place
    tools/<tool>/installed.json   the source and the version it came from
    tools/.staging/<tool>/        downloads and unpacked programs of an installation

Only the named programs are taken from an archive, by name, from its top
level, so an archive cannot write anywhere else. This module must not
decide which source is used or whether a checksum is right: the toolchain
service does.

Tests: backend/tests/integration/test_tool_box_contract.py
"""

import errno
import hashlib
import json
import shutil
import subprocess
import tarfile
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import IO

import httpx2

from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.models import ArchiveKind, InstalledTool, ToolFile, ToolName
from ytmirror.ports.tool_box import Progress

_CONNECT_TIMEOUT_S = 30.0
_READ_TIMEOUT_S = 120.0
"""Between two pieces of a download. There is no limit for the whole download:
35 MB from GitHub took five minutes on the maintainer's network (D-053)."""
_RUN_TIMEOUT_S = 60
"""macOS checks a large new program the first time it runs, which can take a while."""
_CHUNK_BYTES = 256 * 1024
_EXECUTABLE = 0o755
_MARKER = "installed.json"
_STAGING = ".staging"
_OK = 200


class LocalToolBox:
    """Keeps the tools in one folder of this Mac."""

    def __init__(self, tools_dir: Path) -> None:
        """Create the tool box. Nothing is touched yet.

        Args:
            tools_dir: The ``tools/`` folder of this installation.
        """
        self._tools_dir = tools_dir

    def installed(self, tool: ToolName) -> InstalledTool | None:
        """Return what was written down when a tool was put in place, or None."""
        try:
            marker = json.loads((self._place(tool) / _MARKER).read_text(encoding="utf-8"))
            return InstalledTool(source=str(marker["source"]), version=str(marker["version"]))
        except OSError, ValueError, KeyError, TypeError:
            return None

    def run(self, tool: ToolName, program: str, arguments: Sequence[str]) -> str | None:
        """Run a program of a tool that is in place and return its first line of output."""
        try:
            result = subprocess.run(
                [str(self._place(tool) / program), *arguments],
                capture_output=True,
                text=True,
                timeout=_RUN_TIMEOUT_S,
                check=False,
            )
        except OSError, subprocess.TimeoutExpired:
            return None
        lines = (result.stdout or result.stderr).strip().splitlines()
        if result.returncode != 0 or not lines:
            return None
        return lines[0].strip()

    def fetch(self, tool: ToolName, file: ToolFile, on_progress: Progress) -> str:
        """Download a file of a tool into the staging area and return its SHA-256."""
        target = self._download(tool, file)
        digest = hashlib.sha256()
        timeout = httpx2.Timeout(_CONNECT_TIMEOUT_S, read=_READ_TIMEOUT_S)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with (
                httpx2.stream("GET", file.url, follow_redirects=True, timeout=timeout) as response,
                target.open("wb") as out,
            ):
                if response.status_code != _OK:
                    raise AppError(
                        ErrorCode.NETWORK_UNREACHABLE,
                        {"url": file.url, "status": str(response.status_code)},
                    )
                size = response.headers.get("content-length")
                total = int(size) if size and size.isdigit() else None
                done = 0
                on_progress(done, total)
                for chunk in response.iter_bytes(_CHUNK_BYTES):
                    out.write(chunk)
                    digest.update(chunk)
                    done += len(chunk)
                    on_progress(done, total)
        except httpx2.HTTPError as error:
            raise AppError(
                ErrorCode.NETWORK_UNREACHABLE, {"url": file.url, "reason": type(error).__name__}
            ) from error
        except OSError as error:
            raise _disk_error(error) from error
        return digest.hexdigest()

    def unpack(self, tool: ToolName, file: ToolFile) -> None:
        """Take the programs of a fetched file out of its archive, into the staging area."""
        archive = self._download(tool, file)
        programs_dir = self._staging(tool) / "programs"
        try:
            programs_dir.mkdir(parents=True, exist_ok=True)
            if file.kind is ArchiveKind.ZIP:
                with zipfile.ZipFile(archive) as opened:
                    for program in file.programs:
                        with opened.open(program) as member:
                            _write_program(member, programs_dir / program)
            else:
                with tarfile.open(archive, "r:xz") as opened:
                    for program in file.programs:
                        member = opened.extractfile(program)
                        if member is None:
                            raise KeyError(program)
                        with member:
                            _write_program(member, programs_dir / program)
        except (KeyError, FileNotFoundError, zipfile.BadZipFile, tarfile.TarError) as error:
            raise ValueError(
                f"The archive of {file.url} does not hold {list(file.programs)}"
            ) from error
        except OSError as error:
            raise _disk_error(error) from error

    def commit(self, tool: ToolName, installed: InstalledTool) -> None:
        """Put the unpacked programs in place of the tool and write down where they came from."""
        programs_dir = self._staging(tool) / "programs"
        marker = {"source": installed.source, "version": installed.version}
        (programs_dir / _MARKER).write_text(json.dumps(marker), encoding="utf-8")
        place = self._place(tool)
        shutil.rmtree(place, ignore_errors=True)
        programs_dir.rename(place)
        self.clear(tool)

    def clear(self, tool: ToolName) -> None:
        """Empty the staging area of a tool. A tool that is in place stays."""
        shutil.rmtree(self._staging(tool), ignore_errors=True)

    def _place(self, tool: ToolName) -> Path:
        return self._tools_dir / tool.value

    def _staging(self, tool: ToolName) -> Path:
        return self._tools_dir / _STAGING / tool.value

    def _download(self, tool: ToolName, file: ToolFile) -> Path:
        return self._staging(tool) / "downloads" / hashlib.sha256(file.url.encode()).hexdigest()


def _write_program(member: IO[bytes], target: Path) -> None:
    with target.open("wb") as out:
        shutil.copyfileobj(member, out)
    target.chmod(_EXECUTABLE)


def _disk_error(error: OSError) -> AppError:
    code = ErrorCode.DISK_FULL if error.errno == errno.ENOSPC else ErrorCode.INTERNAL
    return AppError(code, {"reason": error.strerror or type(error).__name__})
