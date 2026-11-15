"""Add the side files of synced videos that are still to be written.

Once a video file is in the channel folder with its dates, a failure to
write a side file (the info JSON, the original thumbnail, the thumbnail
next to the video) does not fail the download: the video is synced, and the
side file waits here, with its content, until it can be written (R-MD-02,
R-MD-05). Removing the video removes what waits for it.

Tests: backend/tests/migrations/test_0008_pending_side_files.py
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"


def upgrade() -> None:
    """Create ``pending_side_files``."""
    op.create_table(
        "pending_side_files",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "video_id",
            sa.Text(),
            sa.ForeignKey("videos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
    )
