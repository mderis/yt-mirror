"""The SQLAlchemy table classes (docs/ARCHITECTURE.md section 5).

All timestamps are integers: seconds since the Unix epoch, UTC. Every table
has ``created_at`` and ``updated_at``. A change to a table needs a migration
in ``backend/ytmirror/migrations/versions/`` in the same commit.

Tests: backend/tests/migrations/test_schema_matches_tables.py
"""

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class of all table classes."""


class SettingRow(Base):
    """One general setting: a key and its value as JSON text."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False)


class AppMetaRow(Base):
    """One fact the app keeps about itself, for example when its setup completed."""

    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False)


class ChannelRow(Base):
    """One channel the user added."""

    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    handle: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    folder: Mapped[str] = mapped_column(Text, nullable=False)
    folder_is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False)
    quality: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_mirror: Mapped[bool] = mapped_column(Boolean, nullable=False)
    mirror_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paused: Mapped[bool] = mapped_column(Boolean, nullable=False)
    first_listed_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_check_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_full_check_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_check_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False)


class VideoRow(Base):
    """One regular video of a channel."""

    __tablename__ = "videos"
    __table_args__ = (
        Index("ix_videos_channel_position", "channel_id", "channel_position"),
        Index("ix_videos_channel_status", "channel_id", "status"),
        Index("ix_videos_status", "status"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    channel_id: Mapped[str] = mapped_column(
        Text, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    view_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_exact: Mapped[bool] = mapped_column(Boolean, nullable=False)
    published_precision: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel_position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    excluded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    excluded_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    exclude_exception: Mapped[bool] = mapped_column(Boolean, nullable=False)
    missing_checks: Mapped[int] = mapped_column(Integer, nullable=False)
    gone: Mapped[bool] = mapped_column(Boolean, nullable=False)
    first_seen_at: Mapped[int] = mapped_column(Integer, nullable=False)
    last_seen_at: Mapped[int] = mapped_column(Integer, nullable=False)
    seen_in_first_listing: Mapped[bool] = mapped_column(Boolean, nullable=False)
    file_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vcodec: Mapped[str | None] = mapped_column(Text, nullable=True)
    acodec: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_subtitles: Mapped[str | None] = mapped_column(Text, nullable=True)
    downloaded_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False)
