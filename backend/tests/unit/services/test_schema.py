"""Tests of ``ytmirror.services.schema``."""

from pathlib import Path

import pytest
from structlog.testing import capture_logs

from tests.fixtures.fakes.clock import FakeClock
from tests.fixtures.fakes.database_schema import FakeDatabaseSchema
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.services.schema import KEEP_BACKUPS, SchemaService

BACKUPS = Path("/data/backups")


class _SlowSchema(FakeDatabaseSchema):
    """A schema whose upgrade takes a known time on the fake clock."""

    def __init__(self, clock: FakeClock) -> None:
        super().__init__(latest="0002", current="0001")
        self._clock = clock

    def upgrade(self) -> None:
        self._clock.advance(1.25)
        super().upgrade()


def test_a_new_database_is_migrated_to_the_latest_version(clock: FakeClock) -> None:
    """R-QA-07: the first start creates the schema through the migrations."""
    schema = FakeDatabaseSchema(latest="0002", current=None)

    version = SchemaService(schema, clock, BACKUPS).bring_up_to_date()

    assert version == "0002"
    assert schema.upgrades == 1


def test_an_up_to_date_database_is_left_alone_and_nothing_is_logged(clock: FakeClock) -> None:
    """R-QA-07: no migration runs when the schema is already current."""
    schema = FakeDatabaseSchema(latest="0002", current="0002")

    with capture_logs() as logs:
        version = SchemaService(schema, clock, BACKUPS).bring_up_to_date()

    assert version == "0002"
    assert schema.upgrades == 0
    assert logs == []


def test_a_migration_is_logged_at_start_and_end_with_its_duration(clock: FakeClock) -> None:
    """R-LG-06: ``db.migration.started`` and ``db.migration.finished`` frame the upgrade."""
    schema = _SlowSchema(clock)

    with capture_logs() as logs:
        SchemaService(schema, clock, BACKUPS).bring_up_to_date()

    assert [line["event"] for line in logs] == [
        "db.backup",
        "db.migration.started",
        "db.migration.finished",
    ]
    assert logs[1]["from_version"] == "0001"
    assert logs[1]["to_version"] == "0002"
    assert logs[2]["duration_ms"] == 1250
    assert all(line["msg"] for line in logs)


def test_an_existing_database_is_copied_before_its_migrations(clock: FakeClock) -> None:
    """R-QA-07: a copy named with the date and the version, five of them kept, comes first."""
    schema = FakeDatabaseSchema(latest="0002", current="0001")

    with capture_logs() as logs:
        SchemaService(schema, clock, BACKUPS).bring_up_to_date()

    copy, version = schema.backups[0]
    assert version == "0001"
    assert copy.parent == BACKUPS
    assert copy.name == f"yt-mirror-{clock.now():%Y-%m-%d-%H%M%S}-schema-0001.db"
    assert logs[0]["file"] == str(copy)
    assert KEEP_BACKUPS == 5


def test_a_new_or_current_database_is_not_copied(clock: FakeClock) -> None:
    """R-QA-07: there is nothing to keep before the first migration, nor without one."""
    new = FakeDatabaseSchema(latest="0002", current=None)
    current = FakeDatabaseSchema(latest="0002", current="0002")

    SchemaService(new, clock, BACKUPS).bring_up_to_date()
    SchemaService(current, clock, BACKUPS).bring_up_to_date()

    assert (new.backups, current.backups) == ([], [])


def test_a_failed_migration_stops_the_start_and_names_the_copy(clock: FakeClock) -> None:
    """R-QA-07: the database stays as it was, the error names the backup, and it is logged."""
    schema = FakeDatabaseSchema(latest="0002", current="0001")
    schema.fail = RuntimeError("a migration failed")

    with capture_logs() as logs, pytest.raises(AppError) as failed:
        SchemaService(schema, clock, BACKUPS).bring_up_to_date()

    copy = schema.backups[0][0]
    assert failed.value.code is ErrorCode.DB_UPGRADE_FAILED
    assert failed.value.details == {
        "backup": str(copy),
        "from_version": "0001",
        "to_version": "0002",
    }
    assert schema.current_version() == "0001"
    assert schema.restored == []
    line = next(line for line in logs if line["event"] == "db.migration.failed")
    assert (line["error_code"], line["backup"], line["restored"]) == (
        "DB_UPGRADE_FAILED",
        str(copy),
        False,
    )


def test_a_database_left_half_updated_is_put_back_from_the_copy(clock: FakeClock) -> None:
    """R-QA-07: should a failed migration leave a changed database, the copy replaces it."""
    schema = FakeDatabaseSchema(latest="0002", current="0001")
    schema.fail = RuntimeError("a migration failed")
    schema.half_done = True

    with pytest.raises(AppError):
        SchemaService(schema, clock, BACKUPS).bring_up_to_date()

    assert schema.restored == [schema.backups[0][0]]
    assert schema.current_version() == "0001"


def test_a_failed_first_migration_has_no_copy_to_name(clock: FakeClock) -> None:
    """R-QA-07: a database that did not exist yet has no backup."""
    schema = FakeDatabaseSchema(latest="0002", current=None)
    schema.fail = RuntimeError("a migration failed")

    with pytest.raises(AppError) as failed:
        SchemaService(schema, clock, BACKUPS).bring_up_to_date()

    assert failed.value.details["backup"] == ""
