"""Tests of ``scripts/requirements_coverage.py``."""

from pathlib import Path

import pytest

import requirements_coverage as script
from requirements_coverage import TestCase

SPEC = """
| ID | Requirement |
|---|---|
| R-CH-01 | The user adds a channel. See also R-CH-02 for what is rejected. |
| R-CH-02 | Anything else is rejected. |
| R-CH-03 | Removed. |
| R-DT-07 | File dates equal the published time. |

Text that mentions R-ZZ-99 outside a table row defines nothing.
"""


def case(label: str, file: str = "backend/tests/test_a.py", name: str = "test_x") -> TestCase:
    """Return a test with the given docstring or title."""
    return TestCase(file, name, label)


def test_the_spec_ids_are_the_first_cells_of_its_tables_in_order() -> None:
    """infra: requirement IDs come from the spec tables, not from prose."""
    assert script.spec_ids(SPEC) == ["R-CH-01", "R-CH-02", "R-DT-07"]


def test_a_removed_requirement_keeps_its_id_but_needs_no_test() -> None:
    """infra: a removed requirement keeps its ID and is marked "Removed" (docs/SPEC.md)."""
    assert "R-CH-03" not in script.spec_ids(SPEC)


def test_a_test_names_the_ids_of_its_docstring_or_title() -> None:
    """infra: a test covers the requirement IDs its label names."""
    test = case("R-FN-05, R-FN-04: a second video with the same title gets the ID suffix.")

    assert test.ids == {"R-FN-05", "R-FN-04"}
    assert test.is_marked
    assert not test.is_infra
    assert test.where == "backend/tests/test_a.py::test_x"


def test_an_infra_test_covers_nothing_even_when_it_mentions_an_id() -> None:
    """infra: the infra marker means no requirement, whatever else the label says."""
    test = case("infra: the fake clock moves only when told. Unrelated to R-DT-02.")

    assert test.is_infra
    assert test.is_marked
    assert test.ids == frozenset()


@pytest.mark.parametrize(
    "label",
    ["", "The clock is in UTC.", "Covers R-DT-02 somewhere in the middle.", "Infra: wrong case"],
)
def test_a_label_that_starts_with_neither_an_id_nor_the_marker_is_unmarked(label: str) -> None:
    """infra: every test must say at its start what it covers."""
    assert not case(label).is_marked


def test_python_tests_are_the_test_functions_with_their_docstrings() -> None:
    """infra: functions named test_ are tests, also inside classes and when async."""
    source = '''
"""Module docstring that mentions R-CH-01 and must not count."""

def helper():
    """R-CH-02: not a test."""

def test_b():
    """R-DT-07: dates."""

class TestGroup:
    async def test_a(self):
        """infra: a tool."""

def test_c():
    pass
'''

    tests = script.python_tests("backend/tests/test_x.py", source)

    assert [(test.name, test.label) for test in tests] == [
        ("test_a", "infra: a tool."),
        ("test_b", "R-DT-07: dates."),
        ("test_c", ""),
    ]


def test_typescript_tests_are_the_it_and_test_calls_with_their_titles() -> None:
    """infra: titles of it() and test() calls are read, with any quote and across lines."""
    source = """
describe('R-CH-02: a group title does not count', () => {
  it('R-UI-01: the shell', () => {})
  it.skip("infra: a tool's check", () => {})
  test(
    `R-PL-04, R-IN-02: the ${kind} URL`,
    async ({ page }) => {},
  )
  test.use({ colorScheme: 'dark' })
  expect(submit('R-CH-01')).toBe(true)
})
"""

    tests = script.typescript_tests("e2e/tests/a.spec.ts", source)

    assert [test.label for test in tests] == [
        "R-UI-01: the shell",
        "infra: a tool's check",
        "R-PL-04, R-IN-02: the ${kind} URL",
    ]
    assert [sorted(test.ids) for test in tests] == [["R-UI-01"], [], ["R-IN-02", "R-PL-04"]]


def test_a_requirement_named_by_any_test_is_covered() -> None:
    """infra: one naming test is enough to count a requirement as covered."""
    report = script.build_report(
        ["R-CH-01", "R-CH-02", "R-DT-07"],
        [case("R-CH-01: a"), case("R-CH-01, R-DT-07: b", file="e2e/tests/b.ts")],
        {},
    )

    assert report.covered == ("R-CH-01", "R-DT-07")
    assert report.uncovered == ("R-CH-02",)
    assert report.untestable == {}
    assert report.unknown == {}
    assert report.unmarked == ()
    assert report.total == 3
    assert report.requirement_tests == 2
    assert report.infra_tests == 0


def test_infra_tests_are_counted_but_never_cover_a_requirement() -> None:
    """infra: an infrastructure test cannot make a requirement look covered."""
    report = script.build_report(
        ["R-CH-01"], [case("infra: mentions R-CH-01 and R-ZZ-99"), case("infra: other")], {}
    )

    assert report.covered == ()
    assert report.uncovered == ("R-CH-01",)
    assert report.unknown == {}
    assert report.infra_tests == 2
    assert report.requirement_tests == 0


def test_an_untestable_requirement_is_accounted_for_with_its_reason() -> None:
    """infra: requirements that need the real YouTube are listed, not forgotten."""
    report = script.build_report(["R-CH-01", "R-CH-02"], [], {"R-CH-02": "Needs the real YouTube."})

    assert report.untestable == {"R-CH-02": "Needs the real YouTube."}
    assert report.uncovered == ("R-CH-01",)


def test_a_test_wins_over_an_untestable_entry() -> None:
    """infra: once a test exists, the requirement counts as covered."""
    report = script.build_report(["R-CH-01"], [case("R-CH-01: a")], {"R-CH-01": "Old reason."})

    assert report.covered == ("R-CH-01",)
    assert report.untestable == {}


def test_ids_that_are_not_in_the_spec_are_reported_with_their_files() -> None:
    """infra: a typo in an ID must not look like coverage."""
    report = script.build_report(
        ["R-CH-01"],
        [case("R-CH-99: typo", file="b.py"), case("R-CH-99, R-CH-01: typo", file="a.py")],
        {"R-XX-01": "Not in the spec."},
    )

    assert report.unknown == {"R-CH-99": ("a.py", "b.py"), "R-XX-01": ("untestable.yml",)}


def test_unmarked_tests_are_listed_by_file_and_name() -> None:
    """infra: a test without an ID and without the marker is found."""
    report = script.build_report(
        ["R-CH-01"],
        [
            case("Says nothing about what it covers.", file="b.py", name="test_two"),
            case("", file="a.py", name="test_one"),
            case("R-CH-01: fine"),
        ],
        {},
    )

    assert report.unmarked == ("a.py::test_one", "b.py::test_two")


def test_report_mode_passes_with_gaps_and_strict_mode_fails() -> None:
    """infra: the script only reports gaps until the final milestone turns on --strict."""
    with_gaps = script.build_report(["R-CH-01", "R-CH-02"], [case("R-CH-01: a")], {})
    complete = script.build_report(["R-CH-01"], [case("R-CH-01: a")], {})

    assert script.exit_code(with_gaps, strict=False) == 0
    assert script.exit_code(with_gaps, strict=True) == 1
    assert script.exit_code(complete, strict=True) == 0


def test_an_unknown_id_or_an_unmarked_test_fails_in_every_mode() -> None:
    """infra: both are mistakes in the tests, not gaps in the app."""
    unknown = script.build_report(["R-CH-01"], [case("R-CH-01, R-CH-77: a")], {})
    unmarked = script.build_report(["R-CH-01"], [case("R-CH-01: a"), case("No marker.")], {})

    for report in (unknown, unmarked):
        assert script.exit_code(report, strict=False) == 1
        assert script.exit_code(report, strict=True) == 1


def test_the_text_report_shows_counts_gaps_by_area_and_errors() -> None:
    """infra: the output tells what is missing at a glance."""
    report = script.build_report(
        ["R-CH-01", "R-CH-02", "R-DT-07", "R-DT-08"],
        [
            case("R-CH-01, R-QQ-01: a", file="t.py"),
            case("infra: a tool", file="t.py"),
            case("Nothing.", file="t.py", name="test_bare"),
        ],
        {"R-DT-08": "By hand only."},
    )

    assert script.render(report) == (
        "Requirement coverage (docs/SPEC.md against the tests)\n"
        "\n"
        "  Requirements in the spec:   4\n"
        "  Named by a test:            1\n"
        "  Listed as untestable:       1\n"
        "  Without a test:             2\n"
        "\n"
        "  Tests naming a requirement: 1\n"
        "  Infrastructure tests:       1\n"
        "\n"
        "Without a test:\n"
        "  R-CH: R-CH-02\n"
        "  R-DT: R-DT-07\n"
        "\n"
        "Listed as untestable:\n"
        "  R-DT-08: By hand only.\n"
        "\n"
        "ERROR: IDs that are not in the spec:\n"
        "  R-QQ-01 in t.py\n"
        "\n"
        'ERROR: tests that start with neither a requirement ID nor "infra:":\n'
        "  t.py::test_bare\n"
    )


def test_the_untestable_list_is_read_from_yaml() -> None:
    """infra: untestable.yml holds an ID and a reason per entry."""
    text = "requirements:\n  - id: R-QA-02\n    reason: Needs the real YouTube.\n"

    assert script.load_untestable(text) == {"R-QA-02": "Needs the real YouTube."}
    assert script.load_untestable("requirements: []\n") == {}
    assert script.load_untestable("# only a comment\n") == {}


@pytest.mark.parametrize(
    "text",
    [
        "requirements:\n  - id: R-QA-02\n",
        "requirements:\n  - reason: No id.\n",
        "requirements:\n  - id: QA-2\n    reason: Not an ID.\n",
    ],
)
def test_an_untestable_entry_without_id_or_reason_is_rejected(text: str) -> None:
    """infra: an exemption always says which requirement and why."""
    with pytest.raises(ValueError, match="every entry needs an id and a reason"):
        script.load_untestable(text)


def test_tests_are_collected_from_backend_frontend_and_e2e(tmp_path: Path) -> None:
    """infra: tests of every layer count, and third-party folders and app code do not."""
    files = {
        "backend/tests/unit/test_a.py": 'def test_a():\n    """R-CH-01: a."""\n',
        "frontend/tests/b.test.ts": "it('R-UI-01: b', () => {})",
        "e2e/tests/c.spec.ts": "test('infra: c', () => {})",
        "e2e/tests/node_modules/pkg/d.ts": "it('R-ZZ-01: in a dependency', () => {})",
        "backend/tests/fixtures/helper.py": 'def make():\n    """R-CH-02: not a test."""\n',
        "backend/ytmirror/core/x.py": 'def test_like():\n    """R-FN-01: app code."""\n',
    }
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    tests = script.collect_tests(tmp_path)

    assert [(test.file, test.label) for test in tests] == [
        ("backend/tests/unit/test_a.py", "R-CH-01: a."),
        ("frontend/tests/b.test.ts", "R-UI-01: b"),
        ("e2e/tests/c.spec.ts", "infra: c"),
    ]


def test_this_repository_has_no_unknown_ids_and_no_unmarked_tests(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """infra: the real tests follow the convention, and every ID they name is in the spec."""
    exit_code = script.main([])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "ERROR" not in output
    assert "Requirements in the spec:" in output


def test_a_test_marked_infra_in_its_docstring_carries_the_pytest_marker(
    request: pytest.FixtureRequest,
) -> None:
    """infra: ``pytest -m infra`` and ``-m "not infra"`` select by the same marker."""
    assert request.node.get_closest_marker("infra") is not None
