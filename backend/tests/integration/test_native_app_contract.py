"""Contract of the NativeApp port, run against the fake and against real AppKit.

The real adapter is used inside the test process, without a window and
without the app's loop: AppKit builds and reads menus and delivers
notifications without them. What needs a real window is in
backend/tests/integration/app/test_window_app.py.
"""

import importlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import pytest

from tests.fixtures.fakes.native_app import FakeNativeApp
from ytmirror.adapters.native_app_mac import MacNativeApp
from ytmirror.app.menus import menu_bar
from ytmirror.core.models import Menu, MenuAction, MenuItem, Shortcut
from ytmirror.ports.native_app import NativeApp


@dataclass
class Subject:
    """A NativeApp and the two things only a test does: turn the loop, end the app."""

    app: NativeApp
    turn_loop: Callable[[], None]
    end: Callable[[], None]


def _turn_the_real_loop() -> None:
    foundation: Any = importlib.import_module("Foundation")
    until: Any = foundation.NSDate.dateWithTimeIntervalSinceNow_(0.2)
    foundation.NSRunLoop.currentRunLoop().runUntilDate_(until)


def _announce_the_end() -> None:
    appkit: Any = importlib.import_module("AppKit")
    appkit.NSNotificationCenter.defaultCenter().postNotificationName_object_(
        appkit.NSApplicationWillTerminateNotification, None
    )


@pytest.fixture(params=["fake", "mac"])
def subject(request: pytest.FixtureRequest) -> Iterator[Subject]:
    """The fake, and the real adapter on the AppKit of this Mac."""
    if request.param == "fake":
        fake = FakeNativeApp()
        yield Subject(fake, fake.turn_loop, fake.end)
        return
    appkit: Any = importlib.import_module("AppKit")
    application: Any = appkit.NSApplication.sharedApplication()
    before: Any = application.mainMenu()
    mac = MacNativeApp()
    yield Subject(mac, _turn_the_real_loop, _announce_the_end)
    mac.stop_observing()
    application.setMainMenu_(before)


def ours(
    subject: Subject,
) -> list[tuple[str, list[tuple[str, MenuAction | None, Shortcut | None]]]]:
    """Return the shown menu bar reduced to the items that carry one of our actions."""
    return [
        (
            menu.title,
            [
                (item.title, item.action, item.shortcut)
                for item in menu.items
                if item.action is not None
            ],
        )
        for menu in subject.app.shown_menu_bar()
    ]


def test_the_menu_bar_is_exactly_what_was_given(subject: Subject) -> None:
    """R-NA-03: the menu bar has our menus, our items and our shortcuts, in order."""
    menus = menu_bar("yt-mirror")

    subject.app.show_menu_bar(menus)

    assert ours(subject) == [
        (
            menu.title,
            [(item.title, item.action, item.shortcut) for group in menu.groups for item in group],
        )
        for menu in menus
    ]


def test_a_new_menu_bar_replaces_the_old_one_completely(subject: Subject) -> None:
    """R-NA-03: nothing of an earlier menu bar stays behind."""
    subject.app.show_menu_bar(menu_bar("yt-mirror"))
    only = Menu("Edit", ((MenuItem("Copy", MenuAction.COPY, Shortcut("c")),),))

    subject.app.show_menu_bar([only])

    assert ours(subject) == [("Edit", [("Copy", MenuAction.COPY, Shortcut("c"))])]


def test_shift_and_option_are_part_of_a_shortcut(subject: Subject) -> None:
    """R-NA-03: Redo is Shift+Cmd+Z and Hide Others is Option+Cmd+H."""
    subject.app.show_menu_bar(menu_bar("yt-mirror"))

    shortcuts = {title: shortcut for _menu, items in ours(subject) for title, _a, shortcut in items}

    assert shortcuts["Redo"] == Shortcut("z", shift=True)
    assert shortcuts["Undo"] == Shortcut("z")
    assert shortcuts["Hide Others"] == Shortcut("h", option=True)
    assert shortcuts["Show All"] is None


def test_the_app_has_a_name_under_which_macos_knows_it(subject: Subject) -> None:
    """R-NA-01: the name macOS shows for the running app can be read."""
    identity = subject.app.identity()

    assert identity.name
    assert isinstance(identity.bundle_identifier, str)


def test_work_for_the_main_thread_runs_when_the_loop_turns(subject: Subject) -> None:
    """infra: an action handed to the main thread runs once the app's loop gets to it."""
    ran: list[str] = []

    subject.app.run_on_main_thread(lambda: ran.append("done"))
    subject.turn_loop()

    assert ran == ["done"]


def test_registered_work_runs_before_the_app_ends(subject: Subject) -> None:
    """R-PL-13: when macOS is about to end the app, our work runs first, each piece once."""
    ran: list[str] = []
    subject.app.on_will_terminate(lambda: ran.append("first"))
    subject.app.on_will_terminate(lambda: ran.append("second"))

    subject.end()

    assert sorted(ran) == ["first", "second"]


def test_work_that_returns_a_value_does_not_disturb_the_end_of_the_app(subject: Subject) -> None:
    """R-PL-13: the hook hands nothing back to macOS, whatever the work returns.

    A value handed back to AppKit makes it drop the event it was handling,
    which once stopped a logout (docs/DECISIONS.md D-052).
    """
    ran: list[str] = []

    def work() -> None:
        ran.append("done")
        return 42  # pyright: ignore[reportReturnType]  (the point of this test)

    subject.app.on_will_terminate(work)

    subject.end()

    assert ran == ["done"]
