"""Tests of ``ytmirror.adapters.db.engine``."""

from pathlib import Path

import pytest
from sqlalchemy import text

from ytmirror.adapters.db.engine import create_db_engine


def test_creating_the_engine_touches_nothing_on_disk(tmp_path: Path) -> None:
    """R-QA-07: ``--doctor`` and the schema export build the app without creating a database."""
    database_file = tmp_path / "data" / "yt-mirror.db"

    create_db_engine(database_file)

    assert not (tmp_path / "data").exists()


def test_the_first_connection_creates_the_folder_and_the_file(tmp_path: Path) -> None:
    """R-QA-07: a fresh clone has no ``data/`` folder. The first start creates it."""
    database_file = tmp_path / "data" / "nested" / "yt-mirror.db"
    engine = create_db_engine(database_file)

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    assert database_file.is_file()


def test_connections_use_wal_mode_and_enforce_foreign_keys(tmp_path: Path) -> None:
    """R-QA-07: WAL mode keeps the database consistent through a crash (D-005)."""
    engine = create_db_engine(tmp_path / "yt-mirror.db")

    with engine.connect() as connection:
        journal_mode = connection.execute(text("PRAGMA journal_mode")).scalar_one()
        foreign_keys = connection.execute(text("PRAGMA foreign_keys")).scalar_one()
        busy_timeout = connection.execute(text("PRAGMA busy_timeout")).scalar_one()

    assert journal_mode == "wal"
    assert foreign_keys == 1
    assert busy_timeout == 5000


def test_a_transaction_that_fails_undoes_changes_of_tables_too(tmp_path: Path) -> None:
    """R-QA-04, R-QA-06: a migration that fails half way leaves no new column behind."""
    engine = create_db_engine(tmp_path / "yt-mirror.db")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE things (id INTEGER PRIMARY KEY)"))

    with pytest.raises(RuntimeError), engine.begin() as connection:
        connection.execute(text("ALTER TABLE things ADD COLUMN half_done TEXT"))
        connection.execute(text("CREATE TABLE other (id INTEGER PRIMARY KEY)"))
        raise RuntimeError("failed half way")

    with engine.connect() as connection:
        columns = [row[1] for row in connection.execute(text("PRAGMA table_info(things)"))]
        tables = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        assert columns == ["id"]
        assert [row[0] for row in tables] == ["things"]
