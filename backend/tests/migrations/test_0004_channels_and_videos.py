"""Tests of migration 0004, which creates the channels and videos tables."""

from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from tests.migrations.helpers import new_database, table_names, upgrade_to

CHANNEL = (
    "INSERT INTO channels (id, url, title, folder, folder_is_custom, auto_mirror, paused,"
    " position, created_at, updated_at)"
    " VALUES ('UCa', 'u', 'A channel', 'A channel', 0, 0, 0, 0, 1, 1)"
)
VIDEO = (
    "INSERT INTO videos (id, channel_id, title, published_exact, channel_position, status,"
    " excluded, exclude_exception, missing_checks, gone, first_seen_at, last_seen_at,"
    " seen_in_first_listing, attempts, created_at, updated_at)"
    " VALUES (:id, :channel, 'A video', 0, 0, 'not_downloaded', 0, 0, 0, 0, 1, 1, 1, 0, 1, 1)"
)


def test_the_upgrade_creates_both_tables_and_keeps_what_was_stored(tmp_path: Path) -> None:
    """R-QA-04: a database of the version before gets the catalogue tables and loses nothing."""
    engine = new_database(tmp_path)
    upgrade_to(engine, "0003")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO app_meta (key, value, created_at, updated_at)"
                " VALUES ('setup_completed_at', '1794000000', 1, 1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO settings (key, value, created_at, updated_at)"
                " VALUES ('log_detail', '\"verbose\"', 1, 1)"
            )
        )

    upgrade_to(engine, "0004")

    assert table_names(engine) == {"alembic_version", "settings", "app_meta", "channels", "videos"}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT value FROM app_meta")).scalars().all() == [
            "1794000000"
        ]
        assert connection.execute(text("SELECT value FROM settings")).scalars().all() == [
            '"verbose"'
        ]


def test_a_channel_has_the_columns_of_the_data_model(tmp_path: Path) -> None:
    """R-QA-04, R-CH-35: a channel stores the time of its last check and of its last full check."""
    engine = new_database(tmp_path)

    upgrade_to(engine, "0004")

    columns = {column["name"]: column for column in inspect(engine).get_columns("channels")}
    assert list(columns) == [
        "id",
        "url",
        "title",
        "handle",
        "avatar_url",
        "folder",
        "folder_is_custom",
        "quality",
        "auto_mirror",
        "mirror_after",
        "paused",
        "first_listed_at",
        "last_check_at",
        "last_full_check_at",
        "last_check_error",
        "position",
        "created_at",
        "updated_at",
    ]
    may_be_empty = {name for name, column in columns.items() if column["nullable"]}
    assert may_be_empty == {
        "handle",
        "avatar_url",
        "quality",
        "mirror_after",
        "first_listed_at",
        "last_check_at",
        "last_full_check_at",
        "last_check_error",
    }
    assert inspect(engine).get_pk_constraint("channels")["constrained_columns"] == ["id"]


def test_a_video_has_the_columns_of_the_data_model(tmp_path: Path) -> None:
    """R-QA-04, R-DT-04, R-DT-01: a video stores the precision of its date and when it was seen."""
    engine = new_database(tmp_path)

    upgrade_to(engine, "0004")

    columns = {column["name"]: column for column in inspect(engine).get_columns("videos")}
    assert list(columns) == [
        "id",
        "channel_id",
        "title",
        "duration_s",
        "view_count",
        "published_at",
        "published_exact",
        "published_precision",
        "thumbnail_url",
        "channel_position",
        "status",
        "excluded",
        "excluded_by",
        "exclude_exception",
        "missing_checks",
        "gone",
        "first_seen_at",
        "last_seen_at",
        "seen_in_first_listing",
        "file_name",
        "file_size",
        "height",
        "vcodec",
        "acodec",
        "has_subtitles",
        "downloaded_at",
        "last_error_code",
        "last_error_at",
        "attempts",
        "created_at",
        "updated_at",
    ]
    required = {name for name, column in columns.items() if not column["nullable"]}
    assert required == {
        "id",
        "channel_id",
        "title",
        "published_exact",
        "channel_position",
        "status",
        "excluded",
        "exclude_exception",
        "missing_checks",
        "gone",
        "first_seen_at",
        "last_seen_at",
        "seen_in_first_listing",
        "attempts",
        "created_at",
        "updated_at",
    }
    assert inspect(engine).get_pk_constraint("videos")["constrained_columns"] == ["id"]


def test_the_catalogue_has_the_indexes_of_the_data_model(tmp_path: Path) -> None:
    """R-QA-04: the three indexes of ARCHITECTURE section 5 exist."""
    engine = new_database(tmp_path)

    upgrade_to(engine, "0004")

    indexes = {
        index["name"]: index["column_names"] for index in inspect(engine).get_indexes("videos")
    }
    assert indexes == {
        "ix_videos_channel_position": ["channel_id", "channel_position"],
        "ix_videos_channel_status": ["channel_id", "status"],
        "ix_videos_status": ["status"],
    }


def test_a_video_needs_its_channel_and_goes_with_it(tmp_path: Path) -> None:
    """R-CH-32, R-QA-04: the catalogue of a channel is deleted with the channel."""
    engine = new_database(tmp_path)
    upgrade_to(engine, "0004")
    with engine.begin() as connection:
        connection.execute(text(CHANNEL))
        connection.execute(text(VIDEO), {"id": "v1", "channel": "UCa"})

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text(VIDEO), {"id": "v2", "channel": "UCmissing"})
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM channels WHERE id = 'UCa'"))

    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM videos")).scalar_one() == 0
