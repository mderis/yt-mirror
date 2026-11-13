"""The Alembic environment of yt-mirror.

Alembic runs this file for every migration command. The connection is given
by ``adapters/db/schema.py``, so this file must not open the database itself
and must not be used through the ``alembic`` command line.

Tests: backend/tests/migrations/
"""

from alembic import context
from sqlalchemy import Connection


def run_migrations() -> None:
    """Run the pending migrations on the connection provided by the app."""
    connection = context.config.attributes.get("connection")
    if not isinstance(connection, Connection):
        raise RuntimeError("Migrations are run by the app, not with the alembic command.")
    context.configure(connection=connection, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


run_migrations()
