"""Domain data types of yt-mirror.

Frozen dataclasses and enums only. Channel, Video and Job are added by the
milestones that implement them. This module must not read or write anything.

Tests: backend/tests/unit/core/test_models.py
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

APP_NAME = "yt-mirror"
"""The name of the app everywhere a user reads it (R-NA-01)."""

BUNDLE_IDENTIFIER = "io.github.mderis.yt-mirror"
"""The bundle identifier of an installed copy. It never changes (docs/DECISIONS.md D-047)."""

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


@dataclass(frozen=True, slots=True)
class AppIdentity:
    """The name and the bundle identifier under which macOS knows the app (R-NA-01, R-NA-02).

    Attributes:
        name: The name in the Dock, the app switcher, the menu bar and Activity Monitor.
        bundle_identifier: The identifier macOS ties the app's identity to.
    """

    name: str
    bundle_identifier: str


class MenuAction(StrEnum):
    """What a menu item does. In milestone M1 only the standard macOS actions (R-NA-03)."""

    HIDE = "hide"
    HIDE_OTHERS = "hide_others"
    SHOW_ALL = "show_all"
    QUIT = "quit"
    UNDO = "undo"
    REDO = "redo"
    CUT = "cut"
    COPY = "copy"
    PASTE = "paste"
    SELECT_ALL = "select_all"


@dataclass(frozen=True, slots=True)
class Shortcut:
    """A menu shortcut. Command is always part of it.

    Attributes:
        key: The key, one lower-case character.
        shift: Shift is held as well.
        option: Option is held as well.
    """

    key: str
    shift: bool = False
    option: bool = False


@dataclass(frozen=True, slots=True)
class MenuItem:
    """One item of a menu.

    Attributes:
        title: The text of the item, written as macOS writes it.
        action: What the item does.
        shortcut: Its shortcut, or None.
    """

    title: str
    action: MenuAction
    shortcut: Shortcut | None = None


@dataclass(frozen=True, slots=True)
class Menu:
    """One menu of the menu bar.

    Attributes:
        title: The title in the menu bar. macOS shows the app name for the first menu.
        groups: The items in groups. A separator line is drawn between two groups.
    """

    title: str
    groups: tuple[tuple[MenuItem, ...], ...]


@dataclass(frozen=True, slots=True)
class ShownMenuItem:
    """An item as it really is in the menu bar right now.

    Attributes:
        title: The text of the item.
        action: Our action, or None for an item that is not ours. macOS adds items
            of its own to some menus, for example "Start Dictation" to Edit.
        shortcut: Its shortcut, or None.
        enabled: Whether the item can be chosen right now.
    """

    title: str
    action: MenuAction | None
    shortcut: Shortcut | None
    enabled: bool


@dataclass(frozen=True, slots=True)
class ShownMenu:
    """A menu as it really is in the menu bar right now.

    Attributes:
        title: The title of the menu.
        items: Its items without the separator lines.
    """

    title: str
    items: tuple[ShownMenuItem, ...]
