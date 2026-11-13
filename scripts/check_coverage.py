"""Checks the backend coverage thresholds per scope (docs/TESTING.md section 3).

pytest-cov knows one global threshold only. The project has three: core,
services, and the backend overall. This program reads the JSON coverage
report and checks each scope. A scope without any code yet counts as met.

Run: pytest --cov --cov-report=json:coverage.json
     python scripts/check_coverage.py coverage.json

Tests: backend/tests/unit/scripts/test_check_coverage.py
"""

import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast


@dataclass(frozen=True)
class Scope:
    """One row of the threshold table.

    Attributes:
        name: The name shown in the report.
        prefix: Files whose path starts with this belong to the scope.
        lines: The minimum line coverage in percent.
        branches: The minimum branch coverage in percent.
    """

    name: str
    prefix: str
    lines: float
    branches: float


SCOPES = (
    Scope("core", "backend/ytmirror/core/", lines=100, branches=95),
    Scope("services", "backend/ytmirror/services/", lines=95, branches=90),
    Scope("backend overall", "backend/ytmirror/", lines=90, branches=85),
)


@dataclass(frozen=True)
class Result:
    """The coverage of one scope.

    Attributes:
        scope: The scope.
        lines: The line coverage in percent.
        branches: The branch coverage in percent.
    """

    scope: Scope
    lines: float
    branches: float

    @property
    def ok(self) -> bool:
        """Whether both thresholds are met."""
        return self.lines >= self.scope.lines and self.branches >= self.scope.branches


def measure(report: Mapping[str, object], scope: Scope) -> Result:
    """Return the coverage of one scope from a coverage.py JSON report.

    Args:
        report: The parsed JSON report.
        scope: The scope to measure.
    """
    statements = covered = branches = covered_branches = 0
    files = cast(dict[str, dict[str, dict[str, int]]], report.get("files") or {})
    for path, data in files.items():
        if not path.replace("\\", "/").startswith(scope.prefix):
            continue
        summary = data["summary"]
        statements += summary["num_statements"]
        covered += summary["covered_lines"]
        branches += summary.get("num_branches", 0)
        covered_branches += summary.get("covered_branches", 0)
    return Result(scope, _percent(covered, statements), _percent(covered_branches, branches))


def render(results: Sequence[Result]) -> str:
    """Return the results as text, one line per scope.

    Args:
        results: The measured scopes.
    """
    lines = ["Coverage thresholds (docs/TESTING.md section 3)", ""]
    for result in results:
        mark = " ok " if result.ok else "FAIL"
        lines.append(
            f"[{mark}] {result.scope.name}: "
            f"lines {result.lines:.1f}% (needs {result.scope.lines:g}%), "
            f"branches {result.branches:.1f}% (needs {result.scope.branches:g}%)"
        )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str]) -> int:
    """Check the thresholds for a JSON coverage report.

    Args:
        argv: The path of the JSON report.

    Returns:
        The process exit code: 1 when a threshold is missed.
    """
    if len(argv) != 1:
        print("Usage: python scripts/check_coverage.py coverage.json")
        return 2
    report: dict[str, object] = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    results = [measure(report, scope) for scope in SCOPES]
    print(render(results), end="")
    return 0 if all(result.ok for result in results) else 1


def _percent(part: int, whole: int) -> float:
    """Return a share in percent. Nothing to cover counts as fully covered."""
    return 100.0 if whole == 0 else 100.0 * part / whole


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
