"""Baseline: an empty schema.

The first migration creates no table. It exists so that every database has a
schema version from its first start, and so that the migration pipeline is
proven before the first table arrives.

Tests: backend/tests/migrations/test_0001_baseline.py
"""

revision = "0001"
down_revision = None


def upgrade() -> None:
    """Change nothing. Migrations are forward only: there is no downgrade."""
