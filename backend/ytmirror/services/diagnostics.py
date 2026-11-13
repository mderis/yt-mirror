"""Health of the app and the environment report of ``./start --doctor``.

The full health check with fix buttons (R-LG-05) and the debug report
(R-LG-04) arrive in milestone M7, the tool checks in M1. This module must
only read: a check never repairs anything.

Tests: backend/tests/unit/services/test_diagnostics.py
"""

from ytmirror.core.models import (
    MINIMUM_MACOS_MAJOR,
    AppInfo,
    CheckResult,
    Health,
    InstallKind,
)
from ytmirror.ports.database_schema import DatabaseSchema
from ytmirror.ports.system_probe import SystemProbe

_SUPPORTED_ARCHITECTURES = ("arm64", "x86_64")
_BYTES_PER_GB = 1024**3


class DiagnosticsService:
    """Reports whether the app and its environment are in working order."""

    def __init__(self, info: AppInfo, schema: DatabaseSchema, probe: SystemProbe) -> None:
        """Create the service.

        Args:
            info: Facts about this installation.
            schema: The database schema port.
            probe: Read-only access to facts about the Mac.
        """
        self._info = info
        self._schema = schema
        self._probe = probe

    def health(self) -> Health:
        """Return the app version and the database schema version."""
        return Health(
            version=self._info.version,
            schema_version=self._schema.current_version(),
        )

    def environment_report(self) -> list[CheckResult]:
        """Check the environment the app needs and return one result per item.

        Returns:
            The results, in the order they should be shown.
        """
        checks = [
            self._check_macos(),
            self._check_processor(),
            self._check_python(),
            self._check_uv(),
        ]
        if self._info.install_kind is InstallKind.CLONE:
            checks.append(self._check_node())
        checks += [
            self._check_frontend(),
            self._check_window_library(),
            self._check_data_folder(),
            self._check_free_space(),
            self._check_database(),
        ]
        return checks

    def _check_macos(self) -> CheckResult:
        version = self._probe.os_version()
        major_text = version.split(".", maxsplit=1)[0]
        ok = major_text.isdigit() and int(major_text) >= MINIMUM_MACOS_MAJOR
        fix = None if ok else f"yt-mirror needs macOS {MINIMUM_MACOS_MAJOR} or newer."
        return CheckResult("macOS", ok, version or "unknown", fix)

    def _check_processor(self) -> CheckResult:
        architecture = self._probe.cpu_architecture()
        ok = architecture in _SUPPORTED_ARCHITECTURES
        fix = None if ok else "yt-mirror needs a Mac with Apple Silicon or an Intel processor."
        return CheckResult("Processor", ok, architecture, fix)

    def _check_python(self) -> CheckResult:
        return CheckResult("Python", True, self._probe.python_version())

    def _check_uv(self) -> CheckResult:
        version = self._probe.command_version(str(self._info.uv_executable))
        if version is None:
            return CheckResult("uv", False, "not found", "Run ./start again. It downloads uv.")
        return CheckResult("uv", True, version)

    def _check_node(self) -> CheckResult:
        version = self._probe.command_version("node")
        if version is None:
            return CheckResult(
                "Node.js",
                False,
                "not found",
                "Install Node.js from https://nodejs.org. A clone needs it to build the interface.",
            )
        return CheckResult("Node.js", True, version)

    def _check_frontend(self) -> CheckResult:
        index = self._info.frontend_dir / "index.html"
        if self._probe.file_exists(index):
            return CheckResult("Interface", True, f"built in {self._info.frontend_dir}")
        return CheckResult(
            "Interface", False, "not built yet", "Run ./start. It builds the interface."
        )

    def _check_window_library(self) -> CheckResult:
        if self._probe.module_available("webview"):
            return CheckResult("App window", True, "pywebview is installed")
        return CheckResult(
            "App window",
            False,
            "pywebview is missing",
            "Run ./start again. It repairs the Python environment.",
        )

    def _check_data_folder(self) -> CheckResult:
        folder = self._info.data_dir
        if self._probe.can_write_to(folder):
            return CheckResult("Data folder", True, str(folder))
        return CheckResult(
            "Data folder",
            False,
            f"{folder} is not writable",
            "Allow yt-mirror to write to its own folder, or move the folder to a place you own.",
        )

    def _check_free_space(self) -> CheckResult:
        free_gb = self._probe.free_bytes(self._info.data_dir) / _BYTES_PER_GB
        return CheckResult("Free disk space", True, f"{free_gb:.1f} GB")

    def _check_database(self) -> CheckResult:
        if not self._schema.exists():
            return CheckResult("Database", True, "not created yet. The first start creates it")
        if not self._schema.is_intact():
            return CheckResult(
                "Database",
                False,
                f"{self._info.database_file} is damaged",
                "Report a problem at https://github.com/mderis/yt-mirror/issues.",
            )
        version = self._schema.current_version()
        return CheckResult("Database", True, f"schema version {version}")
