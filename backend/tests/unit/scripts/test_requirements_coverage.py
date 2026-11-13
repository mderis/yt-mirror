"""Tests of ``scripts/requirements_coverage.py``."""

from pathlib import Path

import pytest

import requirements_coverage as script


def fake_id(area: str, number: int) -> str:
    """Build a requirement ID.

    The sample IDs of this file are built here instead of written out, so that the
    coverage script, which reads this file too, does not count them as real coverage.
    """
    return f"R-{area}-{number:02d}"


# Sample IDs. They look like real ones on purpose.
CH1 = fake_id("CH", 1)
CH2 = fake_id("CH", 2)
CH3 = fake_id("CH", 3)
DT7 = fake_id("DT", 7)
DT8 = fake_id("DT", 8)
FN5 = fake_id("FN", 5)
FN4 = fake_id("FN", 4)
UI1 = fake_id("UI", 1)
PL4 = fake_id("PL", 4)

# IDs that are not in the spec.
FAKE_PROSE = fake_id("ZZ", 99)
FAKE_TYPO = fake_id("CH", 99)
FAKE_EXEMPT = fake_id("XX", 1)
FAKE_OTHER = fake_id("QQ", 1)
FAKE_SECOND = fake_id("CH", 77)
FAKE_VENDOR = fake_id("ZZ", 1)

SPEC = f"""
| ID | Requirement |
|---|---|
| {CH1} | The user adds a channel. See also {CH2} for what is rejected. |
| {CH2} | Anything else is rejected. |
| {CH3} | Removed. |
| {DT7} | File dates equal the published time. |

Text that mentions {FAKE_PROSE} outside a table row defines nothing.
"""


def test_the_spec_ids_are_the_first_cells_of_its_tables_in_order() -> None:
    """R-QA-01: requirement IDs come from the spec tables, not from prose."""
    assert script.spec_ids(SPEC) == [CH1, CH2, DT7]


def test_a_removed_requirement_keeps_its_id_but_needs_no_test() -> None:
    """R-QA-01: a removed requirement keeps its ID and is marked "Removed" (docs/SPEC.md)."""
    assert CH3 not in script.spec_ids(SPEC)


def test_ids_are_found_anywhere_in_a_test_file() -> None:
    """R-QA-01: each test names the requirement IDs it covers, in a docstring or a title."""
    text = (
        f'"""{FN5}, {FN4}: suffix."""\nit("{UI1}: shell", () => {{}})\n# not an ID: R-FN-5, X{FN5}'
    )

    assert script.ids_in(text) == {FN5, FN4, UI1}


def test_a_requirement_named_by_any_test_is_covered() -> None:
    """R-QA-01: one naming test is enough to count a requirement as covered."""
    report = script.build_report(
        [CH1, CH2, DT7],
        {"backend/tests/a.py": {CH1}, "e2e/tests/b.ts": {CH1, DT7}},
        {},
    )

    assert report.covered == (CH1, DT7)
    assert report.uncovered == (CH2,)
    assert report.untestable == {}
    assert report.unknown == {}
    assert report.total == 3


def test_an_untestable_requirement_is_accounted_for_with_its_reason() -> None:
    """R-QA-02: requirements that need the real YouTube are listed, not forgotten."""
    report = script.build_report([CH1, CH2], {}, {CH2: "Needs the real YouTube."})

    assert report.untestable == {CH2: "Needs the real YouTube."}
    assert report.uncovered == (CH1,)


def test_a_test_wins_over_an_untestable_entry() -> None:
    """R-QA-01: once a test exists, the requirement counts as covered."""
    report = script.build_report([CH1], {"t.py": {CH1}}, {CH1: "Old reason."})

    assert report.covered == (CH1,)
    assert report.untestable == {}


def test_ids_that_are_not_in_the_spec_are_reported_with_their_files() -> None:
    """R-QA-01: a typo in an ID must not look like coverage."""
    report = script.build_report(
        [CH1],
        {"b.py": {FAKE_TYPO}, "a.py": {FAKE_TYPO, CH1}},
        {FAKE_EXEMPT: "Not in the spec."},
    )

    assert report.unknown == {FAKE_TYPO: ("a.py", "b.py"), FAKE_EXEMPT: ("untestable.yml",)}


def test_report_mode_passes_with_gaps_and_strict_mode_fails() -> None:
    """R-QA-01: the script only reports until the final milestone turns on --strict."""
    with_gaps = script.build_report([CH1, CH2], {"t.py": {CH1}}, {})
    complete = script.build_report([CH1], {"t.py": {CH1}}, {})

    assert script.exit_code(with_gaps, strict=False) == 0
    assert script.exit_code(with_gaps, strict=True) == 1
    assert script.exit_code(complete, strict=True) == 0


def test_an_unknown_id_fails_in_every_mode() -> None:
    """R-QA-01: an ID outside the spec is always an error."""
    report = script.build_report([CH1], {"t.py": {CH1, FAKE_SECOND}}, {})

    assert script.exit_code(report, strict=False) == 1
    assert script.exit_code(report, strict=True) == 1


def test_the_text_report_shows_counts_gaps_by_area_and_errors() -> None:
    """R-QA-01: the output tells what is missing at a glance."""
    report = script.build_report(
        [CH1, CH2, DT7, DT8],
        {"t.py": {CH1, FAKE_OTHER}},
        {DT8: "By hand only."},
    )

    assert script.render(report) == (
        "Requirement coverage (docs/SPEC.md against the tests)\n"
        "\n"
        "  Requirements in the spec:   4\n"
        "  Named by a test:            1\n"
        "  Listed as untestable:       1\n"
        "  Without a test:             2\n"
        "\n"
        "Without a test:\n"
        f"  R-CH: {CH2}\n"
        f"  R-DT: {DT7}\n"
        "\n"
        "Listed as untestable:\n"
        f"  {DT8}: By hand only.\n"
        "\n"
        "ERROR: IDs that are not in the spec:\n"
        f"  {FAKE_OTHER} in t.py\n"
    )


def test_the_untestable_list_is_read_from_yaml() -> None:
    """R-QA-02: untestable.yml holds an ID and a reason per entry."""
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
    """R-QA-02: an exemption always says which requirement and why."""
    with pytest.raises(ValueError, match="every entry needs an id and a reason"):
        script.load_untestable(text)


def test_test_files_are_collected_from_backend_frontend_and_e2e(tmp_path: Path) -> None:
    """R-QA-01: tests of every layer count, and third-party folders do not."""
    files = {
        "backend/tests/unit/test_a.py": f'"""{CH1}: a."""',
        "frontend/tests/b.test.ts": f"it('{UI1}: b', () => {{}})",
        "e2e/tests/c.spec.ts": f"test('{PL4}: c', () => {{}})",
        "e2e/tests/node_modules/pkg/d.ts": f"// {FAKE_VENDOR} in a dependency",
        "backend/tests/unit/test_none.py": "def test_nothing(): pass",
        "backend/ytmirror/core/x.py": f'"""Implements {FN4}."""',
    }
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    assert script.collect_test_ids(tmp_path) == {
        "backend/tests/unit/test_a.py": {CH1},
        "frontend/tests/b.test.ts": {UI1},
        "e2e/tests/c.spec.ts": {PL4},
    }


def test_this_repository_has_no_unknown_ids(capsys: pytest.CaptureFixture[str]) -> None:
    """R-QA-01: every ID the real tests name exists in the real spec."""
    exit_code = script.main([])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "ERROR" not in output
    assert "Requirements in the spec:" in output
