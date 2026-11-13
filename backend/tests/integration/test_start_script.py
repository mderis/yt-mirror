"""Tests of the ``start`` launcher script, run on a throwaway copy.

The copy lives in a temp folder, so these tests never touch the real
``tools/`` folder and never reach the network: the uv download is pointed at
local files.
"""

import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
START = REPO_ROOT / "start"
SYSTEM_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"


def pinned_uv_version() -> str:
    """Return the uv version the launcher pins."""
    match = re.search(r'^UV_VERSION="([^"]+)"$', START.read_text(encoding="utf-8"), re.MULTILINE)
    assert match is not None
    return match.group(1)


@pytest.fixture
def clone(tmp_path: Path) -> Path:
    """A folder that looks like a fresh clone: the launcher and interface sources, no tools."""
    root = tmp_path / "clone"
    (root / "frontend" / "src").mkdir(parents=True)
    shutil.copy(START, root / "start")
    return root


def run_start(
    clone: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the copied launcher with a minimal environment."""
    full_env = {"PATH": SYSTEM_PATH, "HOME": str(clone.parent)}
    full_env.update(env or {})
    return subprocess.run(
        ["/bin/sh", str(clone / "start"), *args],
        capture_output=True,
        text=True,
        env=full_env,
        timeout=60,
        check=False,
    )


def install_fake_uv(clone: Path) -> Path:
    """Put a stand-in for uv into ``tools/`` that reports the pinned version and syncs nothing."""
    uv = clone / "tools" / "uv" / "uv"
    uv.parent.mkdir(parents=True)
    uv.write_text(
        "#!/bin/sh\n"
        f'if [ "$1" = "--version" ]; then echo "uv {pinned_uv_version()} (test)"; exit 0; fi\n'
        f'echo "$@" >> "{clone}/uv-calls.txt"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    uv.chmod(0o755)
    return uv


def test_help_explains_every_flag_and_needs_nothing_installed(clone: Path) -> None:
    """R-IN-02: ``./start --help`` lists the flags of the implementation plan."""
    result = run_start(clone, "--help")

    assert result.returncode == 0
    for flag in ("--dev", "--debug", "--browser", "--doctor", "--update"):
        assert flag in result.stdout
    assert not (clone / "tools").exists()


def test_an_unknown_flag_stops_before_anything_is_downloaded(clone: Path) -> None:
    """R-IN-02: a typo costs nothing and shows the usage."""
    result = run_start(clone, "--no-such-flag")

    assert result.returncode == 2
    assert "Unknown option: --no-such-flag" in result.stderr
    assert "Usage: ./start" in result.stderr
    assert not (clone / "tools").exists()


def test_another_operating_system_is_refused_with_a_clear_message(
    clone: Path, tmp_path: Path
) -> None:
    """R-PL-01: yt-mirror runs on macOS only, and says so."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "uname").write_text("#!/bin/sh\necho Linux\n", encoding="utf-8")
    (fake_bin / "uname").chmod(0o755)

    result = run_start(clone, env={"PATH": f"{fake_bin}:{SYSTEM_PATH}"})

    assert result.returncode == 1
    assert "yt-mirror runs on macOS only." in result.stderr
    assert not (clone / "tools").exists()


def test_an_unknown_processor_is_refused(clone: Path, tmp_path: Path) -> None:
    """R-PL-01: Apple Silicon and Intel only."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "uname").write_text(
        '#!/bin/sh\nif [ "$1" = "-s" ]; then echo Darwin; else echo riscv64; fi\n',
        encoding="utf-8",
    )
    (fake_bin / "uname").chmod(0o755)

    result = run_start(clone, env={"PATH": f"{fake_bin}:{SYSTEM_PATH}"})

    assert result.returncode == 1
    assert "this processor (riscv64) is not supported" in result.stderr


def test_a_download_that_fails_its_checksum_is_never_used(clone: Path, tmp_path: Path) -> None:
    """R-IN-02: uv is verified against its SHA-256 before use (ARCHITECTURE section 9)."""
    downloads = tmp_path / "downloads" / pinned_uv_version()
    downloads.mkdir(parents=True)
    for name in ("uv-aarch64-apple-darwin", "uv-x86_64-apple-darwin"):
        payload = tmp_path / name
        payload.mkdir()
        (payload / "uv").write_text("#!/bin/sh\necho tampered\n", encoding="utf-8")
        (payload / "uvx").write_text("#!/bin/sh\n", encoding="utf-8")
        with tarfile.open(downloads / f"{name}.tar.gz", "w:gz") as archive:
            archive.add(payload, arcname=name)

    result = run_start(clone, env={"YTM_UV_BASE_URL": f"file://{downloads.parent}"})

    assert result.returncode == 1
    assert "does not match its checksum, so it was not used" in result.stderr
    assert not (clone / "tools" / "uv").exists()
    assert not (clone / "tools" / ".uv-download").exists()
    assert not (clone / "tools" / "venv").exists()


def test_a_failed_download_is_explained(clone: Path, tmp_path: Path) -> None:
    """R-IN-02: without a connection the launcher says what to do, in plain words."""
    result = run_start(clone, env={"YTM_UV_BASE_URL": f"file://{tmp_path}/nothing-here"})

    assert result.returncode == 1
    assert "uv could not be downloaded" in result.stderr
    assert not (clone / "tools" / "uv").exists()


def test_a_present_uv_of_the_pinned_version_is_not_downloaded_again(
    clone: Path, tmp_path: Path
) -> None:
    """R-IN-02: a second start does not need the network for uv."""
    install_fake_uv(clone)

    result = run_start(clone, env={"YTM_UV_BASE_URL": f"file://{tmp_path}/nothing-here"})

    assert "Downloading uv" not in result.stderr
    calls = (clone / "uv-calls.txt").read_text(encoding="utf-8")
    assert calls.startswith("sync --project ")
    assert "--frozen" in calls


def test_python_and_packages_go_into_the_tools_folder(clone: Path) -> None:
    """R-IN-02: nothing is installed outside the app folder (docs/DECISIONS.md D-018)."""
    uv = install_fake_uv(clone)
    script = uv.read_text(encoding="utf-8")
    record_env = f'env | grep "^UV_" | sort > "{clone}/uv-env.txt"; echo "$@" >>'
    uv.write_text(script.replace('echo "$@" >>', record_env), encoding="utf-8")

    run_start(clone)

    env_lines = (clone / "uv-env.txt").read_text(encoding="utf-8").splitlines()
    tools = os.path.realpath(clone / "tools")
    assert f"UV_PYTHON_INSTALL_DIR={tools}/python" in env_lines
    assert f"UV_PROJECT_ENVIRONMENT={tools}/venv" in env_lines
    assert f"UV_CACHE_DIR={tools}/uv-cache" in env_lines
    assert "UV_PYTHON_PREFERENCE=only-managed" in env_lines


def test_without_node_a_clone_gets_a_clear_message_instead_of_a_crash(clone: Path) -> None:
    """R-IN-02: building the interface in a clone needs Node.js (docs/DECISIONS.md D-037)."""
    install_fake_uv(clone)

    result = run_start(clone)

    assert result.returncode == 1
    assert "Node.js is needed to build the interface" in result.stderr
    assert "https://nodejs.org" in result.stderr


def test_an_installation_without_interface_sources_and_without_a_build_says_so(
    clone: Path,
) -> None:
    """R-IN-02: a damaged archive install is reported, not silently rebuilt."""
    install_fake_uv(clone)
    shutil.rmtree(clone / "frontend" / "src")

    result = run_start(clone)

    assert result.returncode == 1
    assert "the built interface is missing from this installation" in result.stderr


def test_doctor_does_not_build_the_interface(clone: Path) -> None:
    """R-IN-02: ``./start --doctor`` only looks. It needs no Node.js."""
    install_fake_uv(clone)

    result = run_start(clone, "--doctor")

    assert "Node.js is needed" not in result.stderr
    assert "Building the interface" not in result.stderr


def test_ci_uses_the_same_uv_version_as_the_launcher() -> None:
    """infra: the automated checks run with the uv version a clone gets."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    match = re.search(r'^  UV_VERSION: "([^"]+)"$', workflow, re.MULTILINE)

    assert match is not None
    assert match.group(1) == pinned_uv_version()
