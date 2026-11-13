"""Contract of the DatabaseSchema port, run against the fake and the real adapter."""

from pathlib import Path

import pytest

from tests.fixtures.fakes.database_schema import FakeDatabaseSchema
from ytmirror.adapters.db.engine import create_db_engine
from ytmirror.adapters.db.schema import AlembicSchema
from ytmirror.ports.database_schema import DatabaseSchema

LATEST = "0002"


@pytest.fixture(params=["fake", "alembic"])
def schema(request: pytest.FixtureRequest, tmp_path: Path) -> DatabaseSchema:
    """The fake and the real schema of a database that does not exist yet."""
    if request.param == "fake":
        return FakeDatabaseSchema(latest=LATEST, current=None)
    database_file = tmp_path / "data" / "yt-mirror.db"
    return AlembicSchema(create_db_engine(database_file), database_file)


def test_before_the_first_upgrade_there_is_no_database_and_no_version(
    schema: DatabaseSchema,
) -> None:
    """R-QA-07: looking at a missing database does not create it."""
    assert not schema.exists()
    assert schema.current_version() is None
    assert schema.is_intact()
    assert not schema.exists()


def test_the_latest_version_is_the_newest_migration(schema: DatabaseSchema) -> None:
    """R-QA-07: the app knows which schema version it expects."""
    assert schema.latest_version() == LATEST


def test_upgrade_creates_the_database_at_the_latest_version(schema: DatabaseSchema) -> None:
    """R-QA-07: every database change is a migration, including the first."""
    schema.upgrade()

    assert schema.exists()
    assert schema.current_version() == schema.latest_version()
    assert schema.is_intact()


def test_upgrading_twice_changes_nothing(schema: DatabaseSchema) -> None:
    """R-QA-07: an upgrade of a current database is harmless."""
    schema.upgrade()

    schema.upgrade()

    assert schema.current_version() == LATEST


def test_a_file_that_is_not_a_database_fails_the_integrity_check(tmp_path: Path) -> None:
    """R-LG-05: a damaged database is noticed."""
    database_file = tmp_path / "yt-mirror.db"
    schema = AlembicSchema(create_db_engine(database_file), database_file)
    schema.upgrade()
    damaged = bytearray(database_file.read_bytes())
    damaged[100:400] = b"\xff" * 300
    database_file.write_bytes(bytes(damaged))
    for leftover in tmp_path.glob("yt-mirror.db-*"):
        leftover.unlink()

    fresh = AlembicSchema(create_db_engine(database_file), database_file)

    assert not fresh.is_intact()
