"""Create the jobs and video_events tables (docs/ARCHITECTURE.md section 5).

Milestone M3 downloads videos. A job is one piece of work on one video, and
its ID ties its log lines together (R-LG-02). Every status change of a video
is recorded with its time, both statuses, the reason and the job ID
(R-LG-03). Removing a channel removes its videos, and with them their jobs
and their history (R-CH-32).

Tests: backend/tests/migrations/test_0006_jobs_and_video_events.py
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"


def upgrade() -> None:
    """Create ``jobs`` and ``video_events`` with the indexes the queue and the history read."""
    op.create_table(
        "jobs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "video_id",
            sa.Text(),
            sa.ForeignKey("videos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("quality", sa.Text(), nullable=False),
        sa.Column("progress", sa.Float(), nullable=True),
        sa.Column("stage", sa.Text(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("started_at", sa.Integer(), nullable=True),
        sa.Column("finished_at", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
    )
    op.create_index("ix_jobs_state_priority", "jobs", ["state", "priority"])
    op.create_index("ix_jobs_video", "jobs", ["video_id"])
    op.create_table(
        "video_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "video_id",
            sa.Text(),
            sa.ForeignKey("videos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("at", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=False),
        sa.Column("to_status", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("job_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
    )
    op.create_index("ix_video_events_video_at", "video_events", ["video_id", "at"])
