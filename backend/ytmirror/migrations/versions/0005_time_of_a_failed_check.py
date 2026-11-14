"""Add the time of a failed check to the channels (docs/ARCHITECTURE.md section 5).

The banner of a failed check says when the check failed (R-CH-25). The
error code alone was stored by migration 0004.

Tests: backend/tests/migrations/test_0005_time_of_a_failed_check.py
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"


def upgrade() -> None:
    """Add ``channels.last_check_error_at``. Existing channels have no time."""
    op.add_column("channels", sa.Column("last_check_error_at", sa.Integer(), nullable=True))
