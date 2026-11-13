"""Create the settings table (docs/ARCHITECTURE.md section 5).

Tests: backend/tests/migrations/test_0002_settings.py
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    """Create ``settings``: one row per setting, the value as JSON text."""
    op.create_table(
        "settings",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
    )
