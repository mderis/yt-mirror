"""Fixtures shared by all backend tests, and the guard of the real tools folder."""

import logging
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog
from hypothesis import settings

from tests.fixtures.fakes.clock import FakeClock

INFRA_MARKER = "infra:"

# Property tests draw the same examples on every run and keep no database of
# examples on disk, so that a run never depends on an earlier one (TESTING rules 4 and 6).
settings.register_profile("yt-mirror", derandomize=True, database=None, deadline=None)
settings.load_profile("yt-mirror")

REAL_TOOLS = Path(__file__).resolve().parents[2] / "tools"
"""The tools of the app folder these tests run from. No test may change them (TESTING rule 9)."""
_TOOLS_BEFORE = pytest.StashKey[list[tuple[str, int, int]]]()


def real_tools_state(tools_dir: Path = REAL_TOOLS) -> list[tuple[str, int, int]]:
    """Return every file of the downloaded tools with its size and its time of change."""
    files = [
        path
        for tool in ("ffmpeg", "deno")
        if (tools_dir / tool).is_dir()
        for path in (tools_dir / tool).iterdir()
    ]
    return sorted(
        (str(path.relative_to(tools_dir)), path.stat().st_size, path.stat().st_mtime_ns)
        for path in files
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    """Remember the tools of the app folder before any test runs."""
    session.config.stash[_TOOLS_BEFORE] = real_tools_state()


def pytest_sessionfinish(session: pytest.Session) -> None:
    """Fail the run when a test added, removed or rewrote a tool of the app folder."""
    before = session.config.stash.get(_TOOLS_BEFORE, None)
    if before is not None and real_tools_state() != before:
        sys.stderr.write(
            f"\nThe tools in {REAL_TOOLS} changed during the tests. No test may touch them.\n"
        )
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Give every test whose docstring starts with ``infra:`` the pytest marker ``infra``.

    The docstring is the one place where a test says what it covers
    (docs/TESTING.md rule 1). This hook only makes that selectable.
    """
    for item in items:
        function: object = getattr(item, "function", None)
        docstring = getattr(function, "__doc__", None) or ""
        if docstring.lstrip().startswith(INFRA_MARKER):
            item.add_marker(pytest.mark.infra)


@pytest.fixture(autouse=True)
def reset_logging() -> Iterator[None]:
    """Give every test the default log setup, whatever the test before it configured."""
    yield
    structlog.reset_defaults()
    root = logging.getLogger()
    root.handlers = []
    root.setLevel(logging.WARNING)


@pytest.fixture
def clock() -> FakeClock:
    """A clock that stands still at a known moment."""
    return FakeClock()
