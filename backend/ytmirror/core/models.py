"""Domain data types of yt-mirror.

Frozen dataclasses and enums only. Channel, Video and Job are added by the
milestones that implement them. This module must not read or write anything.

Tests: backend/tests/unit/core/test_models.py
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

MINIMUM_MACOS_MAJOR = 15
"""The oldest supported macOS major version (R-PL-01, docs/DECISIONS.md D-035)."""


class LogDetail(StrEnum):
    """The "Log detail" setting (docs/SPEC.md section 10, docs/LOGGING.md section 1)."""

    NORMAL = "normal"
    VERBOSE = "verbose"


class InstallKind(StrEnum):
    """How this copy of the app was installed (docs/GLOSSARY.md)."""

    CLONE = "clone"
    ARCHIVE = "archive"


@dataclass(frozen=True, slots=True)
class Settings:
    """The general settings, with their defaults (docs/SPEC.md section 10).

    Each milestone adds the settings it implements. A field name is the key
    under which the value is stored.

    Attributes:
        log_detail: How much the debug log records.
    """

    log_detail: LogDetail = LogDetail.NORMAL


@dataclass(frozen=True, slots=True)
class AppInfo:
    """Facts about this installation that do not change while the app runs.

    Attributes:
        version: The app version.
        install_kind: How this copy was installed.
        home_dir: The folder that holds ``data/`` and ``tools/``.
        data_dir: The folder with the database, logs and caches.
        database_file: The SQLite database file.
        frontend_dir: The folder with the built interface.
        uv_executable: The bundled uv program.
    """

    version: str
    install_kind: InstallKind
    home_dir: Path
    data_dir: Path
    database_file: Path
    frontend_dir: Path
    uv_executable: Path


@dataclass(frozen=True, slots=True)
class Health:
    """The answer of the health endpoint.

    Attributes:
        version: The app version.
        schema_version: The database schema version, or None before the first migration.
    """

    version: str
    schema_version: str | None


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One line of the environment report of ``./start --doctor``.

    Attributes:
        name: What was checked.
        ok: Whether the check passed.
        detail: What was found.
        fix: What the user can do when the check failed, otherwise None.
    """

    name: str
    ok: bool
    detail: str
    fix: str | None = None
