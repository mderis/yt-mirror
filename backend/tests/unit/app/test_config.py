"""Tests of ``ytmirror.app.config``."""

from pathlib import Path

import pytest

from ytmirror.app.config import (
    DEFAULT_DEV_FRONTEND_URL,
    detect_install_kind,
    parse_options,
    resolve_paths,
)
from ytmirror.core.models import InstallKind


def test_in_a_clone_data_and_tools_are_next_to_the_code() -> None:
    """R-IN-07: a clone keeps ``data/`` and ``tools/`` in the repository root."""
    paths = resolve_paths({})

    assert (paths.code_root / "pyproject.toml").is_file()
    assert paths.home_dir == paths.code_root
    assert paths.data_dir == paths.code_root / "data"
    assert paths.logs_dir == paths.code_root / "data" / "logs"
    assert paths.database_file == paths.code_root / "data" / "yt-mirror.db"
    assert paths.frontend_dir == paths.code_root / "frontend" / "dist"
    assert paths.uv_executable == paths.code_root / "tools" / "uv" / "uv"


def test_the_home_folder_can_be_given_by_the_launcher(tmp_path: Path) -> None:
    """R-IN-07: ``./start`` tells the app where ``data/`` and ``tools/`` are."""
    paths = resolve_paths({"YTM_HOME": str(tmp_path)})

    assert paths.home_dir == tmp_path
    assert paths.data_dir == tmp_path / "data"
    assert paths.uv_executable == tmp_path / "tools" / "uv" / "uv"
    assert paths.frontend_dir == paths.code_root / "frontend" / "dist"


def test_the_data_folder_can_be_moved_for_tests(tmp_path: Path) -> None:
    """infra: automated tests run the real app on a throwaway data folder."""
    paths = resolve_paths({"YTM_DATA_DIR": str(tmp_path / "elsewhere")})

    assert paths.data_dir == tmp_path / "elsewhere"
    assert paths.database_file == tmp_path / "elsewhere" / "yt-mirror.db"
    assert paths.home_dir == paths.code_root


def test_downloaded_tools_and_their_manifest_have_their_place_in_the_app_folder(
    tmp_path: Path,
) -> None:
    """R-IN-03: tools are downloaded into the app folder, as the app's own manifest pins them."""
    paths = resolve_paths({"YTM_HOME": str(tmp_path)})

    assert paths.tool_dir == tmp_path / "tools"
    assert paths.tool_manifest == (
        paths.code_root / "backend" / "ytmirror" / "services" / "toolchain_manifest.json"
    )
    assert paths.tool_manifest.is_file()
    assert paths.only_tool_source is None


def test_tests_can_point_the_app_at_stand_in_tools(tmp_path: Path) -> None:
    """infra: the end-to-end tests install small stand-ins into a folder of their own."""
    paths = resolve_paths(
        {
            "YTM_TOOL_DIR": str(tmp_path / "tools"),
            "YTM_TOOL_MANIFEST": str(tmp_path / "manifest.json"),
            "YTM_TOOL_SOURCE": "jellyfin-ffmpeg",
        }
    )

    assert paths.tool_dir == tmp_path / "tools"
    assert paths.tool_manifest == tmp_path / "manifest.json"
    assert paths.only_tool_source == "jellyfin-ffmpeg"


def test_a_folder_with_git_is_a_clone_and_one_without_is_an_archive(tmp_path: Path) -> None:
    """R-UP-04: the install kind decides later how the app updates."""
    clone = tmp_path / "clone"
    (clone / ".git").mkdir(parents=True)
    archive = tmp_path / "archive"
    archive.mkdir()

    assert detect_install_kind(clone) is InstallKind.CLONE
    assert detect_install_kind(archive) is InstallKind.ARCHIVE


def test_without_flags_the_app_opens_its_window_on_any_free_port() -> None:
    """R-PL-02: the default is the dedicated window."""
    options = parse_options([], {})

    assert not (options.dev or options.debug or options.browser)
    assert not (options.doctor or options.update or options.no_window)
    assert options.port is None
    assert options.session_token is None
    assert options.frontend_url is None


@pytest.mark.parametrize("flag", ["dev", "debug", "browser", "doctor", "update"])
def test_each_flag_of_the_launcher_is_understood(flag: str) -> None:
    """R-IN-06: ``--dev``, ``--debug``, ``--browser``, ``--doctor`` and ``--update``."""
    options = parse_options([f"--{flag}"], {})

    assert getattr(options, flag) is True


def test_an_unknown_flag_ends_with_the_usage_exit_code() -> None:
    """R-IN-06: a typo is reported, not ignored."""
    with pytest.raises(SystemExit) as exit_info:
        parse_options(["--no-such-flag"], {})

    assert exit_info.value.code == 2


def test_dev_mode_uses_the_development_server_of_the_launcher() -> None:
    """R-IN-06: ``./start --dev`` passes the address of the development server."""
    options = parse_options(["--dev"], {"YTM_FRONTEND_URL": "http://127.0.0.1:5999/"})

    assert options.frontend_url == "http://127.0.0.1:5999/"


def test_dev_mode_without_an_address_uses_the_usual_one() -> None:
    """R-IN-06: the development server has a fixed default address."""
    assert parse_options(["--dev"], {}).frontend_url == DEFAULT_DEV_FRONTEND_URL


def test_the_development_server_address_is_ignored_outside_dev_mode() -> None:
    """R-PL-04: a stray environment variable cannot widen the accepted origins."""
    options = parse_options([], {"YTM_FRONTEND_URL": "http://127.0.0.1:5999/"})

    assert options.frontend_url is None


def test_tests_can_fix_the_port_the_token_and_run_without_a_window() -> None:
    """infra: end-to-end tests drive the real app (docs/ARCHITECTURE.md section 10)."""
    env = {"YTM_PORT": "47801", "YTM_SESSION_TOKEN": "known", "YTM_NO_WINDOW": "1"}

    options = parse_options([], env)

    assert options.port == 47801
    assert options.session_token == "known"
    assert options.no_window


@pytest.mark.parametrize("value", ["", "0"])
def test_the_window_stays_on_when_the_no_window_variable_is_off(value: str) -> None:
    """infra: only a set, non-zero value turns the window off."""
    assert not parse_options([], {"YTM_NO_WINDOW": value}).no_window


@pytest.mark.parametrize("value", ["abc", "0", "70000", "-1", "80.5"])
def test_an_invalid_port_ends_with_the_usage_exit_code(value: str) -> None:
    """infra: the app never binds to a port it did not understand."""
    with pytest.raises(SystemExit) as exit_info:
        parse_options([], {"YTM_PORT": value})

    assert exit_info.value.code == 2
