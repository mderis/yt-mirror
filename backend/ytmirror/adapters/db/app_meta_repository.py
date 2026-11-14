"""Stores facts the app keeps about itself in the ``app_meta`` table.

Implements the AppMetaRepository port. This module must not decide what a
fact means.

Tests: backend/tests/integration/test_app_meta_repository_contract.py
"""

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from ytmirror.adapters.db.tables import AppMetaRow
from ytmirror.ports.clock import Clock


class SqlAppMetaRepository:
    """Reads and writes rows of ``app_meta``."""

    def __init__(self, engine: Engine, clock: Clock) -> None:
        """Create the repository.

        Args:
            engine: The database engine.
            clock: The source of the ``created_at`` and ``updated_at`` times.
        """
        self._engine = engine
        self._clock = clock

    def get(self, key: str) -> str | None:
        """Return the value stored under a key, or None when nothing was stored.

        Args:
            key: The name of the fact.
        """
        with Session(self._engine) as session:
            row = session.get(AppMetaRow, key)
            return None if row is None else row.value

    def put(self, key: str, value: str) -> None:
        """Store a value under a key, replacing an earlier one.

        Args:
            key: The name of the fact.
            value: Its value as text.
        """
        now = int(self._clock.now().timestamp())
        with Session(self._engine) as session, session.begin():
            row = session.get(AppMetaRow, key)
            if row is None:
                session.add(AppMetaRow(key=key, value=value, created_at=now, updated_at=now))
            elif row.value != value:
                row.value = value
                row.updated_at = now
