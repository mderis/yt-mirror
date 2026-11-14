"""Fixtures for tests that run the real app on a throwaway installation."""

from pathlib import Path

import pytest

from ytmirror.app.config import AppPaths

INDEX_HTML = "<!doctype html><title>yt-mirror</title><div id='app'></div>"


@pytest.fixture
def paths(tmp_path: Path) -> AppPaths:
    """An installation in a temp folder, with a built interface and no data yet."""
    frontend_dir = tmp_path / "frontend" / "dist"
    frontend_dir.mkdir(parents=True)
    (frontend_dir / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    data_dir = tmp_path / "data"
    return AppPaths(
        code_root=tmp_path,
        home_dir=tmp_path,
        data_dir=data_dir,
        logs_dir=data_dir / "logs",
        database_file=data_dir / "yt-mirror.db",
        frontend_dir=frontend_dir,
        uv_executable=tmp_path / "tools" / "uv" / "uv",
        tool_dir=tmp_path / "tools",
        cache_dir=data_dir / "cache",
        default_library=tmp_path / "library",
    )
