"""Prints the environment report of ``./start --doctor``.

The checks themselves are in ``services/diagnostics.py``. This module only
turns their results into text.

Tests: backend/tests/unit/app/test_doctor.py
"""

from collections.abc import Sequence
from typing import TextIO

from ytmirror.core.models import CheckResult
from ytmirror.services.diagnostics import DiagnosticsService

_FIX_INDENT = " " * 7


def render_report(results: Sequence[CheckResult]) -> str:
    """Return the report as text, one line per check and one per fix.

    Args:
        results: The results of the checks, in display order.

    Returns:
        The text, ending with a summary line.
    """
    lines = ["yt-mirror environment report", ""]
    for result in results:
        mark = " ok " if result.ok else "FAIL"
        lines.append(f"[{mark}] {result.name}: {result.detail}")
        if result.fix is not None:
            lines.append(f"{_FIX_INDENT}Fix: {result.fix}")
    failed = sum(1 for result in results if not result.ok)
    lines.append("")
    lines.append("Everything is in order." if failed == 0 else f"{failed} problem(s) found.")
    return "\n".join(lines) + "\n"


def run_doctor(diagnostics: DiagnosticsService, out: TextIO) -> int:
    """Run the environment checks and write the report.

    Args:
        diagnostics: The service that performs the checks.
        out: Where the report is written.

    Returns:
        The process exit code: 0 when every check passed, otherwise 1.
    """
    results = diagnostics.environment_report()
    out.write(render_report(results))
    return 0 if all(result.ok for result in results) else 1
