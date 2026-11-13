"""Tests of ``ytmirror.services.diagnostics``."""

from pathlib import Path

from tests.fixtures.fakes.database_schema import FakeDatabaseSchema
from tests.fixtures.fakes.system_probe import FakeSystemProbe
from ytmirror.core.models import AppInfo, CheckResult, InstallKind
from ytmirror.services.diagnostics import DiagnosticsService

HOME = Path("/apps/yt-mirror")
UV = HOME / "tools" / "uv" / "uv"
FRONTEND = HOME / "frontend" / "dist"


def make_info(install_kind: InstallKind = InstallKind.CLONE) -> AppInfo:
    """Return the facts of an installation in ``HOME``."""
    return AppInfo(
        version="1.2.3",
        install_kind=install_kind,
        home_dir=HOME,
        data_dir=HOME / "data",
        database_file=HOME / "data" / "yt-mirror.db",
        frontend_dir=FRONTEND,
        uv_executable=UV,
    )


def healthy_probe() -> FakeSystemProbe:
    """Return a Mac on which every check passes."""
    return FakeSystemProbe(
        commands={str(UV): "uv 0.13.8", "node": "v26.8.1"},
        modules={"webview"},
        files={FRONTEND / "index.html"},
    )


def report(
    probe: FakeSystemProbe | None = None,
    schema: FakeDatabaseSchema | None = None,
    install_kind: InstallKind = InstallKind.CLONE,
) -> dict[str, CheckResult]:
    """Run the environment report and return the results by name."""
    service = DiagnosticsService(
        make_info(install_kind),
        schema if schema is not None else FakeDatabaseSchema(current="0002"),
        probe if probe is not None else healthy_probe(),
    )
    return {result.name: result for result in service.environment_report()}


def test_health_reports_the_app_version_and_the_schema_version() -> None:
    """R-PL-12: the health endpoint is backed by the real versions."""
    service = DiagnosticsService(make_info(), FakeDatabaseSchema(current="0002"), healthy_probe())

    health = service.health()

    assert health.version == "1.2.3"
    assert health.schema_version == "0002"


def test_a_healthy_mac_passes_every_check_and_needs_no_fix() -> None:
    """R-LG-05: ``./start --doctor`` reports a working environment as such."""
    results = report()

    assert all(result.ok for result in results.values())
    assert all(result.fix is None for result in results.values())


def test_the_report_lists_its_checks_in_a_fixed_order() -> None:
    """R-LG-05: the report always reads the same way."""
    names = list(report())

    assert names == [
        "macOS",
        "Processor",
        "Python",
        "uv",
        "Node.js",
        "Interface",
        "App window",
        "Data folder",
        "Free disk space",
        "Database",
    ]


def test_macos_older_than_fifteen_fails_with_the_minimum_named() -> None:
    """R-PL-01, R-LG-05: the minimum is macOS 15."""
    probe = healthy_probe()
    probe.macos = "14.7.2"

    result = report(probe)["macOS"]

    assert not result.ok
    assert result.detail == "14.7.2"
    assert result.fix == "yt-mirror needs macOS 15 or newer."


def test_macos_fifteen_and_newer_pass() -> None:
    """R-PL-01, R-LG-05: macOS 15 itself and later versions are supported."""
    for version in ("15.0", "15.6.1", "26.1", "27.0"):
        probe = healthy_probe()
        probe.macos = version

        assert report(probe)["macOS"].ok, version


def test_an_unreadable_macos_version_fails_instead_of_crashing() -> None:
    """R-PL-01, R-LG-05: a version that cannot be read is reported, never guessed."""
    probe = healthy_probe()
    probe.macos = ""

    result = report(probe)["macOS"]

    assert not result.ok
    assert result.detail == "unknown"


def test_an_unsupported_processor_fails() -> None:
    """R-PL-01, R-LG-05: Apple Silicon and Intel only."""
    probe = healthy_probe()
    probe.architecture = "riscv64"

    result = report(probe)["Processor"]

    assert not result.ok
    assert result.fix is not None


def test_intel_processors_are_supported() -> None:
    """R-PL-01, R-LG-05: Intel Macs are supported."""
    probe = healthy_probe()
    probe.architecture = "x86_64"

    assert report(probe)["Processor"].ok


def test_missing_uv_fails_and_says_to_run_start_again() -> None:
    """R-LG-05: a missing tool gets a fix, not a stack trace."""
    probe = healthy_probe()
    del probe.commands[str(UV)]

    result = report(probe)["uv"]

    assert not result.ok
    assert result.fix == "Run ./start again. It downloads uv."


def test_missing_node_fails_in_a_clone() -> None:
    """R-LG-05: a clone needs Node.js to build the interface (docs/DECISIONS.md D-037)."""
    probe = healthy_probe()
    del probe.commands["node"]

    result = report(probe)["Node.js"]

    assert not result.ok
    assert result.fix is not None
    assert "nodejs.org" in result.fix


def test_node_is_not_checked_for_an_archive_install() -> None:
    """R-LG-05: an installed copy ships the built interface and never needs Node.js."""
    probe = healthy_probe()
    del probe.commands["node"]

    results = report(probe, install_kind=InstallKind.ARCHIVE)

    assert "Node.js" not in results
    assert all(result.ok for result in results.values())


def test_a_missing_interface_build_fails() -> None:
    """R-LG-05: the built interface must exist before the window can show it."""
    probe = healthy_probe()
    probe.files.clear()

    result = report(probe)["Interface"]

    assert not result.ok
    assert result.fix == "Run ./start. It builds the interface."


def test_a_missing_window_library_fails() -> None:
    """R-LG-05: the dedicated window needs pywebview."""
    probe = healthy_probe()
    probe.modules.clear()

    result = report(probe)["App window"]

    assert not result.ok
    assert result.fix is not None


def test_a_read_only_data_folder_fails() -> None:
    """R-LG-05: the app must be able to write its database and logs."""
    probe = healthy_probe()
    probe.writable = False

    result = report(probe)["Data folder"]

    assert not result.ok
    assert str(HOME / "data") in result.detail


def test_free_space_is_reported_in_gigabytes() -> None:
    """R-LG-05: the report shows the free space of the data volume."""
    probe = healthy_probe()
    probe.free = 3 * 1024**3 + 512 * 1024**2

    result = report(probe)["Free disk space"]

    assert result.ok
    assert result.detail == "3.5 GB"


def test_a_database_that_does_not_exist_yet_is_not_a_problem() -> None:
    """R-LG-05: before the first start there is no database, and that is fine."""
    result = report(schema=FakeDatabaseSchema(current=None))["Database"]

    assert result.ok
    assert "not created yet" in result.detail


def test_an_existing_database_reports_its_schema_version() -> None:
    """R-LG-05: the report shows which schema version the database has."""
    result = report(schema=FakeDatabaseSchema(current="0002"))["Database"]

    assert result.ok
    assert result.detail == "schema version 0002"


def test_a_damaged_database_fails() -> None:
    """R-LG-05: a database that fails its integrity check is reported."""
    result = report(schema=FakeDatabaseSchema(current="0002", intact=False))["Database"]

    assert not result.ok
    assert "damaged" in result.detail
    assert result.fix is not None
