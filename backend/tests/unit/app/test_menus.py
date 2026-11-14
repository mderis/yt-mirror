"""Tests of ``ytmirror.app.menus``."""

from ytmirror.app.menus import menu_bar
from ytmirror.core.models import MenuAction, Shortcut


def titles(app_name: str) -> dict[str, list[list[str]]]:
    """Return the titles of every menu, group by group."""
    return {
        menu.title: [[item.title for item in group] for group in menu.groups]
        for menu in menu_bar(app_name)
    }


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
    edit = menu_bar("yt-mirror")[1]

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


def test_no_item_exists_before_its_target_does() -> None:
    """infra: until M5 and M7 build their targets, there is no About, Settings or Help item."""
    everything = [item for menu in menu_bar("yt-mirror") for group in menu.groups for item in group]

    assert [menu.title for menu in menu_bar("yt-mirror")] == ["yt-mirror", "Edit"]
    assert not any(
        word in item.title for item in everything for word in ("About", "Settings", "Help")
    )
