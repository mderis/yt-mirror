"""Add what the queue of milestone M5 keeps about jobs, videos and channels.

- ``jobs.by_hand``: whether the user started the job by hand. Such a job is
  never held back by the lookup budget; an automatic one waits for room
  (R-DT-06, D-090). Every job stored before was started by hand: auto-mirror
  did not exist.
- ``jobs.not_before``: the earliest time an automatic retry may start (R-QU-07).
- ``jobs.formats``: the formats the download chose, asked for again when it
  continues after a quit (R-QU-05, D-091).
- ``videos.replacing``: the marker of a re-download that swaps its new file in
  (R-QL-06, D-093).
- ``channels.missing_left``: how many missing files the user chose to leave
  missing (R-MI-06, D-092).
- ``channels.auto_mirror_asked``: whether auto-mirror may start the downloads
  of the channel. Every channel stored with auto-mirror on is asked first at
  its next start (R-MI-02, D-095).

Tests: backend/tests/migrations/test_0011_queue.py
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"


def upgrade() -> None:
    """Add the columns and ask every channel that has auto-mirror on."""
    op.add_column(
        "jobs", sa.Column("by_hand", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.add_column("jobs", sa.Column("not_before", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("formats", sa.Text(), nullable=True))
    op.add_column("videos", sa.Column("replacing", sa.Text(), nullable=True))
    op.add_column("channels", sa.Column("missing_left", sa.Integer(), nullable=True))
    op.add_column(
        "channels",
        sa.Column("auto_mirror_asked", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.execute("UPDATE channels SET auto_mirror_asked = 0 WHERE auto_mirror = 1")
