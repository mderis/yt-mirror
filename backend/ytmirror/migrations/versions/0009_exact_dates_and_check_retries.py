"""Add what the exact-date fetch keeps per video, and the retry step of a failed check.

``date_fetch_queue`` holds, for a video without an exact date, what the
fetch must remember across restarts (R-DT-06): whether a decision waits for
its date (R-MI-03), how many lookups failed and when the next may be tried
(R-DT-13), and when the YouTube API last left it out (D-083). A video that
has no row simply waits its turn. Removing the video removes its row.

``channels.check_retries`` is the step of the automatic retries of a
failed check (R-CH-25): 0 before the first, then 5, 15 and 60 minutes. It
must survive a restart.

Tests: backend/tests/migrations/test_0009_exact_dates_and_check_retries.py
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"


def upgrade() -> None:
    """Create ``date_fetch_queue`` and add ``channels.check_retries``."""
    op.create_table(
        "date_fetch_queue",
        sa.Column(
            "video_id",
            sa.Text(),
            sa.ForeignKey("videos.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_try_at", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("api_left_out_at", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
    )
    op.create_index("ix_videos_exact", "videos", ["published_exact", "gone"])
    op.add_column(
        "channels",
        sa.Column("check_retries", sa.Integer(), nullable=False, server_default="0"),
    )
