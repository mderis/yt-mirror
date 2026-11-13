"""Tests of ``scripts/check_no_em_dash.py``."""

from pathlib import Path

import pytest

import check_no_em_dash as script

EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)


def test_each_line_with_an_em_dash_is_reported() -> None:
    """infra: the maintainer's rule against em dashes is checked by a tool."""
    text = f"clean\nnot {EM_DASH} clean\nclean\nalso{EM_DASH}not"

    assert script.find_em_dashes(Path("docs/A.md"), text) == ["docs/A.md:2", "docs/A.md:4"]


def test_hyphens_and_en_dashes_are_not_em_dashes() -> None:
    """infra: only the em dash is banned."""
    assert script.find_em_dashes(Path("a.md"), f"yt-mirror, pages 3{EN_DASH}4, -- and ---") == []


def test_text_files_are_checked_and_binary_and_missing_files_are_skipped(tmp_path: Path) -> None:
    """infra: fonts and images cannot contain prose, and a deleted file is not an error."""
    (tmp_path / "bad.md").write_text(f"a {EM_DASH} b\n", encoding="utf-8")
    (tmp_path / "good.md").write_text("a - b\n", encoding="utf-8")
    (tmp_path / "font.woff2").write_bytes(b"\xff\xfe\x00\x14\x20\xe2\x80")

    found = script.check_files(tmp_path, ["bad.md", "good.md", "font.woff2", "deleted.md"])

    assert found == ["bad.md:1"]


def test_this_repository_contains_no_em_dash(capsys: pytest.CaptureFixture[str]) -> None:
    """infra: the repository follows its own rule (AGENTS.md rule 11)."""
    exit_code = script.main([])

    assert capsys.readouterr().out == "No em dashes.\n"
    assert exit_code == 0


def test_named_files_can_be_checked_alone_and_a_finding_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """infra: the pre-commit hook passes only the changed files."""
    (tmp_path / "note.md").write_text(f"wrong {EM_DASH} here\n", encoding="utf-8")
    monkeypatch.setattr(script, "REPO_ROOT", tmp_path)

    exit_code = script.main(["note.md"])

    assert exit_code == 1
    assert "note.md:1" in capsys.readouterr().out
