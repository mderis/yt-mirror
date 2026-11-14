"""Knows the state of the tools the app needs, and installs the missing ones.

Implements R-IN-03 and R-IN-04. The tools are the Python environment and
yt-dlp, which ``./start`` installs, and ffmpeg with ffprobe and Deno, which
the app downloads into its own folder. A downloaded tool can have a second
source: it is tried when the first one fails or its file does not match
its checksum, and whatever is installed must pass the same self-check
(docs/DECISIONS.md D-053).

This module must not know HTTP, archives or folders: it works through the
ToolBox port. It never touches the network by itself, only when asked to
install a tool.

Tests: backend/tests/unit/services/test_toolchain.py
"""

import threading
from collections.abc import Callable, Sequence

import structlog
from structlog.typing import FilteringBoundLogger

from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.models import (
    InstalledTool,
    ToolName,
    ToolReport,
    ToolSource,
    ToolSpec,
    ToolStatus,
    ToolUpdated,
)
from ytmirror.core.toolchain import download_progress, setup_required
from ytmirror.ports.app_meta_repository import AppMetaRepository
from ytmirror.ports.clock import Clock
from ytmirror.ports.system_probe import SystemProbe
from ytmirror.ports.tool_box import ToolBox
from ytmirror.services.events import EventBus

_log: FilteringBoundLogger = structlog.get_logger(__name__)

SETUP_COMPLETED_KEY = "setup_completed_at"
YTDLP_PACKAGE = "yt-dlp"
_PROGRESS_STEPS = 100
"""Progress is published when it moved by one of this many steps, not for every piece."""


class ToolchainService:
    """Reports on the tools and installs the ones the app can install."""

    def __init__(
        self,
        *,
        specs: Sequence[ToolSpec],
        tool_box: ToolBox,
        probe: SystemProbe,
        meta: AppMetaRepository,
        events: EventBus,
        clock: Clock,
        run_in_background: Callable[[Callable[[], None]], None],
        only_source: str | None = None,
    ) -> None:
        """Create the service. Nothing is checked yet: call ``verify``.

        Args:
            specs: The downloadable tools of the tool manifest.
            tool_box: Fetches, keeps and runs the downloaded tools.
            probe: Tells about Python and its packages.
            meta: Remembers that the setup completed.
            events: Where changes are published for the interface.
            clock: The source of time.
            run_in_background: Runs an installation without blocking the caller.
            only_source: The name of the one source to use, or None for all. For tests.
        """
        self._specs = {spec.name: spec for spec in specs}
        self._tool_box = tool_box
        self._probe = probe
        self._meta = meta
        self._events = events
        self._clock = clock
        self._run_in_background = run_in_background
        self._only_source = only_source
        self._lock = threading.Lock()
        self._reports: dict[ToolName, ToolReport] = {}
        self._setup_required = True

    def verify(self) -> tuple[ToolReport, ...]:
        """Check every tool and decide whether the first-run screen is needed.

        Implements R-IN-04: on every start the app verifies that the tools
        still work. Nothing is downloaded or repaired here.

        Returns:
            The state of every tool, in the order of the first-run screen.
        """
        checked = {tool: self._check(tool) for tool in ToolName}
        completed = self._meta.get(SETUP_COMPLETED_KEY) is not None
        with self._lock:
            self._reports = checked
            self._setup_required = setup_required(completed, list(checked.values()))
        for report in checked.values():
            _log.info(
                "tool.check",
                msg="Tool checked",
                tool=report.name.value,
                status=report.status.value,
                version=report.version,
                source=report.source,
            )
        self._remember_a_completed_setup()
        return self.reports()

    def reports(self) -> tuple[ToolReport, ...]:
        """Return the state of every tool as it was last seen, in display order."""
        with self._lock:
            return tuple(self._reports[tool] for tool in ToolName if tool in self._reports)

    def setup_required(self) -> bool:
        """Return whether the interface must show the first-run screen (R-IN-03)."""
        with self._lock:
            return self._setup_required

    def start_install(self, tool: ToolName) -> ToolReport:
        """Start installing a tool in the background and return its new state.

        Implements the installing half of R-IN-03 and the "Install now"
        button of R-IN-04. A tool that is being installed already is not
        started a second time.

        Args:
            tool: The tool to install.

        Returns:
            The state of the tool right after the start.

        Raises:
            AppError: ``INVALID_REQUEST`` for a tool the app cannot install by itself.
        """
        if tool not in self._specs:
            raise AppError(ErrorCode.INVALID_REQUEST, {"tool": tool.value})
        with self._lock:
            current = self._reports.get(tool)
            if current is not None and current.status is ToolStatus.INSTALLING:
                return current
            starting = ToolReport(tool, ToolStatus.INSTALLING, progress=0.0, installable=True)
            self._reports[tool] = starting
        self._events.publish(ToolUpdated(starting))
        self._run_in_background(lambda: self._install(tool))
        return starting

    def _check(self, tool: ToolName) -> ToolReport:
        if tool is ToolName.PYTHON:
            return ToolReport(tool, ToolStatus.OK, version=self._probe.python_version())
        if tool is ToolName.YTDLP:
            version = self._probe.package_version(YTDLP_PACKAGE)
            status = ToolStatus.MISSING if version is None else ToolStatus.OK
            return ToolReport(tool, status, version=version)
        installed = self._tool_box.installed(tool)
        if installed is None:
            return ToolReport(tool, ToolStatus.MISSING, installable=True)
        status = ToolStatus.OK if self._works(self._specs[tool]) else ToolStatus.BROKEN
        return ToolReport(
            tool, status, version=installed.version, source=installed.source, installable=True
        )

    def _works(self, spec: ToolSpec) -> bool:
        return all(
            self._tool_box.run(spec.name, program, spec.check) is not None
            for program in spec.programs
        )

    def _install(self, tool: ToolName) -> None:
        spec = self._specs[tool]
        sources = [
            source
            for source in spec.sources
            if self._only_source is None or source.name == self._only_source
        ]
        failure = ErrorCode.TOOL_MISSING
        for source in sources:
            started = self._clock.monotonic()
            _log.info(
                "tool.install.started",
                msg="Tool installation started",
                tool=tool.value,
                source=source.name,
                version=source.version,
            )
            try:
                self._install_from(spec, source)
            except AppError as error:
                failure = error.code
                self._tool_box.clear(tool)
                _log.warning(
                    "tool.install.failed",
                    msg="Tool installation failed",
                    tool=tool.value,
                    source=source.name,
                    error_code=error.code.value,
                    duration_ms=round((self._clock.monotonic() - started) * 1000),
                    **error.details,
                )
                continue
            _log.info(
                "tool.install.finished",
                msg="Tool installation finished",
                tool=tool.value,
                source=source.name,
                version=source.version,
                duration_ms=round((self._clock.monotonic() - started) * 1000),
            )
            self._set(self._check(tool))
            self._remember_a_completed_setup()
            return
        self._set(ToolReport(tool, ToolStatus.FAILED, error_code=failure, installable=True))

    def _install_from(self, spec: ToolSpec, source: ToolSource) -> None:
        tool = spec.name
        files = source.files.get(self._probe.cpu_architecture(), ())
        if not files:
            raise AppError(ErrorCode.TOOL_MISSING, {"reason": "no build for this processor"})
        self._tool_box.clear(tool)
        for index, file in enumerate(files):
            checksum = self._tool_box.fetch(
                tool,
                file,
                lambda done, total, at=index: self._progress(tool, at, len(files), done, total),
            )
            if checksum != file.sha256:
                raise AppError(
                    ErrorCode.CHECKSUM_MISMATCH,
                    {"url": file.url, "expected": file.sha256, "actual": checksum},
                )
            try:
                self._tool_box.unpack(tool, file)
            except ValueError as error:
                raise AppError(ErrorCode.TOOL_MISSING, {"reason": str(error)}) from error
        self._tool_box.commit(tool, InstalledTool(source=source.name, version=source.version))
        if not self._works(spec):
            raise AppError(ErrorCode.TOOL_MISSING, {"reason": "the self-check failed"})

    def _progress(
        self, tool: ToolName, file_index: int, file_count: int, done: int, total: int | None
    ) -> None:
        share = download_progress(done, total)
        overall = None if share is None else (file_index + share) / file_count
        with self._lock:
            before = self._reports[tool].progress
            if _step(before) == _step(overall) and overall != 1.0:
                return
            report = ToolReport(tool, ToolStatus.INSTALLING, progress=overall, installable=True)
            self._reports[tool] = report
        self._events.publish(ToolUpdated(report))

    def _set(self, report: ToolReport) -> None:
        with self._lock:
            self._reports[report.name] = report
        self._events.publish(ToolUpdated(report))

    def _remember_a_completed_setup(self) -> None:
        """Write down, once, that every tool was in order, and end the first-run state."""
        with self._lock:
            complete = all(
                tool in self._reports and self._reports[tool].status is ToolStatus.OK
                for tool in ToolName
            )
            if complete:
                self._setup_required = False
        if complete and self._meta.get(SETUP_COMPLETED_KEY) is None:
            self._meta.put(SETUP_COMPLETED_KEY, str(int(self._clock.now().timestamp())))


def _step(progress: float | None) -> int | None:
    return None if progress is None else int(progress * _PROGRESS_STEPS)
