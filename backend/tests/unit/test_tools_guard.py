"""Tests of the guard that keeps the tests away from the real tools folder (tests/conftest.py)."""

from pathlib import Path

from tests.conftest import REAL_TOOLS, real_tools_state


def test_the_guard_sees_a_tool_that_was_removed_or_rewritten(tmp_path: Path) -> None:
    """infra: a removed program and a rewritten marker both change what the guard sees."""
    (tmp_path / "ffmpeg").mkdir()
    (tmp_path / "ffmpeg" / "ffmpeg").write_bytes(b"program")
    (tmp_path / "ffmpeg" / "installed.json").write_text('{"version": "1"}', encoding="utf-8")
    before = real_tools_state(tmp_path)

    (tmp_path / "ffmpeg" / "installed.json").write_text('{"version": "22"}', encoding="utf-8")
    rewritten = real_tools_state(tmp_path)
    (tmp_path / "ffmpeg" / "ffmpeg").unlink()
    removed = real_tools_state(tmp_path)

    assert len(before) == 2
    assert rewritten != before
    assert [name for name, _size, _time in removed] == ["ffmpeg/installed.json"]


def test_the_guard_watches_the_tools_of_the_app_folder_these_tests_run_from() -> None:
    """infra: the folder the guard compares is the ``tools`` folder next to ``backend``."""
    assert REAL_TOOLS.name == "tools"
    assert (REAL_TOOLS.parent / "backend").is_dir()
    assert (REAL_TOOLS.parent / "start").is_file()
