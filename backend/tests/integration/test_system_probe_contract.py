"""Contract of the SystemProbe port, run against the fake and the real adapter."""

import sys
from pathlib import Path

import pytest

from tests.fixtures.fakes.system_probe import FakeSystemProbe
from ytmirror.adapters.system_probe import MacSystemProbe
from ytmirror.ports.system_probe import SystemProbe


@pytest.fixture
def existing_file(tmp_path: Path) -> Path:
    """A file that exists."""
    path = tmp_path / "present.txt"
    path.write_text("x", encoding="utf-8")
    return path


@pytest.fixture(params=["fake", "mac"])
def probe(request: pytest.FixtureRequest, existing_file: Path) -> SystemProbe:
    """The fake, told about this test's world, and the real probe."""
    if request.param == "fake":
        return FakeSystemProbe(
            commands={sys.executable: "Python 3.14.10"},
            modules={"json"},
            files={existing_file},
        )
    return MacSystemProbe()


def test_versions_and_architecture_are_plain_text(probe: SystemProbe) -> None:
    """R-LG-05: the report can show macOS version, processor and Python."""
    assert probe.os_version().split(".")[0].isdigit()
    assert probe.cpu_architecture() in ("arm64", "x86_64")
    assert probe.python_version().startswith("3.")


def test_a_program_that_runs_reports_its_version_line(probe: SystemProbe) -> None:
    """R-LG-05: a present tool is shown with its version."""
    version = probe.command_version(sys.executable)

    assert version is not None
    assert version.startswith("Python 3.")


def test_a_program_that_does_not_exist_has_no_version(probe: SystemProbe) -> None:
    """R-LG-05: a missing tool is reported as missing, not as an error."""
    assert probe.command_version("no-such-program-for-yt-mirror") is None


def test_modules_are_found_or_not(probe: SystemProbe) -> None:
    """R-LG-05: the report can tell whether a Python package is installed."""
    assert probe.module_available("json")
    assert not probe.module_available("no_such_module_for_yt_mirror")


def test_files_are_found_or_not(probe: SystemProbe, existing_file: Path) -> None:
    """R-LG-05: the report can tell whether the built interface exists."""
    assert probe.file_exists(existing_file)
    assert not probe.file_exists(existing_file.with_name("absent.txt"))


def test_a_folder_that_does_not_exist_yet_is_judged_by_its_parent(
    probe: SystemProbe, tmp_path: Path
) -> None:
    """R-LG-05: before the first start the data folder does not exist, and that is fine."""
    future_folder = tmp_path / "data" / "logs"

    assert probe.can_write_to(future_folder)
    assert probe.free_bytes(future_folder) > 0


def test_a_program_that_fails_has_no_version(tmp_path: Path) -> None:
    """R-LG-05: a broken tool counts as missing."""
    broken = tmp_path / "broken-tool"
    broken.write_text("#!/bin/sh\nexit 3\n", encoding="utf-8")
    broken.chmod(0o755)

    assert MacSystemProbe().command_version(str(broken)) is None


def test_a_file_that_cannot_be_executed_has_no_version(tmp_path: Path) -> None:
    """R-LG-05: a file that is not a program counts as missing."""
    not_a_program = tmp_path / "data.bin"
    not_a_program.write_bytes(b"\x00\x01")
    not_a_program.chmod(0o755)

    assert MacSystemProbe().command_version(str(not_a_program)) is None


def test_the_version_is_read_from_stderr_when_stdout_is_empty(tmp_path: Path) -> None:
    """R-LG-05: some tools print their version to the error stream."""
    tool = tmp_path / "tool"
    tool.write_text("#!/bin/sh\necho 'tool 1.0' >&2\n", encoding="utf-8")
    tool.chmod(0o755)

    assert MacSystemProbe().command_version(str(tool)) == "tool 1.0"


def test_a_read_only_folder_is_not_writable(tmp_path: Path) -> None:
    """R-LG-05: a data folder the app cannot write to is noticed."""
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)

    try:
        assert not MacSystemProbe().can_write_to(locked / "data")
    finally:
        locked.chmod(0o700)
