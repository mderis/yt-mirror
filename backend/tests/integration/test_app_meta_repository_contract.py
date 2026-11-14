"""Contract of the AppMetaRepository port, run against the fake and the real adapter."""

from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from tests.fixtures.fakes.app_meta_repository import InMemoryAppMetaRepository
from tests.fixtures.fakes.clock import FakeClock
from ytmirror.adapters.db.app_meta_repository import SqlAppMetaRepository
from ytmirror.adapters.db.engine import create_db_engine
from ytmirror.adapters.db.schema import AlembicSchema
from ytmirror.ports.app_meta_repository import AppMetaRepository


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    """A migrated database in a temp folder."""
    database_file = tmp_path / "yt-mirror.db"
    engine = create_db_engine(database_file)
    AlembicSchema(engine, database_file).upgrade()
    return engine


@pytest.fixture(params=["fake", "sql"])
def repository(
    request: pytest.FixtureRequest, engine: Engine, clock: FakeClock
) -> AppMetaRepository:
    """The fake and the real repository, one after the other."""
    if request.param == "fake":
        return InMemoryAppMetaRepository()
    return SqlAppMetaRepository(engine, clock)


def test_a_fact_that_was_never_stored_is_not_there(repository: AppMetaRepository) -> None:
    """R-IN-03: before the first setup, the app knows that setup never completed."""
    assert repository.get("setup_completed_at") is None


def test_a_stored_fact_is_read_back_and_can_be_replaced(repository: AppMetaRepository) -> None:
    """R-IN-03: the app remembers that its setup completed."""
    repository.put("setup_completed_at", "1794600000")
    first = repository.get("setup_completed_at")
    repository.put("setup_completed_at", "1794700000")

    assert first == "1794600000"
    assert repository.get("setup_completed_at") == "1794700000"
    assert repository.get("something_else") is None


def test_the_rows_record_when_a_fact_was_stored_and_changed(
    engine: Engine, clock: FakeClock
) -> None:
    """infra: every table has ``created_at`` and ``updated_at`` (ARCHITECTURE section 5)."""
    repository = SqlAppMetaRepository(engine, clock)
    created = int(clock.now().timestamp())

    repository.put("fact", "one")
    clock.advance(90)
    repository.put("fact", "one")
    with engine.connect() as connection:
        untouched = connection.execute(text("SELECT created_at, updated_at FROM app_meta")).one()
    repository.put("fact", "two")
    with engine.connect() as connection:
        changed = connection.execute(text("SELECT created_at, updated_at FROM app_meta")).one()

    assert tuple(untouched) == (created, created)
    assert tuple(changed) == (created, created + 90)
