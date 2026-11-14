"""The menu bar, defined as data (docs/ARCHITECTURE.md section 7.10).

Implements the part of R-NA-03 that exists in milestone M1: the app menu
and Edit, so that Quit and the text fields work. The other menus arrive in
M5 with the actions they trigger. This is the one place of the menu texts
and shortcuts (R-PL-06, R-NA-09). It must not draw anything: the NativeApp
port does that.

Tests: backend/tests/unit/app/test_menus.py
"""

from ytmirror.core.models import Menu, MenuAction, MenuItem, Shortcut


def menu_bar(app_name: str) -> tuple[Menu, ...]:
    """Return the menu bar of the app.

    Implements R-NA-03 as far as milestone M1 goes.

    Args:
        app_name: The name of the app as macOS shows it, for "Hide" and "Quit".

    Returns:
        The menus from left to right. The first one is the app menu.
    """
    return (
        Menu(
            title=app_name,
            groups=(
                (
                    MenuItem(f"Hide {app_name}", MenuAction.HIDE, Shortcut("h")),
                    MenuItem("Hide Others", MenuAction.HIDE_OTHERS, Shortcut("h", option=True)),
                    MenuItem("Show All", MenuAction.SHOW_ALL),
                ),
                (MenuItem(f"Quit {app_name}", MenuAction.QUIT, Shortcut("q")),),
            ),
        ),
        Menu(
            title="Edit",
            groups=(
                (
                    MenuItem("Undo", MenuAction.UNDO, Shortcut("z")),
                    MenuItem("Redo", MenuAction.REDO, Shortcut("z", shift=True)),
                ),
                (
                    MenuItem("Cut", MenuAction.CUT, Shortcut("x")),
                    MenuItem("Copy", MenuAction.COPY, Shortcut("c")),
                    MenuItem("Paste", MenuAction.PASTE, Shortcut("v")),
                    MenuItem("Select All", MenuAction.SELECT_ALL, Shortcut("a")),
                ),
            ),
        ),
    )
