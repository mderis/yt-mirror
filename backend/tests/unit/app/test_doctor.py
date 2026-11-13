"""Tests of ``ytmirror.app.doctor``."""

import io
from pathlib import Path

from tests.fixtures.fakes.database_schema import FakeDatabaseSchema
from tests.fixtures.fakes.system_probe import FakeSystemProbe
from ytmirror.app.doctor import render_report, run_doctor
from ytmirror.core.models import AppInfo, CheckResult, InstallKind
from ytmirror.services.diagnostics import DiagnosticsService

HOME = Path("/apps/yt-mirror")


def make_diagnostics(probe: FakeSystemProbe) -> DiagnosticsService:
    """Return the diagnostics of an archive install on the given Mac."""
    info = AppInfo(
        version="1.0.0",
        install_kind=InstallKind.ARCHIVE,
        home_dir=HOME,
        data_dir=HOME / "data",
        database_file=HOME / "data" / "yt-mirror.db",
        frontend_dir=HOME / "app" / "frontend" / "dist",
        uv_executable=HOME / "tools" / "uv" / "uv",
    )
    return DiagnosticsService(info, FakeDatabaseSchema(current="0002"), probe)


def healthy_probe() -> FakeSystemProbe:
    """Return a Mac on which every check passes."""
    return FakeSystemProbe(
        commands={str(HOME / "tools" / "uv" / "uv"): "uv 0.13.8"},
        modules={"webview"},
        files={HOME / "app" / "frontend" / "dist" / "index.html"},
    )


def test_the_report_shows_pass_or_fail_per_item_with_the_fix() -> None:
    """R-IN-02: ``./start --doctor`` prints pass or fail per item with the fix."""
    results = [
        CheckResult("macOS", True, "15.6.1"),
        CheckResult("Node.js", False, "not found", "Install Node.js."),
    ]

    text = render_report(results)

    assert text == (
        "yt-mirror environment report\n"
        "\n"
        "[ ok ] macOS: 15.6.1\n"
        "[FAIL] Node.js: not found\n"
        "       Fix: Install Node.js.\n"
        "\n"
        "1 problem(s) found.\n"
    )


def test_a_report_without_failures_says_everything_is_in_order() -> None:
    """R-IN-02: a working environment gets a clear summary."""
    text = render_report([CheckResult("macOS", True, "15.6.1")])

    assert text.endswith("\nEverything is in order.\n")


def test_doctor_exits_with_zero_when_every_check_passes() -> None:
    """R-IN-02: scripts can rely on the exit code of ``./start --doctor``."""
    out = io.StringIO()

    exit_code = run_doctor(make_diagnostics(healthy_probe()), out)

    assert exit_code == 0
    assert "Everything is in order." in out.getvalue()


def test_doctor_exits_with_one_when_a_check_fails() -> None:
    """R-IN-02: a problem is visible in the exit code."""
    probe = healthy_probe()
    probe.macos = "13.2"
    out = io.StringIO()

    exit_code = run_doctor(make_diagnostics(probe), out)

    assert exit_code == 1
    assert "[FAIL] macOS: 13.2" in out.getvalue()
