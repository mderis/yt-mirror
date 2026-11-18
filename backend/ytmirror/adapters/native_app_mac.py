"""The NativeApp port on macOS, through AppKit.

Implements the macOS side of R-NA-01, R-NA-03 and R-PL-13. The whole menu
bar is built here with AppKit, because the menu API of the window library
has no shortcuts, cannot disable an item, and always adds menus of its own
(docs/DECISIONS.md D-049). Only public calls of AppKit are used.

This module must not import the window library and must not know what the
menus mean: it draws what it is given.

Tests: backend/tests/integration/test_native_app_contract.py
"""

import importlib
from collections.abc import Callable, Sequence
from typing import Any

from ytmirror.core.models import (
    AppIdentity,
    ItemState,
    Menu,
    MenuAction,
    MenuCommand,
    MenuItem,
    Shortcut,
    ShownMenu,
    ShownMenuItem,
)

_SELECTORS: dict[MenuAction, str] = {
    MenuAction.COMMAND: "runCommand:",
    MenuAction.CLOSE_WINDOW: "performClose:",
    MenuAction.MINIMIZE: "performMiniaturize:",
    MenuAction.ZOOM: "performZoom:",
    MenuAction.HIDE: "hide:",
    MenuAction.HIDE_OTHERS: "hideOtherApplications:",
    MenuAction.SHOW_ALL: "unhideAllApplications:",
    MenuAction.QUIT: "terminate:",
    MenuAction.UNDO: "undo:",
    MenuAction.REDO: "redo:",
    MenuAction.CUT: "cut:",
    MenuAction.COPY: "copy:",
    MenuAction.PASTE: "paste:",
    MenuAction.SELECT_ALL: "selectAll:",
}
"""The standard AppKit action behind each menu action. AppKit sends it to whatever
has the keyboard, which is how Undo or Paste reach a text field of the web view."""

_ACTIONS: dict[str, MenuAction] = {selector: action for action, selector in _SELECTORS.items()}


def _four_char(code: str) -> int:
    """Return the number of a four-character code of Apple events, as 'why?'."""
    return int.from_bytes(code.encode("ascii"), "big")


_QUIT_REASON = _four_char("why?")
"""kAEQuitReason: the parameter of a quit request that says why it is sent."""
_SESSION_ENDS = frozenset(_four_char(code) for code in ("quia", "rlgo", "rest", "shut"))
"""kAEQuitAll, kAEReallyLogOut, kAERestart, kAEShutDown: a logout, a restart or a shutdown."""

_target_class: Any = None
"""The class of the object behind every command item. A class of the Objective-C
runtime can be registered only once per process, so it is made once."""


def _menu_target_class(appkit: Any) -> Any:
    global _target_class
    if _target_class is not None:
        return _target_class
    objc: Any = importlib.import_module("objc")

    class YTMMenuTarget(appkit.NSObject):  # type: ignore[misc]
        """Runs and validates the command items of the menu bar (D-094)."""

        state_of: Callable[[MenuCommand], ItemState] | None = None
        on_command: Callable[[MenuCommand], None] | None = None

        @objc.typedSelector(b"v@:@")
        def runCommand_(self, sender: Any) -> None:  # noqa: N802 - an Objective-C selector
            # Returns nothing, as every AppKit handler must (D-052).
            command = _command_of(sender)
            if command is not None and self.on_command is not None:
                self.on_command(command)

        @objc.typedSelector(b"Z@:@")
        def validateMenuItem_(self, item: Any) -> bool:  # noqa: N802 - an Objective-C selector
            command = _command_of(item)
            if command is None or self.state_of is None:
                return command is not None
            try:
                state = self.state_of(command)
            except Exception:  # noqa: BLE001 - an error inside AppKit would drop its event
                return False
            if state.title is not None:
                item.setTitle_(state.title)
            item.setState_(
                appkit.NSControlStateValueOn if state.checked else appkit.NSControlStateValueOff
            )
            return state.enabled

    _target_class = YTMMenuTarget
    return _target_class


def _command_of(item: Any) -> MenuCommand | None:
    value: Any = item.representedObject()
    try:
        return MenuCommand(str(value)) if value is not None else None
    except ValueError:
        return None


def _appkit() -> Any:
    """Return the AppKit module.

    pyobjc ships no type information, so its modules are handled as ``Any``.
    It is imported late: tests and ``--doctor`` must not need it.
    """
    return importlib.import_module("AppKit")


class MacNativeApp:
    """The running app as macOS sees it."""

    def __init__(self) -> None:
        """Create the adapter. Nothing is asked of macOS yet."""
        self._observers: list[Any] = []
        # A menu item holds its target weakly: the adapter keeps it alive.
        self._target: Any = None

    def identity(self) -> AppIdentity:
        """Return the name and the bundle identifier under which macOS knows this process."""
        appkit = _appkit()
        name: Any = appkit.NSRunningApplication.currentApplication().localizedName()
        identifier: Any = appkit.NSBundle.mainBundle().bundleIdentifier()
        return AppIdentity(name=str(name or ""), bundle_identifier=str(identifier or ""))

    def show_menu_bar(
        self,
        menus: Sequence[Menu],
        state_of: Callable[[MenuCommand], ItemState] | None = None,
        on_command: Callable[[MenuCommand], None] | None = None,
    ) -> None:
        """Replace the whole menu bar of the app. Call it on the main thread.

        Args:
            menus: The menus, from left to right. The first one is the app menu.
            state_of: Says whether a command item is enabled, its title and its check mark.
            on_command: Runs the command of a chosen item.
        """
        appkit = _appkit()
        target: Any = _menu_target_class(appkit).alloc().init()
        target.state_of = state_of
        target.on_command = on_command
        self._target = target
        app: Any = appkit.NSApplication.sharedApplication()
        bar: Any = appkit.NSMenu.alloc().init()
        roles: list[tuple[str, Any]] = []
        for menu in menus:
            holder: Any = appkit.NSMenuItem.alloc().init()
            submenu: Any = appkit.NSMenu.alloc().initWithTitle_(menu.title)
            for index, group in enumerate(menu.groups):
                if index > 0:
                    submenu.addItem_(appkit.NSMenuItem.separatorItem())
                for item in group:
                    submenu.addItem_(_native_item(appkit, item, target))
            holder.setSubmenu_(submenu)
            bar.addItem_(holder)
            if menu.role is not None:
                roles.append((menu.role, submenu))
        app.setMainMenu_(bar)
        for role, submenu in roles:
            # macOS fills these: the list of windows, and the search field of Help.
            if role == "window":
                app.setWindowsMenu_(submenu)
            elif role == "help":
                app.setHelpMenu_(submenu)

    def shown_menu_bar(self) -> tuple[ShownMenu, ...]:
        """Return the menu bar as it really is right now. Call it on the main thread."""
        appkit = _appkit()
        bar: Any = appkit.NSApplication.sharedApplication().mainMenu()
        if bar is None:
            return ()
        shown: list[ShownMenu] = []
        for holder in bar.itemArray():
            submenu: Any = holder.submenu()
            if submenu is None:
                continue
            # Lets AppKit decide now which items are enabled, as it does before showing a menu.
            submenu.update()
            items = tuple(
                _shown_item(appkit, item)
                for item in submenu.itemArray()
                if not item.isSeparatorItem()
            )
            shown.append(ShownMenu(title=str(submenu.title()), items=items))
        return tuple(shown)

    def run_on_main_thread(self, action: Callable[[], None]) -> None:
        """Run an action on the main thread, once the app's loop gets to it.

        Args:
            action: What to run.
        """
        helper: Any = importlib.import_module("PyObjCTools.AppHelper")
        helper.callAfter(action)

    def on_will_terminate(self, action: Callable[[], None]) -> None:
        """Run an action when macOS is about to end the app, before the process ends.

        Args:
            action: What to run.
        """
        appkit = _appkit()

        def handler(_notification: object) -> None:
            # A notification handler must return nothing. A returned value makes pyobjc
            # raise inside AppKit, and AppKit then drops the event it was handling: a
            # logout hung on exactly this (docs/DECISIONS.md D-052).
            action()

        center: Any = appkit.NSNotificationCenter.defaultCenter()
        observer: Any = center.addObserverForName_object_queue_usingBlock_(
            appkit.NSApplicationWillTerminateNotification, None, None, handler
        )
        self._observers.append(observer)

    def stop_observing(self) -> None:
        """Forget every action given to ``on_will_terminate``. For tests."""
        center: Any = _appkit().NSNotificationCenter.defaultCenter()
        for observer in self._observers:
            center.removeObserver_(observer)
        self._observers.clear()

    def request_quit(self) -> None:  # pragma: no cover
        """Ask the app to quit, exactly as "Quit" in its menu does. Main thread only.

        Not covered in this process: it ends the process. The window tests run it
        in a child process (backend/tests/integration/app/test_window_app.py).
        """
        _appkit().NSApplication.sharedApplication().terminate_(None)

    def ending_session(self) -> bool:
        """Tell whether the quit macOS asks for now comes from a logout, a restart or a shutdown.

        The quit request of macOS is an Apple event; its reason parameter says why.
        Cmd+Q and the menu send no Apple event, and Quit in the Dock sends one
        without a reason: neither is the end of a session.
        """
        foundation: Any = importlib.import_module("Foundation")
        event: Any = foundation.NSAppleEventManager.sharedAppleEventManager().currentAppleEvent()
        if event is None:
            return False
        reason: Any = event.paramDescriptorForKeyword_(_QUIT_REASON)
        if reason is None:
            reason = event.attributeDescriptorForKeyword_(_QUIT_REASON)
        return reason is not None and int(reason.enumCodeValue()) in _SESSION_ENDS

    def show_alert(self, title: str, text: str) -> None:
        """Show a message in a window of its own, and return when the user closed it.

        Args:
            title: What happened, in one sentence.
            text: What it means for the user's data, and what to do.
        """
        appkit = _appkit()
        app: Any = appkit.NSApplication.sharedApplication()
        app.setActivationPolicy_(appkit.NSApplicationActivationPolicyRegular)
        alert: Any = appkit.NSAlert.alloc().init()
        alert.setAlertStyle_(appkit.NSAlertStyleCritical)
        alert.setMessageText_(title)
        alert.setInformativeText_(text)
        alert.addButtonWithTitle_("Quit")
        app.activateIgnoringOtherApps_(True)
        alert.runModal()


def _native_item(appkit: Any, item: MenuItem, target: Any) -> Any:
    native: Any = appkit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        item.title, _SELECTORS[item.action], ""
    )
    if item.command is not None:
        native.setTarget_(target)
        native.setRepresentedObject_(item.command.value)
    if item.shortcut is not None:
        mask: int = appkit.NSEventModifierFlagCommand
        if item.shortcut.option:
            mask |= appkit.NSEventModifierFlagOption
        # AppKit reads an upper-case letter as "with Shift", as the standard menus do.
        key = item.shortcut.key.upper() if item.shortcut.shift else item.shortcut.key
        native.setKeyEquivalent_(key)
        native.setKeyEquivalentModifierMask_(mask)
    return native


def _shown_item(appkit: Any, item: Any) -> ShownMenuItem:
    selector: Any = item.action()
    key = str(item.keyEquivalent())
    shortcut: Shortcut | None = None
    if key:
        mask = int(item.keyEquivalentModifierMask())
        shortcut = Shortcut(
            key=key.lower(),
            shift=key != key.lower() or bool(mask & appkit.NSEventModifierFlagShift),
            option=bool(mask & appkit.NSEventModifierFlagOption),
        )
    return ShownMenuItem(
        title=str(item.title()),
        action=_ACTIONS.get(str(selector)) if selector else None,
        shortcut=shortcut,
        enabled=bool(item.isEnabled()),
        command=_command_of(item),
        checked=int(item.state()) == int(appkit.NSControlStateValueOn),
    )
