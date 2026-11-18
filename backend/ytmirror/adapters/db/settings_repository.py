"""Stores the general settings in the ``settings`` table.

Implements the SettingsRepository port. Each field of the Settings model is
one row: the field name is the key, the value is stored as JSON. This module
must not decide what a setting means.

Tests: backend/tests/integration/test_settings_repository_contract.py
"""

import json
from collections.abc import Mapping, Sequence

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from ytmirror.adapters.db.engine import for_reading
from ytmirror.adapters.db.tables import SettingRow
from ytmirror.core.channels import Quality
from ytmirror.core.models import (
    DISK_GUARD_GB,
    FULL_CHECK_DAYS,
    PARALLEL_DOWNLOADS,
    RECHECK_INTERVALS_MIN,
    SPEED_LIMITS_MBPS,
    LogDetail,
    Settings,
    ViewKind,
)
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
        self._reader = for_reading(engine)
        self._clock = clock

    def load(self) -> Settings:
        """Return the stored settings. A setting that was never stored has its default."""
        with Session(self._reader) as session:
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
    return {
        "log_detail": json.dumps(settings.log_detail.value),
        "library_folder": json.dumps(settings.library_folder),
        "default_quality": json.dumps(settings.default_quality.value),
        "embed_subtitles": json.dumps(settings.embed_subtitles),
        "auto_subtitles": json.dumps(settings.auto_subtitles),
        "thumbnail_next_to_video": json.dumps(settings.thumbnail_next_to_video),
        "check_on_open": json.dumps(settings.check_on_open),
        "recheck_interval_min": json.dumps(settings.recheck_interval_min),
        "full_check_days": json.dumps(settings.full_check_days),
        "fetch_exact_dates": json.dumps(settings.fetch_exact_dates),
        "repair_dates": json.dumps(settings.repair_dates),
        "parallel_downloads": json.dumps(settings.parallel_downloads),
        "speed_limit_mbps": json.dumps(settings.speed_limit_mbps),
        "disk_guard_gb": json.dumps(settings.disk_guard_gb),
        "downloads_paused": json.dumps(settings.downloads_paused),
        "default_view": json.dumps(settings.default_view.value),
    }


def _settings_from(stored: Mapping[str, object]) -> Settings:
    """Build the settings from stored values, using defaults for missing keys."""
    defaults = Settings()
    log_detail = stored.get("log_detail")
    library_folder = stored.get("library_folder")
    return Settings(
        log_detail=LogDetail(log_detail) if isinstance(log_detail, str) else defaults.log_detail,
        library_folder=library_folder
        if isinstance(library_folder, str) and library_folder
        else defaults.library_folder,
        default_quality=_quality(stored.get("default_quality"), defaults.default_quality),
        embed_subtitles=_flag(stored.get("embed_subtitles"), defaults.embed_subtitles),
        auto_subtitles=_flag(stored.get("auto_subtitles"), defaults.auto_subtitles),
        thumbnail_next_to_video=_flag(
            stored.get("thumbnail_next_to_video"), defaults.thumbnail_next_to_video
        ),
        check_on_open=_flag(stored.get("check_on_open"), defaults.check_on_open),
        recheck_interval_min=_choice(
            stored.get("recheck_interval_min"),
            RECHECK_INTERVALS_MIN,
            defaults.recheck_interval_min,
        ),
        full_check_days=_choice(
            stored.get("full_check_days"), FULL_CHECK_DAYS, defaults.full_check_days
        ),
        fetch_exact_dates=_flag(stored.get("fetch_exact_dates"), defaults.fetch_exact_dates),
        repair_dates=_flag(stored.get("repair_dates"), defaults.repair_dates),
        parallel_downloads=_choice(
            stored.get("parallel_downloads"), PARALLEL_DOWNLOADS, defaults.parallel_downloads
        ),
        speed_limit_mbps=_choice(
            stored.get("speed_limit_mbps"), SPEED_LIMITS_MBPS, defaults.speed_limit_mbps
        ),
        disk_guard_gb=_choice(stored.get("disk_guard_gb"), DISK_GUARD_GB, defaults.disk_guard_gb),
        downloads_paused=_flag(stored.get("downloads_paused"), defaults.downloads_paused),
        default_view=_view(stored.get("default_view"), defaults.default_view),
    )


def _quality(value: object, default: Quality) -> Quality:
    """Return a stored quality, or the default when it cannot be read (R-SE-04)."""
    try:
        return Quality(value) if isinstance(value, str) else default
    except ValueError:
        return default


def _view(value: object, default: ViewKind) -> ViewKind:
    """Return a stored view, or the default when it cannot be read (R-SE-04)."""
    try:
        return ViewKind(value) if isinstance(value, str) else default
    except ValueError:
        return default


def _flag(value: object, default: bool) -> bool:
    """Return a stored switch, or the default when it is not one (R-SE-04)."""
    return value if isinstance(value, bool) else default


def _choice(value: object, choices: Sequence[int], default: int) -> int:
    """Return a stored number that is one of the choices, or the default (R-SE-04)."""
    if isinstance(value, bool) or not isinstance(value, int) or value not in choices:
        return default
    return value
