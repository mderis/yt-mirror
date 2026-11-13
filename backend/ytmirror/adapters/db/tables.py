"""The SQLAlchemy table classes (docs/ARCHITECTURE.md section 5).

All timestamps are integers: seconds since the Unix epoch, UTC. Every table
has ``created_at`` and ``updated_at``. A change to a table needs a migration
in ``backend/ytmirror/migrations/versions/`` in the same commit.

Tests: backend/tests/migrations/test_schema_matches_tables.py
"""

from sqlalchemy import Integer, Text
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
