"""Fixtures shared by all backend tests."""

import logging
from collections.abc import Iterator

import pytest
import structlog

from tests.fixtures.fakes.clock import FakeClock

INFRA_MARKER = "infra:"


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
