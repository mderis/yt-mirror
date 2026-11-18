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
from ytmirror.core.channels import Quality
from ytmirror.core.models import LogDetail, Settings, ViewKind
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
            text("SELECT key, value, created_at, updated_at FROM settings WHERE key = 'log_detail'")
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
        updated = connection.execute(text("SELECT updated_at FROM settings")).scalars().all()
    assert set(updated) == {first}


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


def test_the_library_folder_is_stored_and_has_its_default(
    repository: SettingsRepository,
) -> None:
    """R-SE-04, R-FI-01: the library folder defaults to ~/Movies/YouTube and can be stored."""
    assert repository.load().library_folder == "~/Movies/YouTube"

    repository.save(Settings(library_folder="/Volumes/Media/YouTube"))

    assert repository.load().library_folder == "/Volumes/Media/YouTube"


def test_an_unreadable_library_folder_falls_back_to_the_default(
    engine: Engine, clock: FakeClock
) -> None:
    """R-SE-04: a stored value that cannot be read has its default."""
    SqlSettingsRepository(engine, clock).save(Settings())
    with engine.begin() as connection:
        connection.execute(text("UPDATE settings SET value = '12' WHERE key = 'library_folder'"))

    assert SqlSettingsRepository(engine, clock).load().library_folder == "~/Movies/YouTube"


def test_the_settings_of_downloads_have_the_defaults_of_the_spec(
    repository: SettingsRepository,
) -> None:
    """R-SE-04, R-QL-02, R-MD-03, R-MD-05: Best available, both subtitles on, no visible cover."""
    settings = repository.load()

    assert settings.default_quality is Quality.BEST
    assert (settings.embed_subtitles, settings.auto_subtitles) == (True, True)
    assert settings.thumbnail_next_to_video is False


def test_the_settings_of_downloads_are_stored(repository: SettingsRepository) -> None:
    """R-SE-03, R-QL-02, R-MD-03, R-MD-05: each setting of downloads comes back as saved."""
    chosen = Settings(
        default_quality=Quality.P720,
        embed_subtitles=False,
        auto_subtitles=False,
        thumbnail_next_to_video=True,
    )

    repository.save(chosen)

    assert repository.load() == chosen


@pytest.mark.parametrize(
    ("key", "value"),
    [("default_quality", '"4320"'), ("embed_subtitles", '"yes"'), ("thumbnail_next_to_video", "1")],
)
def test_an_unreadable_setting_of_downloads_has_its_default(
    engine: Engine, clock: FakeClock, key: str, value: str
) -> None:
    """R-SE-04: a stored value that cannot be read has its default."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO settings (key, value, created_at, updated_at)"
                " VALUES (:key, :value, 0, 0)"
            ),
            {"key": key, "value": value},
        )

    assert SqlSettingsRepository(engine, clock).load() == Settings()


def test_the_settings_of_checks_and_dates_have_their_defaults(
    repository: SettingsRepository,
) -> None:
    """R-SE-04, R-CH-20, R-CH-22, R-CH-26, R-DT-05, R-DT-09: the defaults of section 10."""
    settings = repository.load()

    assert settings.check_on_open is True
    assert settings.recheck_interval_min == 30
    assert settings.full_check_days == 7
    assert settings.fetch_exact_dates is True
    assert settings.repair_dates is True


def test_the_settings_of_checks_and_dates_are_stored(repository: SettingsRepository) -> None:
    """R-SE-03: every M4 setting comes back as it was saved."""
    chosen = Settings(
        check_on_open=False,
        recheck_interval_min=0,
        full_check_days=30,
        fetch_exact_dates=False,
        repair_dates=False,
    )

    repository.save(chosen)

    assert repository.load() == chosen


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("recheck_interval_min", "45"),
        ("recheck_interval_min", "true"),
        ("full_check_days", "0"),
        ("full_check_days", '"7"'),
        ("check_on_open", "1"),
        ("parallel_downloads", "0"),
        ("parallel_downloads", "6"),
        ("speed_limit_mbps", "3"),
        ("disk_guard_gb", "-1"),
        ("downloads_paused", "0"),
        ("default_view", '"table"'),
        ("default_view", "1"),
    ],
)
def test_a_value_that_is_not_one_of_the_choices_has_the_default(
    engine: Engine, clock: FakeClock, key: str, value: str
) -> None:
    """R-SE-04: a stored value that is not allowed cannot break loading."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO settings (key, value, created_at, updated_at)"
                " VALUES (:key, :value, 0, 0)"
            ),
            {"key": key, "value": value},
        )

    assert SqlSettingsRepository(engine, clock).load() == Settings()


def test_the_settings_of_the_queue_have_the_defaults_of_the_spec(
    repository: SettingsRepository,
) -> None:
    """R-SE-04, R-QU-01, R-QU-03, R-QU-10, R-QU-02, R-UI-03: the defaults of section 10."""
    settings = repository.load()

    assert settings.parallel_downloads == 2
    assert settings.speed_limit_mbps == 0
    assert settings.disk_guard_gb == 10
    assert settings.downloads_paused is False
    assert settings.default_view is ViewKind.LIST


def test_the_settings_of_the_queue_are_stored(repository: SettingsRepository) -> None:
    """R-SE-03, R-QU-01, R-QU-03, R-QU-10, R-QU-02, R-UI-03: each comes back as it was saved."""
    chosen = Settings(
        parallel_downloads=5,
        speed_limit_mbps=1,
        disk_guard_gb=25,
        downloads_paused=True,
        default_view=ViewKind.GRID,
    )

    repository.save(chosen)

    assert repository.load() == chosen
