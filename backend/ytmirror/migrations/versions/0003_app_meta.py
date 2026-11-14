"""Create the app_meta table (docs/ARCHITECTURE.md section 5).

The first fact kept in it is the moment the first-run setup completed
(R-IN-03).

Tests: backend/tests/migrations/test_0003_app_meta.py
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade() -> None:
    """Create ``app_meta``: one row per fact the app keeps about itself."""
    op.create_table(
        "app_meta",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
    )
