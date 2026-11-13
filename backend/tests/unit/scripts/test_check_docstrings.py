"""Tests of ``scripts/check_docstrings.py``."""

from pathlib import Path

import pytest

import check_docstrings as script


def test_a_module_docstring_with_a_tests_line_passes() -> None:
    """infra: every module says where its counterpart tests live."""
    source = '"""Does a thing.\n\nTests: backend/tests/unit/test_thing.py\n"""\n\nX = 1\n'

    assert script.names_its_tests(source)


@pytest.mark.parametrize(
    "source",
    [
        "X = 1\n",
        '"""Does a thing, but does not say where it is tested."""\n',
        '"""Mentions Tests: only in the middle of a line."""\n',
        'X = 1\n"""Tests: this is not the module docstring."""\n',
    ],
)
def test_a_module_without_a_tests_line_fails(source: str) -> None:
    """infra: a missing or misplaced "Tests:" line is found."""
    assert not script.names_its_tests(source)


def test_package_markers_are_exempt_and_every_other_module_is_checked(tmp_path: Path) -> None:
    """infra: ``__init__.py`` files hold no code to test."""
    for name in ("backend/ytmirror/__init__.py", "backend/ytmirror/core/naming.py", "scripts/x.py"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    (tmp_path / "backend" / "tests").mkdir()
    (tmp_path / "backend" / "tests" / "test_x.py").write_text("", encoding="utf-8")

    found = [str(path.relative_to(tmp_path)) for path in script.modules_to_check(tmp_path)]

    assert found == ["backend/ytmirror/core/naming.py", "scripts/x.py"]


def test_every_module_of_this_repository_names_its_tests(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """infra: the repository follows its own rule."""
    exit_code = script.main([])

    assert capsys.readouterr().out == "Every module names its tests.\n"
    assert exit_code == 0


def test_modules_without_the_line_are_listed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """infra: the failure names each file to fix."""
    bad = tmp_path / "backend" / "ytmirror" / "services" / "queue.py"
    bad.parent.mkdir(parents=True)
    bad.write_text('"""No tests named."""\n', encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    monkeypatch.setattr(script, "REPO_ROOT", tmp_path)

    exit_code = script.main([])

    assert exit_code == 1
    assert "backend/ytmirror/services/queue.py" in capsys.readouterr().out
