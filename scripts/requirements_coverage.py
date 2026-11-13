"""Reports which requirements of docs/SPEC.md are named by a test.

Every requirement has an ID such as R-CH-03, and every test names the IDs it
covers (docs/TESTING.md rules 1 and 2). This program reads the IDs from the
spec and from the test files and prints the requirements no test names.
Requirements that can only be tested live or by hand are listed, with the
reason, in backend/tests/untestable.yml.

Run: python scripts/requirements_coverage.py [--strict]

Without --strict the program only reports and ends with exit code 0, because
the app is still being built milestone by milestone. With --strict a
requirement without a test is an error. A test that names an ID the spec does
not contain is always an error: it is a typo or a removed requirement.

Tests: backend/tests/unit/scripts/test_requirements_coverage.py
"""

import argparse
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_FILE = REPO_ROOT / "docs" / "SPEC.md"
UNTESTABLE_FILE = REPO_ROOT / "backend" / "tests" / "untestable.yml"
TEST_GLOBS = (
    "backend/tests/**/*.py",
    "frontend/tests/**/*.ts",
    "e2e/tests/**/*.ts",
)

_ID = re.compile(r"\bR-[A-Z]{2}-\d{2}\b")
_SPEC_ROW = re.compile(r"^\|\s*(R-[A-Z]{2}-\d{2})\s*\|\s*(.*?)\s*\|\s*$", re.MULTILINE)
_REMOVED = "removed"


@dataclass(frozen=True)
class Report:
    """The result of comparing the spec with the tests.

    Attributes:
        covered: Requirement IDs named by at least one test.
        untestable: Requirement IDs listed in untestable.yml, with the reason.
        uncovered: Requirement IDs no test names and that are not listed as untestable.
        unknown: IDs named by tests that the spec does not contain, with the files naming them.
    """

    covered: tuple[str, ...]
    untestable: Mapping[str, str]
    uncovered: tuple[str, ...]
    unknown: Mapping[str, tuple[str, ...]]

    @property
    def total(self) -> int:
        """The number of requirements in the spec."""
        return len(self.covered) + len(self.untestable) + len(self.uncovered)


def spec_ids(spec_text: str) -> list[str]:
    """Return the requirement IDs defined in the spec, in document order.

    A requirement marked "Removed" keeps its ID in the spec but needs no test.

    Args:
        spec_text: The content of docs/SPEC.md.
    """
    ids: list[str] = []
    for match in _SPEC_ROW.finditer(spec_text):
        if match.group(2).strip().lower().startswith(_REMOVED):
            continue
        ids.append(match.group(1))
    return ids


def ids_in(text: str) -> set[str]:
    """Return every requirement ID that appears in a text.

    Args:
        text: The content of a test file.
    """
    return set(_ID.findall(text))


def load_untestable(yaml_text: str) -> dict[str, str]:
    """Return the requirements that cannot be tested automatically, with the reason.

    Args:
        yaml_text: The content of untestable.yml.

    Raises:
        ValueError: When an entry has no ID or no reason.
    """
    data: object = yaml.safe_load(yaml_text)
    entries: object = cast(dict[str, object], data).get("requirements") if data else None
    result: dict[str, str] = {}
    for entry in cast(list[dict[str, object]], entries or []):
        requirement_id = str(entry.get("id", "")).strip()
        reason = str(entry.get("reason", "")).strip()
        if not _ID.fullmatch(requirement_id) or not reason:
            raise ValueError(f"untestable.yml: every entry needs an id and a reason, got {entry!r}")
        result[requirement_id] = reason
    return result


def build_report(
    spec: Sequence[str], ids_by_file: Mapping[str, Iterable[str]], untestable: Mapping[str, str]
) -> Report:
    """Compare the requirements of the spec with the IDs the tests name.

    Args:
        spec: The requirement IDs of the spec.
        ids_by_file: For each test file, the IDs it names.
        untestable: The requirements that cannot be tested automatically, with the reason.

    Returns:
        The report.
    """
    known = set(spec)
    named: set[str] = set()
    unknown: dict[str, list[str]] = {}
    for file, ids in sorted(ids_by_file.items()):
        for requirement_id in sorted(set(ids)):
            if requirement_id in known:
                named.add(requirement_id)
            else:
                unknown.setdefault(requirement_id, []).append(file)
    for requirement_id in untestable:
        if requirement_id not in known:
            unknown.setdefault(requirement_id, []).append("untestable.yml")
    return Report(
        covered=tuple(item for item in spec if item in named),
        untestable={
            item: untestable[item] for item in spec if item in untestable and item not in named
        },
        uncovered=tuple(item for item in spec if item not in named and item not in untestable),
        unknown={item: tuple(files) for item, files in sorted(unknown.items())},
    )


def render(report: Report) -> str:
    """Return the report as text.

    Args:
        report: The report to show.
    """
    lines = [
        "Requirement coverage (docs/SPEC.md against the tests)",
        "",
        f"  Requirements in the spec:   {report.total}",
        f"  Named by a test:            {len(report.covered)}",
        f"  Listed as untestable:       {len(report.untestable)}",
        f"  Without a test:             {len(report.uncovered)}",
    ]
    if report.uncovered:
        lines += ["", "Without a test:"]
        lines += _by_area(report.uncovered)
    if report.untestable:
        lines += ["", "Listed as untestable:"]
        lines += [f"  {item}: {reason}" for item, reason in report.untestable.items()]
    if report.unknown:
        lines += ["", "ERROR: IDs that are not in the spec:"]
        lines += [f"  {item} in {', '.join(files)}" for item, files in report.unknown.items()]
    return "\n".join(lines) + "\n"


def exit_code(report: Report, *, strict: bool) -> int:
    """Return the process exit code for a report.

    Args:
        report: The report.
        strict: Whether a requirement without a test is an error.
    """
    if report.unknown:
        return 1
    if strict and report.uncovered:
        return 1
    return 0


def collect_test_ids(repo_root: Path) -> dict[str, set[str]]:
    """Read every test file and return the requirement IDs each one names.

    Args:
        repo_root: The repository root.
    """
    result: dict[str, set[str]] = {}
    for pattern in TEST_GLOBS:
        for path in sorted(repo_root.glob(pattern)):
            if "node_modules" in path.parts or not path.is_file():
                continue
            found = ids_in(path.read_text(encoding="utf-8"))
            if found:
                result[str(path.relative_to(repo_root))] = found
    return result


def main(argv: Sequence[str]) -> int:
    """Run the report for this repository.

    Args:
        argv: The command line arguments without the program name.

    Returns:
        The process exit code.
    """
    parser = argparse.ArgumentParser(description="Report requirements without a test.")
    parser.add_argument("--strict", action="store_true", help="fail when a requirement has no test")
    options = parser.parse_args(list(argv))
    report = build_report(
        spec_ids(SPEC_FILE.read_text(encoding="utf-8")),
        collect_test_ids(REPO_ROOT),
        load_untestable(UNTESTABLE_FILE.read_text(encoding="utf-8")),
    )
    print(render(report), end="")
    return exit_code(report, strict=options.strict)


def _by_area(ids: Sequence[str]) -> list[str]:
    """Return one line per requirement area, for example all R-CH IDs together."""
    areas: dict[str, list[str]] = {}
    for requirement_id in ids:
        areas.setdefault(requirement_id[:4], []).append(requirement_id)
    return [f"  {area}: {', '.join(members)}" for area, members in areas.items()]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
