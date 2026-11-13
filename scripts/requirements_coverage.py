"""Reports which requirements of docs/SPEC.md are named by a test.

Every requirement has an ID such as R-CH-03. Every test says what it covers
at the start of its docstring (Python) or its title (TypeScript), in one of
two ways (docs/TESTING.md rule 1):

    R-CH-03, R-CH-04: ...   the requirements the test covers
    infra: ...              an infrastructure test. It verifies no product behaviour at
                            all (test doubles, fixtures, check scripts, the test harness,
                            temporary scaffolding) and must not borrow an ID.

This program reads the IDs from the spec and from the tests and prints the
requirements no test names. Infrastructure tests are ignored: they never count
as coverage. Requirements that can only be tested live or by hand are listed,
with the reason, in backend/tests/untestable.yml.

Run: python scripts/requirements_coverage.py [--strict]

Without --strict the program only reports gaps and ends with exit code 0,
because the app is still being built milestone by milestone. With --strict a
requirement without a test is an error. Two things are always an error: a
test that names an ID the spec does not contain (a typo or a removed
requirement), and a test that starts with neither an ID nor the infra marker.

Tests: backend/tests/unit/scripts/test_requirements_coverage.py
"""

import argparse
import ast
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_FILE = REPO_ROOT / "docs" / "SPEC.md"
UNTESTABLE_FILE = REPO_ROOT / "backend" / "tests" / "untestable.yml"
PYTHON_TEST_GLOBS = ("backend/tests/**/*.py",)
TYPESCRIPT_TEST_GLOBS = ("frontend/tests/**/*.ts", "e2e/tests/**/*.ts")
INFRA_MARKER = "infra:"

_ID = re.compile(r"\bR-[A-Z]{2}-\d{2}\b")
_STARTS_WITH_ID = re.compile(r"R-[A-Z]{2}-\d{2}\b")
_SPEC_ROW = re.compile(r"^\|\s*(R-[A-Z]{2}-\d{2})\s*\|\s*(.*?)\s*\|\s*$", re.MULTILINE)
_REMOVED = "removed"
# A test in a TypeScript file: it('title', ...) or test(`title`, ...), also with .only and .skip.
_TS_TEST = re.compile(
    r"(?<![\w.])(?:it|test)(?:\.(?:only|skip|fixme|fails))?\(\s*"
    r"(?P<quote>['\"`])(?P<title>(?:\\.|(?!(?P=quote))[^\\])*)(?P=quote)"
)


@dataclass(frozen=True)
class TestCase:
    """One test, as far as this program cares.

    Attributes:
        file: The path of the test file, relative to the repository root.
        name: The function name (Python) or the title (TypeScript).
        label: The docstring or the title: the text that says what the test covers.
    """

    __test__ = False  # Not a pytest test class, although its name starts with "Test".

    file: str
    name: str
    label: str

    @property
    def is_infra(self) -> bool:
        """Whether the test carries the infra marker."""
        return self.label.lstrip().startswith(INFRA_MARKER)

    @property
    def ids(self) -> frozenset[str]:
        """The requirement IDs the test names. Empty for an infrastructure test."""
        if self.is_infra:
            return frozenset()
        return frozenset(_ID.findall(self.label))

    @property
    def is_marked(self) -> bool:
        """Whether the test starts with a requirement ID or with the infra marker."""
        return self.is_infra or _STARTS_WITH_ID.match(self.label.lstrip()) is not None

    @property
    def where(self) -> str:
        """The test as ``file::name``."""
        return f"{self.file}::{self.name}"


@dataclass(frozen=True)
class Report:
    """The result of comparing the spec with the tests.

    Attributes:
        covered: Requirement IDs named by at least one test.
        untestable: Requirement IDs listed in untestable.yml, with the reason.
        uncovered: Requirement IDs no test names and that are not listed as untestable.
        unknown: IDs named by tests that the spec does not contain, with the files naming them.
        unmarked: Tests that start with neither a requirement ID nor the infra marker.
        requirement_tests: The number of tests that name a requirement.
        infra_tests: The number of infrastructure tests.
    """

    covered: tuple[str, ...]
    untestable: Mapping[str, str]
    uncovered: tuple[str, ...]
    unknown: Mapping[str, tuple[str, ...]]
    unmarked: tuple[str, ...]
    requirement_tests: int
    infra_tests: int

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


def python_tests(file: str, source: str) -> list[TestCase]:
    """Return the tests of a Python file: every function whose name starts with ``test_``.

    Args:
        file: The path to show.
        source: The content of the file.
    """
    tests: list[TestCase] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test_"
        ):
            tests.append(TestCase(file, node.name, ast.get_docstring(node) or ""))
    return sorted(tests, key=lambda test: test.name)


def typescript_tests(file: str, source: str) -> list[TestCase]:
    """Return the tests of a TypeScript file: every ``it(...)`` and ``test(...)`` call.

    Args:
        file: The path to show.
        source: The content of the file.
    """
    return [
        TestCase(file, match.group("title"), match.group("title"))
        for match in _TS_TEST.finditer(source)
    ]


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
    spec: Sequence[str], tests: Sequence[TestCase], untestable: Mapping[str, str]
) -> Report:
    """Compare the requirements of the spec with what the tests say they cover.

    Args:
        spec: The requirement IDs of the spec.
        tests: Every test of the repository.
        untestable: The requirements that cannot be tested automatically, with the reason.

    Returns:
        The report.
    """
    known = set(spec)
    named: set[str] = set()
    unknown: dict[str, set[str]] = {}
    for test in tests:
        for requirement_id in test.ids:
            if requirement_id in known:
                named.add(requirement_id)
            else:
                unknown.setdefault(requirement_id, set()).add(test.file)
    for requirement_id in untestable:
        if requirement_id not in known:
            unknown.setdefault(requirement_id, set()).add("untestable.yml")
    return Report(
        covered=tuple(item for item in spec if item in named),
        untestable={
            item: untestable[item] for item in spec if item in untestable and item not in named
        },
        uncovered=tuple(item for item in spec if item not in named and item not in untestable),
        unknown={item: tuple(sorted(files)) for item, files in sorted(unknown.items())},
        unmarked=tuple(sorted(test.where for test in tests if not test.is_marked)),
        requirement_tests=sum(1 for test in tests if test.ids),
        infra_tests=sum(1 for test in tests if test.is_infra),
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
        "",
        f"  Tests naming a requirement: {report.requirement_tests}",
        f"  Infrastructure tests:       {report.infra_tests}",
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
    if report.unmarked:
        lines += [
            "",
            f'ERROR: tests that start with neither a requirement ID nor "{INFRA_MARKER}":',
        ]
        lines += [f"  {where}" for where in report.unmarked]
    return "\n".join(lines) + "\n"


def exit_code(report: Report, *, strict: bool) -> int:
    """Return the process exit code for a report.

    Args:
        report: The report.
        strict: Whether a requirement without a test is an error.
    """
    if report.unknown or report.unmarked:
        return 1
    if strict and report.uncovered:
        return 1
    return 0


def collect_tests(repo_root: Path) -> list[TestCase]:
    """Read every test file of the repository and return its tests.

    Args:
        repo_root: The repository root.
    """
    tests: list[TestCase] = []
    for globs, parse in (
        (PYTHON_TEST_GLOBS, python_tests),
        (TYPESCRIPT_TEST_GLOBS, typescript_tests),
    ):
        for pattern in globs:
            for path in sorted(repo_root.glob(pattern)):
                if "node_modules" in path.parts or not path.is_file():
                    continue
                relative = str(path.relative_to(repo_root))
                tests += parse(relative, path.read_text(encoding="utf-8"))
    return tests


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
        collect_tests(REPO_ROOT),
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
