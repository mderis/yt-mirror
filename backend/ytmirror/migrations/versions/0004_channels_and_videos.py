"""Create the channels and videos tables (docs/ARCHITECTURE.md section 5).

The catalogue of milestone M2: the channels the user added and their regular
videos (R-CH-10). A video carries the precision of an approximate date
(R-DT-04) and when a check last listed it (R-DT-01). A channel carries the
time of its last check and of its last full check (R-CH-35). Removing a
channel removes its videos (R-CH-32).

Tests: backend/tests/migrations/test_0004_channels_and_videos.py
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade() -> None:
    """Create ``channels`` and ``videos`` with the indexes of the catalogue."""
    op.create_table(
        "channels",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("handle", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("folder", sa.Text(), nullable=False),
        sa.Column("folder_is_custom", sa.Boolean(), nullable=False),
        sa.Column("quality", sa.Text(), nullable=True),
        sa.Column("auto_mirror", sa.Boolean(), nullable=False),
        sa.Column("mirror_after", sa.Integer(), nullable=True),
        sa.Column("paused", sa.Boolean(), nullable=False),
        sa.Column("first_listed_at", sa.Integer(), nullable=True),
        sa.Column("last_check_at", sa.Integer(), nullable=True),
        sa.Column("last_full_check_at", sa.Integer(), nullable=True),
        sa.Column("last_check_error", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
    )
    op.create_table(
        "videos",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "channel_id",
            sa.Text(),
            sa.ForeignKey("channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("duration_s", sa.Integer(), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.Integer(), nullable=True),
        sa.Column("published_exact", sa.Boolean(), nullable=False),
        sa.Column("published_precision", sa.Text(), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("channel_position", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("excluded", sa.Boolean(), nullable=False),
        sa.Column("excluded_by", sa.Text(), nullable=True),
        sa.Column("exclude_exception", sa.Boolean(), nullable=False),
        sa.Column("missing_checks", sa.Integer(), nullable=False),
        sa.Column("gone", sa.Boolean(), nullable=False),
        sa.Column("first_seen_at", sa.Integer(), nullable=False),
        sa.Column("last_seen_at", sa.Integer(), nullable=False),
        sa.Column("seen_in_first_listing", sa.Boolean(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("vcodec", sa.Text(), nullable=True),
        sa.Column("acodec", sa.Text(), nullable=True),
        sa.Column("has_subtitles", sa.Text(), nullable=True),
        sa.Column("downloaded_at", sa.Integer(), nullable=True),
        sa.Column("last_error_code", sa.Text(), nullable=True),
        sa.Column("last_error_at", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
    )
    op.create_index("ix_videos_channel_position", "videos", ["channel_id", "channel_position"])
    op.create_index("ix_videos_channel_status", "videos", ["channel_id", "status"])
    op.create_index("ix_videos_status", "videos", ["status"])
