"""Contract of the SettingsRepository port, run against the fake and the real adapter."""

import json
from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from tests.fixtures.fakes.clock import FakeClock
from tests.fixtures.fakes.settings_repository import InMemorySettingsRepository
from ytmirror.adapters.db.engine import create_db_engine
from ytmirror.adapters.db.schema import AlembicSchema
from ytmirror.adapters.db.settings_repository import SqlSettingsRepository
from ytmirror.core.models import LogDetail, Settings
from ytmirror.ports.settings_repository import SettingsRepository


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
) -> SettingsRepository:
    """The fake and the real repository, one after the other."""
    if request.param == "fake":
        return InMemorySettingsRepository()
    return SqlSettingsRepository(engine, clock)


def test_nothing_stored_gives_the_defaults(repository: SettingsRepository) -> None:
    """R-SE-04: a setting that was never stored has its default."""
    assert repository.load() == Settings()


def test_saved_settings_are_loaded_again(repository: SettingsRepository) -> None:
    """R-SE-03: settings are stored and come back unchanged."""
    repository.save(Settings(log_detail=LogDetail.VERBOSE))

    assert repository.load() == Settings(log_detail=LogDetail.VERBOSE)


def test_saving_again_replaces_the_earlier_value(repository: SettingsRepository) -> None:
    """R-SE-03: the latest saved value wins."""
    repository.save(Settings(log_detail=LogDetail.VERBOSE))
    repository.save(Settings(log_detail=LogDetail.NORMAL))

    assert repository.load().log_detail is LogDetail.NORMAL


def test_settings_survive_a_new_connection(engine: Engine, clock: FakeClock) -> None:
    """R-SE-03: settings are stored in the database, not in memory."""
    SqlSettingsRepository(engine, clock).save(Settings(log_detail=LogDetail.VERBOSE))
    engine.dispose()

    loaded = SqlSettingsRepository(engine, clock).load()

    assert loaded.log_detail is LogDetail.VERBOSE


def test_rows_hold_json_values_and_utc_second_timestamps(engine: Engine, clock: FakeClock) -> None:
    """R-SE-03, R-DT-02: one row per setting, the value as JSON, times as UTC seconds."""
    repository = SqlSettingsRepository(engine, clock)
    created = int(clock.now().timestamp())

    repository.save(Settings(log_detail=LogDetail.NORMAL))
    clock.advance(60)
    repository.save(Settings(log_detail=LogDetail.VERBOSE))

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT key, value, created_at, updated_at FROM settings")
        ).all()
    assert len(rows) == 1
    key, value, created_at, updated_at = rows[0]
    assert key == "log_detail"
    assert json.loads(value) == "verbose"
    assert created_at == created
    assert updated_at == created + 60


def test_saving_an_unchanged_value_keeps_its_updated_time(engine: Engine, clock: FakeClock) -> None:
    """R-SE-03: ``updated_at`` tells when a setting last changed, not when it was last saved."""
    repository = SqlSettingsRepository(engine, clock)
    repository.save(Settings())
    first = int(clock.now().timestamp())

    clock.advance(60)
    repository.save(Settings())

    with engine.connect() as connection:
        updated_at = connection.execute(text("SELECT updated_at FROM settings")).scalar_one()
    assert updated_at == first


def test_a_stored_value_of_the_wrong_type_falls_back_to_the_default(
    engine: Engine, clock: FakeClock
) -> None:
    """R-SE-04: a row that is not a text value cannot break loading."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO settings (key, value, created_at, updated_at)"
                " VALUES ('log_detail', '42', 0, 0)"
            )
        )

    assert SqlSettingsRepository(engine, clock).load() == Settings()


def test_keys_the_app_does_not_know_are_ignored(engine: Engine, clock: FakeClock) -> None:
    """R-SE-04: a row left by another version does not break loading."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO settings (key, value, created_at, updated_at)"
                " VALUES ('from_the_future', '\"x\"', 0, 0)"
            )
        )

    assert SqlSettingsRepository(engine, clock).load() == Settings()
