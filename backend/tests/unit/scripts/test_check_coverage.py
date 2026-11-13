"""Tests of ``scripts/check_coverage.py``."""

import json
from pathlib import Path

import pytest

import check_coverage as script


def file_summary(statements: int, covered: int, branches: int, covered_branches: int) -> object:
    """Return the entry of one file in a coverage.py JSON report."""
    return {
        "summary": {
            "num_statements": statements,
            "covered_lines": covered,
            "num_branches": branches,
            "covered_branches": covered_branches,
        }
    }


def report(**files: object) -> dict[str, object]:
    """Return a JSON report with the given files, keyed by a short name."""
    paths = {
        "core": "backend/ytmirror/core/naming.py",
        "services": "backend/ytmirror/services/queue.py",
        "api": "backend/ytmirror/api/app.py",
    }
    return {"files": {paths[name]: summary for name, summary in files.items()}}


CORE, SERVICES, OVERALL = script.SCOPES


def test_the_thresholds_are_those_of_the_testing_document() -> None:
    """infra: core 100/95, services 95/90, backend overall 90/85 (docs/TESTING.md section 3)."""
    assert [(s.name, s.lines, s.branches) for s in script.SCOPES] == [
        ("core", 100, 95),
        ("services", 95, 90),
        ("backend overall", 90, 85),
    ]


def test_each_scope_counts_only_its_own_files() -> None:
    """infra: a well covered API cannot hide a gap in core."""
    data = report(
        core=file_summary(10, 9, 4, 4),
        services=file_summary(100, 96, 10, 9),
        api=file_summary(90, 90, 6, 6),
    )

    core = script.measure(data, CORE)
    services = script.measure(data, SERVICES)
    overall = script.measure(data, OVERALL)

    assert (core.lines, core.branches, core.ok) == (90.0, 100.0, False)
    assert (services.lines, services.branches, services.ok) == (96.0, 90.0, True)
    assert overall.lines == pytest.approx(97.5)
    assert overall.branches == pytest.approx(95.0)
    assert overall.ok


def test_a_missed_branch_threshold_fails_even_with_full_line_coverage() -> None:
    """infra: branch coverage has its own floor."""
    result = script.measure(report(core=file_summary(10, 10, 20, 18)), CORE)

    assert result.lines == 100.0
    assert result.branches == 90.0
    assert not result.ok


def test_a_scope_without_code_counts_as_met() -> None:
    """infra: an early milestone with an empty package does not fail the check."""
    result = script.measure(report(api=file_summary(5, 5, 0, 0)), SERVICES)

    assert (result.lines, result.branches, result.ok) == (100.0, 100.0, True)
    assert script.measure({}, CORE).ok


def test_the_report_and_exit_code_show_which_scope_failed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """infra: CI fails with a line that names the scope and the numbers."""
    path = tmp_path / "coverage.json"
    path.write_text(
        json.dumps(report(core=file_summary(10, 9, 0, 0), services=file_summary(10, 10, 2, 2))),
        encoding="utf-8",
    )

    exit_code = script.main([str(path)])

    assert exit_code == 1
    assert capsys.readouterr().out == (
        "Coverage thresholds (docs/TESTING.md section 3)\n"
        "\n"
        "[FAIL] core: lines 90.0% (needs 100%), branches 100.0% (needs 95%)\n"
        "[ ok ] services: lines 100.0% (needs 95%), branches 100.0% (needs 90%)\n"
        "[ ok ] backend overall: lines 95.0% (needs 90%), branches 100.0% (needs 85%)\n"
    )


def test_full_coverage_passes(tmp_path: Path) -> None:
    """infra: a fully covered report ends with exit code 0."""
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps(report(core=file_summary(3, 3, 2, 2))), encoding="utf-8")

    assert script.main([str(path)]) == 0


def test_without_a_report_file_the_usage_is_shown(capsys: pytest.CaptureFixture[str]) -> None:
    """infra: a wrong call explains itself."""
    assert script.main([]) == 2
    assert "Usage:" in capsys.readouterr().out
