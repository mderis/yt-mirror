"""Fixtures shared by all backend tests."""

import logging
from collections.abc import Iterator

import pytest
import structlog

from tests.fixtures.fakes.clock import FakeClock


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
