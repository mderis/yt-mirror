"""The menu bar, defined as data (docs/ARCHITECTURE.md section 7.10, docs/DESIGN.md section 7.1).

Implements R-NA-03, R-NA-04 and R-NA-09 as far as their targets exist in
milestone M5. Each item is a standard macOS action or a command of the app,
which the interface runs as its own control does (D-094). An item appears
with its target (D-066): About yt-mirror, Settings..., Show Activity,
Channel Settings..., yt-mirror Help and Report a Problem... arrive with M7,
Check for Updates... with M9. "Full Check" is not an item of the Channel menu
(Q-25). This is the one place of the menu texts and shortcuts (R-PL-06,
R-NA-09). It must not draw anything: the NativeApp port does that.

Tests: backend/tests/unit/app/test_menus.py
"""

from ytmirror.core.models import (
    ItemState,
    Menu,
    MenuAction,
    MenuCommand,
    MenuItem,
    Shortcut,
    UiState,
    ViewKind,
)


def _command(title: str, command: MenuCommand, shortcut: Shortcut | None = None) -> MenuItem:
    return MenuItem(title, MenuAction.COMMAND, shortcut, command)


def menu_bar(app_name: str, *, debug: bool = False) -> tuple[Menu, ...]:
    """Return the menu bar of the app (R-NA-03).

    Args:
        app_name: The name of the app as macOS shows it, for "Hide" and "Quit".
        debug: Whether the app runs with ``--debug``: only then is there "Reload".

    Returns:
        The menus from left to right. The first one is the app menu.
    """
    view_items: list[MenuItem] = [
        _command("List", MenuCommand.VIEW_LIST),
        _command("Grid", MenuCommand.VIEW_GRID),
    ]
    reload = (_command("Reload", MenuCommand.RELOAD),) if debug else ()
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
            title="File",
            groups=(
                (_command("Add Channel...", MenuCommand.ADD_CHANNEL, Shortcut("n")),),
                (MenuItem("Close Window", MenuAction.CLOSE_WINDOW, Shortcut("w")),),
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
        Menu(
            title="View",
            groups=(
                tuple(view_items),
                (_command("Show Downloads", MenuCommand.SHOW_DOWNLOADS),),
                *((reload,) if reload else ()),
            ),
        ),
        Menu(
            title="Channel",
            groups=(
                (
                    _command("Check Now", MenuCommand.CHECK_NOW, Shortcut("r")),
                    _command("Check All Channels", MenuCommand.CHECK_ALL),
                ),
                (
                    _command("Mirror Everything Missing", MenuCommand.MIRROR_MISSING),
                    _command("Pause Channel", MenuCommand.TOGGLE_PAUSE),
                    _command("Open Folder", MenuCommand.OPEN_FOLDER),
                ),
            ),
        ),
        Menu(
            title="Window",
            groups=(
                (
                    MenuItem("Minimize", MenuAction.MINIMIZE, Shortcut("m")),
                    MenuItem("Zoom", MenuAction.ZOOM),
                ),
            ),
            role="window",
        ),
        Menu(
            title="Help",
            groups=((_command("Keyboard Shortcuts", MenuCommand.SHORTCUTS),),),
            role="help",
        ),
    )


def item_state(command: MenuCommand, ui: UiState) -> ItemState:
    """Return how a command item of the menu bar stands now (R-NA-04, docs/DESIGN.md 7.1).

    An item is enabled only when it applies. "Pause Channel" reads "Resume Channel"
    for a paused channel, and the view that is shown has a check mark.

    Args:
        command: The command of the item.
        ui: What the interface last told about itself.
    """
    match command:
        case MenuCommand.VIEW_LIST | MenuCommand.VIEW_GRID:
            kind = ViewKind.LIST if command is MenuCommand.VIEW_LIST else ViewKind.GRID
            return ItemState(enabled=ui.channel_open, checked=ui.view is kind)
        case MenuCommand.CHECK_NOW:
            # A paused channel is not checked (R-CH-31), nor one whose check runs.
            return ItemState(enabled=ui.channel_open and not ui.paused and not ui.checking)
        case MenuCommand.CHECK_ALL:
            return ItemState(enabled=ui.any_unpaused)
        case MenuCommand.MIRROR_MISSING:
            return ItemState(enabled=ui.channel_open and ui.has_missing)
        case MenuCommand.TOGGLE_PAUSE:
            return ItemState(
                enabled=ui.channel_open,
                title="Resume Channel" if ui.channel_open and ui.paused else "Pause Channel",
            )
        case MenuCommand.OPEN_FOLDER:
            return ItemState(enabled=ui.channel_open and ui.folder_available)
        case MenuCommand.ADD_CHANNEL | MenuCommand.SHOW_DOWNLOADS | MenuCommand.SHORTCUTS:
            return ItemState(enabled=True)
        case MenuCommand.RELOAD:
            return ItemState(enabled=True)
