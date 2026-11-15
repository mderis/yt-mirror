"""Add the marker of a file being put in place, and who created a channel folder.

``videos.placing_file`` names the file that a running download is moving into
the channel folder. It is set before the move and cleared when the job ends,
in the same transaction as the video's new status, so that a start after a
crash knows which file the app moved (R-QA-06). ``channels.folder_created``
says whether the app created the channel folder: only such a folder may go
to the Trash when a removal leaves it empty (R-CH-32).

Tests: backend/tests/migrations/test_0007_placing_file_and_folder_created.py
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"


def upgrade() -> None:
    """Add both columns. Existing videos place nothing; existing folders count as the user's."""
    op.add_column("videos", sa.Column("placing_file", sa.Text(), nullable=True))
    # A plain ADD COLUMN, never a rebuild of the table: with foreign keys on, dropping the
    # old channels table would delete every video with it.
    op.add_column(
        "channels",
        sa.Column("folder_created", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
