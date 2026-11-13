"""Tests of ``ytmirror.adapters.db.engine``."""

from pathlib import Path

from sqlalchemy import text

from ytmirror.adapters.db.engine import create_db_engine


def test_creating_the_engine_touches_nothing_on_disk(tmp_path: Path) -> None:
    """R-IN-02: ``--doctor`` and the schema export build the app without creating a database."""
    database_file = tmp_path / "data" / "yt-mirror.db"

    create_db_engine(database_file)

    assert not (tmp_path / "data").exists()


def test_the_first_connection_creates_the_folder_and_the_file(tmp_path: Path) -> None:
    """R-IN-02: a fresh clone has no ``data/`` folder. The first start creates it."""
    database_file = tmp_path / "data" / "nested" / "yt-mirror.db"
    engine = create_db_engine(database_file)

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    assert database_file.is_file()


def test_connections_use_wal_mode_and_enforce_foreign_keys(tmp_path: Path) -> None:
    """R-QA-06: WAL mode keeps the database consistent through a crash (D-005)."""
    engine = create_db_engine(tmp_path / "yt-mirror.db")

    with engine.connect() as connection:
        journal_mode = connection.execute(text("PRAGMA journal_mode")).scalar_one()
        foreign_keys = connection.execute(text("PRAGMA foreign_keys")).scalar_one()
        busy_timeout = connection.execute(text("PRAGMA busy_timeout")).scalar_one()

    assert journal_mode == "wal"
    assert foreign_keys == 1
    assert busy_timeout == 5000
