"""Stores the general settings in the ``settings`` table.

Implements the SettingsRepository port. Each field of the Settings model is
one row: the field name is the key, the value is stored as JSON. This module
must not decide what a setting means.

Tests: backend/tests/integration/test_settings_repository_contract.py
"""

import json
from collections.abc import Mapping

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from ytmirror.adapters.db.tables import SettingRow
from ytmirror.core.models import LogDetail, Settings
from ytmirror.ports.clock import Clock


class SqlSettingsRepository:
    """Loads and saves the general settings (R-SE-03)."""

    def __init__(self, engine: Engine, clock: Clock) -> None:
        """Create the repository.

        Args:
            engine: The database engine.
            clock: The source of the ``created_at`` and ``updated_at`` times.
        """
        self._engine = engine
        self._clock = clock

    def load(self) -> Settings:
        """Return the stored settings. A setting that was never stored has its default."""
        with Session(self._engine) as session:
            rows = session.scalars(select(SettingRow)).all()
            stored: dict[str, object] = {row.key: json.loads(row.value) for row in rows}
        return _settings_from(stored)

    def save(self, settings: Settings) -> None:
        """Store every setting.

        Args:
            settings: The settings to store.
        """
        now = int(self._clock.now().timestamp())
        with Session(self._engine) as session, session.begin():
            for key, value in _values_of(settings).items():
                row = session.get(SettingRow, key)
                if row is None:
                    session.add(SettingRow(key=key, value=value, created_at=now, updated_at=now))
                elif row.value != value:
                    row.value = value
                    row.updated_at = now


def _values_of(settings: Settings) -> dict[str, str]:
    """Return each setting as JSON text, by key."""
    return {"log_detail": json.dumps(settings.log_detail.value)}


def _settings_from(stored: Mapping[str, object]) -> Settings:
    """Build the settings from stored values, using defaults for missing keys."""
    defaults = Settings()
    log_detail = stored.get("log_detail")
    return Settings(
        log_detail=LogDetail(log_detail) if isinstance(log_detail, str) else defaults.log_detail,
    )
