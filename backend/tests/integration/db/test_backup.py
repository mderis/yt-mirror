"""Tests of the backup of the database before migrations, with the real SQLite (R-QA-07)."""

import datetime
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import text

from tests.fixtures.fakes.clock import FakeClock
from tests.migrations.helpers import add_a_failing_migration, new_database, upgrade_to
from tests.migrations.test_no_data_lost import contents, fill, revisions
from ytmirror.adapters.db.schema import AlembicSchema
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.services.schema import KEEP_BACKUPS, SchemaService

MOMENT = datetime.datetime(2026, 11, 16, 9, 30, 5, tzinfo=datetime.UTC)


def rows_of(database: Path, table: str) -> int:
    """Count the rows of a table, reading the file with SQLite itself."""
    with sqlite3.connect(database) as connection:
        count: int = connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
    connection.close()
    return count


def test_the_copy_holds_what_is_still_in_the_write_ahead_log(tmp_path: Path) -> None:
    """R-QA-07: a backup made while another connection has rows in the WAL file has them too."""
    engine = new_database(tmp_path)
    upgrade_to(engine, revisions()[-2])
    fill(engine)
    schema = AlembicSchema(engine, tmp_path / "yt-mirror.db")
    holder = sqlite3.connect(tmp_path / "yt-mirror.db")
    try:
        holder.execute(
            "INSERT INTO app_meta (key, value, created_at, updated_at)"
            " VALUES ('only-in-the-wal', 'yes', 1, 1)"
        )
        holder.commit()
        assert (tmp_path / "yt-mirror.db-wal").stat().st_size > 0

        copy = schema.back_up(tmp_path / "backups", MOMENT, KEEP_BACKUPS)
    finally:
        holder.close()

    assert copy.name == f"yt-mirror-2026-11-16-093005-schema-{revisions()[-2]}.db"
    assert rows_of(copy, "videos") == rows_of(tmp_path / "yt-mirror.db", "videos") > 0
    with sqlite3.connect(copy) as reading:
        found = reading.execute("SELECT value FROM app_meta WHERE key = 'only-in-the-wal'")
        assert found.fetchone() == ("yes",)
    reading.close()


def test_only_the_newest_five_copies_stay_and_no_other_file_is_touched(tmp_path: Path) -> None:
    """R-QA-07: older backups go; a file of another name in the folder stays."""
    engine = new_database(tmp_path)
    upgrade_to(engine, revisions()[-1])
    schema = AlembicSchema(engine, tmp_path / "yt-mirror.db")
    folder = tmp_path / "backups"
    folder.mkdir()
    (folder / "my notes.txt").write_text("keep me")

    made = [
        schema.back_up(folder, MOMENT + datetime.timedelta(minutes=number), KEEP_BACKUPS)
        for number in range(7)
    ]
    twice = schema.back_up(folder, MOMENT + datetime.timedelta(minutes=6), KEEP_BACKUPS)

    left = sorted(path.name for path in folder.iterdir())
    assert left == sorted([*(path.name for path in made[3:]), twice.name, "my notes.txt"])
    assert twice.name.endswith("-2.db")


def test_a_copy_can_be_put_back(tmp_path: Path) -> None:
    """R-QA-07: restoring a backup gives the database as it was when it was copied."""
    engine = new_database(tmp_path)
    upgrade_to(engine, revisions()[-1])
    fill(engine)
    schema = AlembicSchema(engine, tmp_path / "yt-mirror.db")
    before = contents(engine)
    copy = schema.back_up(tmp_path / "backups", MOMENT, KEEP_BACKUPS)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM videos"))

    schema.restore(copy)

    assert contents(engine) == before


def test_a_failing_migration_keeps_the_old_database_and_its_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-QA-07, R-QA-04: the start stops with the copy named; database and copy are as before."""
    add_a_failing_migration(tmp_path, monkeypatch)
    engine = new_database(tmp_path)
    upgrade_to(engine, revisions()[-1])
    fill(engine)
    before = contents(engine)
    service = SchemaService(
        AlembicSchema(engine, tmp_path / "yt-mirror.db"), FakeClock(), tmp_path / "backups"
    )

    with pytest.raises(AppError) as failed:
        service.bring_up_to_date()

    backup = Path(failed.value.details["backup"])
    assert failed.value.code is ErrorCode.DB_UPGRADE_FAILED
    assert backup.parent == tmp_path / "backups"
    assert contents(engine) == before
    assert rows_of(backup, "videos") == before["videos"][0]
    with sqlite3.connect(backup) as connection:
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    connection.close()
    assert version == revisions()[-1]
