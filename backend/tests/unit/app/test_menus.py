"""Tests of ``ytmirror.app.menus``."""

import pytest

from ytmirror.app.menus import item_state, menu_bar
from ytmirror.core.models import (
    ItemState,
    Menu,
    MenuAction,
    MenuCommand,
    Shortcut,
    UiState,
    ViewKind,
)


def titles(app_name: str, *, debug: bool = False) -> dict[str, list[list[str]]]:
    """Return the titles of every menu, group by group."""
    return {
        menu.title: [[item.title for item in group] for group in menu.groups]
        for menu in menu_bar(app_name, debug=debug)
    }


def menu(title: str, *, debug: bool = False) -> Menu:
    """Return one menu of the bar by its title."""
    return next(menu for menu in menu_bar("yt-mirror", debug=debug) if menu.title == title)


def test_the_app_menu_hides_and_quits_under_the_apps_own_name() -> None:
    """R-NA-03: the app menu has Hide, Hide Others and Quit yt-mirror (Cmd+Q)."""
    app_menu = menu_bar("yt-mirror")[0]

    assert titles("yt-mirror")["yt-mirror"] == [
        ["Hide yt-mirror", "Hide Others", "Show All"],
        ["Quit yt-mirror"],
    ]
    quit_item = app_menu.groups[1][0]
    assert quit_item.action is MenuAction.QUIT
    assert quit_item.shortcut == Shortcut("q")


def test_a_clone_names_itself_in_its_menu() -> None:
    """R-NA-01: a clone appears as "yt-mirror (dev)", in its menu items too."""
    assert titles("yt-mirror (dev)")["yt-mirror (dev)"] == [
        ["Hide yt-mirror (dev)", "Hide Others", "Show All"],
        ["Quit yt-mirror (dev)"],
    ]


def test_the_edit_menu_has_the_six_items_text_fields_need() -> None:
    """R-NA-03: Edit has Undo, Redo, Cut, Copy, Paste and Select All."""
    edit = menu("Edit")

    assert titles("yt-mirror")["Edit"] == [
        ["Undo", "Redo"],
        ["Cut", "Copy", "Paste", "Select All"],
    ]
    shortcuts = {item.title: item.shortcut for group in edit.groups for item in group}
    assert shortcuts == {
        "Undo": Shortcut("z"),
        "Redo": Shortcut("z", shift=True),
        "Cut": Shortcut("x"),
        "Copy": Shortcut("c"),
        "Paste": Shortcut("v"),
        "Select All": Shortcut("a"),
    }


def test_the_menu_bar_has_the_menus_of_the_design_with_the_items_whose_targets_exist() -> None:
    """R-NA-03: File, Edit, View, Channel, Window and Help, as docs/DESIGN.md 7.1 lists them."""
    assert titles("yt-mirror") == {
        "yt-mirror": [["Hide yt-mirror", "Hide Others", "Show All"], ["Quit yt-mirror"]],
        "File": [["Add Channel..."], ["Close Window"]],
        "Edit": [["Undo", "Redo"], ["Cut", "Copy", "Paste", "Select All"]],
        "View": [["List", "Grid"], ["Show Downloads"]],
        "Channel": [
            ["Check Now", "Check All Channels"],
            ["Mirror Everything Missing", "Pause Channel", "Open Folder"],
        ],
        "Window": [["Minimize", "Zoom"]],
        "Help": [["Keyboard Shortcuts"]],
    }
    assert menu("Window").role == "window"
    assert menu("Help").role == "help"


def test_the_shortcuts_of_the_menu_bar_are_those_of_the_design() -> None:
    """R-NA-09: Cmd+N adds a channel, Cmd+W closes, Cmd+R checks now, Cmd+M minimizes."""
    shortcuts = {
        item.title: item.shortcut
        for each in menu_bar("yt-mirror")
        for group in each.groups
        for item in group
        if item.shortcut is not None
    }

    assert shortcuts["Add Channel..."] == Shortcut("n")
    assert shortcuts["Close Window"] == Shortcut("w")
    assert shortcuts["Check Now"] == Shortcut("r")
    assert shortcuts["Minimize"] == Shortcut("m")
    assert len(set(shortcuts.values())) == len(shortcuts), "Two items share a shortcut"


def test_reload_exists_only_with_debug_and_never_takes_cmd_r() -> None:
    """R-NA-03: "Reload" is in the View menu only with --debug, without a shortcut."""
    assert "Reload" not in [item for group in titles("yt-mirror")["View"] for item in group]

    reload = next(
        item
        for group in menu("View", debug=True).groups
        for item in group
        if item.title == "Reload"
    )

    assert reload.command is MenuCommand.RELOAD
    assert reload.shortcut is None


def test_every_item_of_ours_is_a_standard_action_or_a_command() -> None:
    """R-NA-03, D-094: an item has a command exactly when its action is a command of the app."""
    for each in menu_bar("yt-mirror", debug=True):
        for group in each.groups:
            for item in group:
                assert (item.action is MenuAction.COMMAND) == (item.command is not None)


def test_no_item_exists_before_its_target_does() -> None:
    """infra: About, Settings, Help and Check for Updates arrive with M7 and M9 (D-066)."""
    everything = [title for groups in titles("yt-mirror").values() for g in groups for title in g]

    for word in ("About", "Settings", "yt-mirror Help", "Updates", "Full Check", "Activity"):
        assert not any(word in title for title in everything)


OPEN = UiState(channel_open=True, any_unpaused=True, has_missing=True)


@pytest.mark.parametrize(
    ("command", "ui", "expected"),
    [
        (MenuCommand.CHECK_NOW, UiState(), ItemState(enabled=False)),
        (MenuCommand.CHECK_NOW, OPEN, ItemState(enabled=True)),
        (MenuCommand.CHECK_NOW, UiState(channel_open=True, paused=True), ItemState(enabled=False)),
        (
            MenuCommand.CHECK_NOW,
            UiState(channel_open=True, checking=True),
            ItemState(enabled=False),
        ),
        (MenuCommand.CHECK_ALL, UiState(), ItemState(enabled=False)),
        (MenuCommand.CHECK_ALL, UiState(any_unpaused=True), ItemState(enabled=True)),
        (MenuCommand.MIRROR_MISSING, UiState(channel_open=True), ItemState(enabled=False)),
        (MenuCommand.MIRROR_MISSING, OPEN, ItemState(enabled=True)),
        (MenuCommand.TOGGLE_PAUSE, UiState(), ItemState(enabled=False, title="Pause Channel")),
        (MenuCommand.TOGGLE_PAUSE, OPEN, ItemState(enabled=True, title="Pause Channel")),
        (
            MenuCommand.TOGGLE_PAUSE,
            UiState(channel_open=True, paused=True),
            ItemState(enabled=True, title="Resume Channel"),
        ),
        (MenuCommand.OPEN_FOLDER, OPEN, ItemState(enabled=True)),
        (
            MenuCommand.OPEN_FOLDER,
            UiState(channel_open=True, folder_available=False),
            ItemState(enabled=False),
        ),
        (MenuCommand.VIEW_LIST, UiState(), ItemState(enabled=False, checked=True)),
        (MenuCommand.VIEW_GRID, OPEN, ItemState(enabled=True, checked=False)),
        (
            MenuCommand.VIEW_GRID,
            UiState(channel_open=True, view=ViewKind.GRID),
            ItemState(enabled=True, checked=True),
        ),
        (MenuCommand.ADD_CHANNEL, UiState(), ItemState(enabled=True)),
        (MenuCommand.SHOW_DOWNLOADS, UiState(), ItemState(enabled=True)),
        (MenuCommand.SHORTCUTS, UiState(), ItemState(enabled=True)),
        (MenuCommand.RELOAD, UiState(), ItemState(enabled=True)),
    ],
)
def test_an_item_is_enabled_only_when_it_applies(
    command: MenuCommand, ui: UiState, expected: ItemState
) -> None:
    """R-NA-04: the Channel menu needs an open channel; "Pause Channel" reads "Resume Channel"."""
    assert item_state(command, ui) == expected


def test_every_command_has_a_rule() -> None:
    """R-NA-04: no command of the menu bar is left without a rule."""
    for command in MenuCommand:
        assert isinstance(item_state(command, UiState()), ItemState)
