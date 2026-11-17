"""Add the marker of a rename after a new title.

Before a synced file is renamed (R-FN-06), its old and new names are stored;
they are cleared when the new name is stored. A rename that the app's end
interrupted is then finished or undone at the next check, whatever the title
is by then.

Tests: backend/tests/migrations/test_0010_rename_marker.py
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"


def upgrade() -> None:
    """Add ``videos.rename_from`` and ``videos.rename_to``."""
    op.add_column("videos", sa.Column("rename_from", sa.Text(), nullable=True))
    op.add_column("videos", sa.Column("rename_to", sa.Text(), nullable=True))
