"""Tests of ``ytmirror.services.schema``."""

from structlog.testing import capture_logs

from tests.fixtures.fakes.clock import FakeClock
from tests.fixtures.fakes.database_schema import FakeDatabaseSchema
from ytmirror.services.schema import SchemaService


class _SlowSchema(FakeDatabaseSchema):
    """A schema whose upgrade takes a known time on the fake clock."""

    def __init__(self, clock: FakeClock) -> None:
        super().__init__(latest="0002", current="0001")
        self._clock = clock

    def upgrade(self) -> None:
        self._clock.advance(1.25)
        super().upgrade()


def test_a_new_database_is_migrated_to_the_latest_version(clock: FakeClock) -> None:
    """R-QA-04: the first start creates the schema through the migrations."""
    schema = FakeDatabaseSchema(latest="0002", current=None)

    version = SchemaService(schema, clock).bring_up_to_date()

    assert version == "0002"
    assert schema.upgrades == 1


def test_an_up_to_date_database_is_left_alone_and_nothing_is_logged(clock: FakeClock) -> None:
    """R-QA-04: no migration runs when the schema is already current."""
    schema = FakeDatabaseSchema(latest="0002", current="0002")

    with capture_logs() as logs:
        version = SchemaService(schema, clock).bring_up_to_date()

    assert version == "0002"
    assert schema.upgrades == 0
    assert logs == []


def test_a_migration_is_logged_at_start_and_end_with_its_duration(clock: FakeClock) -> None:
    """R-LG-01: ``db.migration.started`` and ``db.migration.finished`` frame the upgrade."""
    schema = _SlowSchema(clock)

    with capture_logs() as logs:
        SchemaService(schema, clock).bring_up_to_date()

    assert [line["event"] for line in logs] == ["db.migration.started", "db.migration.finished"]
    assert logs[0]["from_version"] == "0001"
    assert logs[0]["to_version"] == "0002"
    assert logs[1]["duration_ms"] == 1250
    assert all(line["msg"] for line in logs)
