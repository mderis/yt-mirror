# ruff: noqa
# Temporary: the experiment of open question Q-24, point (d), the quit path. Removed again once it has run on macOS 15.
"""Q-24 throwaway experiment: a small pywebview app with an AppKit menu bar.

It shows one window, replaces pywebview's menus with its own through public
AppKit calls, allows one instance per data folder, and answers questions about
its own state over a local control port so that a script can check it.
"""

import fcntl
import json
import os
import signal
import sqlite3
import subprocess
import time
import sys
import threading
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

DATA = Path(os.environ["Q24_DATA"])
BUNDLE = os.environ.get("Q24_BUNDLE", "")
NAME = os.environ.get("Q24_NAME", "yt-mirror")
DATA.mkdir(parents=True, exist_ok=True)


def log(message: str) -> None:
    with (DATA / "app.log").open("a") as handle:
        handle.write(f"[{os.getpid()}] {__import__('time').time():.2f} {message}\n")


# --- One instance per data folder. Decided before AppKit is loaded, so a second
# --- start never shows a second Dock icon.
_lock = (DATA / "instance.lock").open("a+")
try:
    fcntl.flock(_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    first = json.loads((DATA / "instance.json").read_text())
    how = os.environ.get("Q24_FOCUS", "open")
    outcome: dict[str, object] = {"second_pid": os.getpid(), "first": first, "how": how}
    if how == "open":
        done = subprocess.run(["/usr/bin/open", first["bundle"]], capture_output=True, text=True)
        outcome["open_returncode"] = done.returncode
        outcome["open_stderr"] = done.stderr
    else:
        import AppKit as _AppKit

        running = _AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(
            first["pid"]
        )
        outcome["activate_returned"] = bool(
            running.activateWithOptions_(_AppKit.NSApplicationActivateAllWindows)
        )
    (DATA / "second_start.json").write_text(json.dumps(outcome))
    log(f"second start: asked the first instance to come forward ({how})")
    sys.exit(0)

if os.environ.get("Q24_SITE"):
    import site

    site.addsitedir(os.environ["Q24_SITE"])

import AppKit  # noqa: E402
import Foundation  # noqa: E402
import webview  # noqa: E402
from PyObjCTools import AppHelper  # noqa: E402

CMD = AppKit.NSEventModifierFlagCommand
OPT = AppKit.NSEventModifierFlagOption
SHIFT = AppKit.NSEventModifierFlagShift
SEP = None

# The menu bar as data: (title, action, key, modifiers). An action that ends in
# ":" is a standard AppKit action sent along the responder chain. Any other
# action is one of our own commands.
MENU_BAR = [
    (
        NAME,
        [
            (f"Hide {NAME}", "hide:", "h", CMD),
            ("Hide Others", "hideOtherApplications:", "h", CMD | OPT),
            ("Show All", "unhideAllApplications:", "", 0),
            SEP,
            (f"Quit {NAME}", "terminate:", "q", CMD),
        ],
    ),
    (
        "File",
        [
            ("Add Channel...", "add_channel", "n", CMD),
            ("Close Window", "performClose:", "w", CMD),
        ],
    ),
    (
        "Edit",
        [
            ("Undo", "undo:", "z", CMD),
            ("Redo", "redo:", "Z", CMD),
            SEP,
            ("Cut", "cut:", "x", CMD),
            ("Copy", "copy:", "c", CMD),
            ("Paste", "paste:", "v", CMD),
            ("Select All", "selectAll:", "a", CMD),
        ],
    ),
    (
        "Channel",
        [
            ("Check Now", "check_now", "r", CMD),
            ("Pause Channel", "pause_channel", "", 0),
        ],
    ),
    (
        "Window",
        [
            ("Minimize", "performMiniaturize:", "m", CMD),
            ("Zoom", "performZoom:", "", 0),
        ],
    ),
    ("Help", [(f"{NAME} Help", "help", "", 0)]),
]

fired: list[str] = []
disabled: set[str] = set()
activations = {"count": 0}
facts: dict[str, object] = {}
saved_pasteboard: list[dict[str, object]] = []


class MenuTarget(AppKit.NSObject):
    """Receives our own menu commands and says which of them are enabled."""

    def menuAction_(self, sender):  # noqa: N802
        fired.append(str(sender.representedObject()))

    def validateMenuItem_(self, item):  # noqa: N802
        return str(item.representedObject()) not in disabled


menu_target = MenuTarget.alloc().init()


def dump_menu(menu) -> list[dict[str, object]]:
    if menu is None:
        return []
    menu.update()
    items = []
    for item in menu.itemArray():
        entry: dict[str, object] = {"title": str(item.title())}
        if item.isSeparatorItem():
            entry = {"separator": True}
        else:
            entry["action"] = str(item.action()) if item.action() else None
            entry["key"] = str(item.keyEquivalent())
            entry["mods"] = int(item.keyEquivalentModifierMask())
            entry["enabled"] = bool(item.isEnabled())
            if item.representedObject() is not None:
                entry["command"] = str(item.representedObject())
            if item.hasSubmenu():
                entry["items"] = dump_menu(item.submenu())
        items.append(entry)
    return items


def install_menu_bar() -> None:
    """Replace whatever main menu exists with ours. Main thread only."""
    app = AppKit.NSApplication.sharedApplication()
    if "pywebview_default_menu" not in facts:
        facts["pywebview_default_menu"] = dump_menu(app.mainMenu())
    main_menu = AppKit.NSMenu.alloc().init()
    for title, entries in MENU_BAR:
        top = AppKit.NSMenuItem.alloc().init()
        submenu = AppKit.NSMenu.alloc().initWithTitle_(title)
        for entry in entries:
            if entry is SEP:
                submenu.addItem_(AppKit.NSMenuItem.separatorItem())
                continue
            item_title, action, key, mods = entry
            if action.endswith(":"):
                item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                    item_title, action, key
                )
            else:
                item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                    item_title, "menuAction:", key
                )
                item.setTarget_(menu_target)
                item.setRepresentedObject_(action)
            if key:
                item.setKeyEquivalentModifierMask_(mods)
            submenu.addItem_(item)
        top.setSubmenu_(submenu)
        main_menu.addItem_(top)
        if title == "Window":
            app.setWindowsMenu_(submenu)
        if title == "Help":
            app.setHelpMenu_(submenu)
    app.setMainMenu_(main_menu)
    facts["menu_installs"] = int(facts.get("menu_installs", 0)) + 1


def on_main(function):
    """Run a function on the main thread and return its result."""
    done = threading.Event()
    box: dict[str, object] = {}

    def run() -> None:
        try:
            box["value"] = function()
        except Exception:  # noqa: BLE001
            box["error"] = traceback.format_exc()
        done.set()

    AppHelper.callAfter(run)
    if not done.wait(15):
        return {"error": "main thread did not answer"}
    return box.get("value", box)


KEYCODES = {
    "a": 0, "h": 4, "z": 6, "x": 7, "c": 8, "v": 9, "q": 12, "w": 13, "r": 15,
    "n": 45, "m": 46, ",": 43,
}  # fmt: skip


def send_key(key: str, mods: str) -> dict[str, object]:
    """Send one key press through the app's normal event path. Main thread only."""
    app = AppKit.NSApplication.sharedApplication()
    flags = 0
    names = [name for name in mods.split(",") if name]
    if "cmd" in names:
        flags |= CMD
    if "shift" in names:
        flags |= SHIFT
    if "opt" in names:
        flags |= OPT
    window = app.keyWindow() or app.mainWindow()
    number = window.windowNumber() if window else 0
    ignoring = key.upper() if "shift" in names else key
    now = Foundation.NSProcessInfo.processInfo().systemUptime()
    for kind in (AppKit.NSEventTypeKeyDown, AppKit.NSEventTypeKeyUp):
        event = AppKit.NSEvent.keyEventWithType_location_modifierFlags_timestamp_windowNumber_context_characters_charactersIgnoringModifiers_isARepeat_keyCode_(
            kind, Foundation.NSMakePoint(0, 0), flags, now, number, None, key, ignoring, False,
            KEYCODES[key],
        )  # fmt: skip
        app.sendEvent_(event)
    return {
        "sent": key,
        "mods": names,
        "had_key_window": app.keyWindow() is not None,
        "active": bool(app.isActive()),
    }


def pick(menu_title: str, item_title: str) -> dict[str, object]:
    """Choose a menu item the way a click on it would. Main thread only."""
    main_menu = AppKit.NSApplication.sharedApplication().mainMenu()
    for top in main_menu.itemArray():
        submenu = top.submenu()
        if submenu is not None and str(submenu.title()) == menu_title:
            submenu.update()
            index = submenu.indexOfItemWithTitle_(item_title)
            if index < 0:
                return {"error": "no such item"}
            enabled = bool(submenu.itemAtIndex_(index).isEnabled())
            submenu.performActionForItemAtIndex_(index)
            return {"picked": item_title, "was_enabled": enabled}
    return {"error": "no such menu"}


def state() -> dict[str, object]:
    app = AppKit.NSApplication.sharedApplication()
    bundle = AppKit.NSBundle.mainBundle()
    me = AppKit.NSRunningApplication.currentApplication()
    windows = [
        {
            "title": str(window.title()),
            "visible": bool(window.isVisible()),
            "miniaturized": bool(window.isMiniaturized()),
            "key": bool(window.isKeyWindow()),
        }
        for window in app.windows()
        if window.title()
    ]
    icon = app.applicationIconImage()
    return {
        "pid": os.getpid(),
        "localized_name": str(me.localizedName()),
        "bundle_identifier": str(bundle.bundleIdentifier()),
        "bundle_path": str(bundle.bundlePath()),
        "executable_path": str(bundle.executablePath()),
        "info_cfbundlename": str((bundle.infoDictionary() or {}).get("CFBundleName")),
        "process_name": str(Foundation.NSProcessInfo.processInfo().processName()),
        "sys_executable": sys.executable,
        "sys_prefix": sys.prefix,
        "active": bool(app.isActive()),
        "hidden": bool(app.isHidden()),
        "icon_size": [icon.size().width, icon.size().height] if icon else None,
        "windows": windows,
        "menu": dump_menu(app.mainMenu()),
        "fired": list(fired),
        "disabled": sorted(disabled),
        "activations": activations["count"],
        "facts": facts,
        "pywebview_version": getattr(webview, "__version__", "?"),
        "macos": str(Foundation.NSProcessInfo.processInfo().operatingSystemVersionString()),
    }


def pasteboard_save() -> int:
    saved_pasteboard.clear()
    board = AppKit.NSPasteboard.generalPasteboard()
    for item in board.pasteboardItems() or []:
        saved_pasteboard.append({str(kind): item.dataForType_(kind) for kind in item.types()})
    return len(saved_pasteboard)


def pasteboard_restore() -> int:
    board = AppKit.NSPasteboard.generalPasteboard()
    board.clearContents()
    items = []
    for saved in saved_pasteboard:
        item = AppKit.NSPasteboardItem.alloc().init()
        for kind, data in saved.items():
            if data is not None:
                item.setData_forType_(data, kind)
        items.append(item)
    if items:
        board.writeObjects_(items)
    return len(items)


def pasteboard_text() -> str | None:
    text = AppKit.NSPasteboard.generalPasteboard().stringForType_(AppKit.NSPasteboardTypeString)
    return None if text is None else str(text)


# --- The quit path -------------------------------------------------------------
# Every way of quitting ends in two functions of ours: on_closing() decides
# whether the quit may go on, and shutdown() does the work before the process
# ends. Only public calls: pywebview's "closing" event, AppKit's "will
# terminate" notification, NSApplication.terminate_, and Python's signal module.

quit_state: dict[str, object] = {
    "busy": False,  # stands in for "downloads are running"
    "approved": False,  # the user confirmed the quit
    "held": [],  # quits that were held back for a confirmation
    "shutdown": None,  # what started the shutdown work, once it ran
    "session_ending": False,
    "last_signal": None,
}
shutdown_lock = threading.Lock()
worker_stop = threading.Event()
worker_box: dict[str, threading.Thread] = {}
SESSION_REASONS = {"logo": "logout", "rlgo": "logout", "rest": "restart", "rrst": "restart",
                   "shut": "shutdown", "rsdn": "shutdown"}  # fmt: skip


def fourcc(text: str) -> int:
    return int.from_bytes(text.encode("ascii"), "big")


def start_worker() -> None:
    """A stand-in for a download worker that holds a database open."""

    def work() -> None:
        database = sqlite3.connect(DATA / "work.db")
        database.execute("PRAGMA journal_mode=WAL")
        database.execute("CREATE TABLE IF NOT EXISTS ticks (at REAL)")
        while not worker_stop.wait(0.2):
            database.execute("INSERT INTO ticks VALUES (?)", (time.time(),))
            database.commit()
        time.sleep(1.0)  # stopping a worker takes a moment
        database.close()
        log("worker stopped, database closed")

    worker_box["thread"] = threading.Thread(target=work)
    worker_box["thread"].start()


def shutdown(via: str) -> None:
    """Stop the worker and close the database. Runs once, whoever asks."""
    with shutdown_lock:
        if quit_state["shutdown"] is not None:
            log(f"shutdown asked again ({via}): already done")
            return
        quit_state["shutdown"] = via
        log(f"shutdown started ({via})")
        worker_stop.set()
        worker_box["thread"].join()
        log("shutdown finished")


def quit_reason() -> str:
    """Say what asked for the quit, from what AppKit and we know."""
    event = Foundation.NSAppleEventManager.sharedAppleEventManager().currentAppleEvent()
    if event is not None and event.eventID() == fourcc("quit"):
        why = event.attributeDescriptorForKeyword_(fourcc("why?"))
        code = why.enumCodeValue().to_bytes(4, "big").decode("ascii") if why is not None else ""
        if code in SESSION_REASONS:
            return SESSION_REASONS[code]
        return "quit event from outside (Dock menu)"
    if quit_state["last_signal"]:
        name = str(quit_state["last_signal"])
        quit_state["last_signal"] = None
        return f"signal {name}"
    current = AppKit.NSApplication.sharedApplication().currentEvent()
    if current is not None and current.type() == AppKit.NSEventTypeKeyDown:
        return f"shortcut Cmd+{str(current.charactersIgnoringModifiers()).upper()}"
    return "menu item or window button"


def on_closing() -> bool:
    """pywebview's closing event: for the window button and for every quit."""
    reason = quit_reason()
    log(f"quit asked: {reason}")
    if quit_state["approved"]:
        log("quit allowed: confirmed before")
        return True
    if reason in SESSION_REASONS.values() or quit_state["session_ending"]:
        log("the macOS session is ending: no confirmation, shutting down now")
        shutdown(f"closing event, {reason}")
        return True
    if quit_state["busy"]:
        quit_state["held"].append(reason)  # type: ignore[union-attr]
        log(f"quit held for a confirmation: {reason}")
        return False
    log("quit allowed")
    return True


def install_signal_handlers() -> None:
    """Send Ctrl+C and a termination signal into the same quit path. Main thread only."""
    if facts.get("signals_installed"):
        return
    facts["signals_installed"] = True
    read_end, write_end = os.pipe()
    os.set_blocking(write_end, False)
    signal.set_wakeup_fd(write_end, warn_on_full_buffer=False)
    for number in (signal.SIGINT, signal.SIGTERM):
        signal.signal(number, lambda *_: None)

    def watch() -> None:
        while True:
            data = os.read(read_end, 1)
            if not data:
                return
            quit_state["last_signal"] = signal.Signals(data[0]).name
            log(f"signal received: {quit_state['last_signal']}")
            AppHelper.callAfter(AppKit.NSApplication.sharedApplication().terminate_, None)

    threading.Thread(target=watch, daemon=True).start()


def send_quit_event_to_self(why: str) -> bool:
    """Send this app the quit event that macOS sends at logout, restart or shutdown."""
    target = Foundation.NSAppleEventDescriptor.currentProcessDescriptor()
    event = Foundation.NSAppleEventDescriptor.appleEventWithEventClass_eventID_targetDescriptor_returnID_transactionID_(
        fourcc("aevt"), fourcc("quit"), target, -1, 0
    )
    event.setAttributeDescriptor_forKeyword_(
        Foundation.NSAppleEventDescriptor.descriptorWithEnumCode_(fourcc(why)), fourcc("why?")
    )
    _reply, error = event.sendEventWithOptions_timeout_error_(1, 10.0, None)
    return error is None


def after_shown() -> None:
    install_menu_bar()
    install_signal_handlers()


PAGE = """
<!doctype html><html><head><meta charset="utf-8"><title>Q-24</title></head>
<body style="font: 16px -apple-system; padding: 24px">
<h1>Q-24 experiment</h1>
<p>This window belongs to the yt-mirror Q-24 experiment. It closes by itself.</p>
<input id="field" style="font-size:16px; width: 320px" placeholder="text field">
<script>window.loadId = String(Math.random());</script>
</body></html>
"""

windows: list[object] = []


def open_window(title: str) -> None:
    window = webview.create_window(title, html=PAGE, width=640, height=360, min_size=(400, 300))
    if not os.environ.get("Q24_PYWEBVIEW_MENU"):
        window.events.shown += lambda *_: AppHelper.callAfter(after_shown)
    window.events.closing += on_closing
    windows.append(window)


class Control(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # noqa: D102
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        query = {key: values[0] for key, values in urllib.parse.parse_qs(parsed.query).items()}
        app = AppKit.NSApplication.sharedApplication()
        try:
            match parsed.path:
                case "/state":
                    result = on_main(state)
                case "/key":
                    result = on_main(lambda: send_key(query["k"], query.get("mods", "")))
                case "/js":
                    result = {
                        "value": windows[int(query.get("w", "-1"))].evaluate_js(query["code"])
                    }
                case "/enable":
                    (disabled.discard if query["on"] == "1" else disabled.add)(query["cmd"])
                    result = {"disabled": sorted(disabled)}
                case "/pb_save":
                    result = on_main(pasteboard_save)
                case "/pb_restore":
                    result = on_main(pasteboard_restore)
                case "/pb_is":
                    result = {"matches": on_main(pasteboard_text) == query["text"]}
                case "/pick":
                    result = on_main(lambda: pick(query["menu"], query["item"]))
                case "/eval":
                    result = on_main(
                        lambda: eval(
                            query["code"],
                            {
                                "AppKit": AppKit,
                                "app": app,
                                "windows": windows,
                                "Foundation": Foundation,
                            },
                        )
                    )
                case "/busy":
                    quit_state["busy"] = query["on"] == "1"
                    result = {"busy": quit_state["busy"]}
                case "/quit_state":
                    result = dict(quit_state)
                case "/confirm_quit":
                    log("the user confirmed the quit")
                    quit_state["approved"] = True
                    windows[-1].destroy()
                    result = {"confirmed": True}
                case "/perform_close":
                    result = on_main(
                        lambda: [w for w in app.windows() if str(w.title())][-1].performClose_(None)
                    )
                case "/send_quit_event":
                    result = {"sent": on_main(lambda: send_quit_event_to_self(query["why"]))}
                case "/activate":
                    result = on_main(lambda: app.activateIgnoringOtherApps_(True))
                case "/minimize":
                    windows[-1].minimize()
                    result = {"minimized": True}
                case "/hide":
                    result = on_main(lambda: app.hide_(None))
                case "/new_window":
                    open_window(query.get("title", "second window"))
                    result = {"windows": len(windows)}
                case "/close_window":
                    windows[int(query.get("w", "0"))].destroy()
                    result = {"closed": True}
                case "/quit":
                    AppHelper.callAfter(app.terminate_, None)
                    result = {"quitting": True}
                case _:
                    result = {"error": "unknown"}
        except Exception:  # noqa: BLE001
            result = {"error": traceback.format_exc()}
        body = json.dumps(result, default=str).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    bundle_path = str(AppKit.NSBundle.mainBundle().bundlePath())
    (DATA / "instance.json").write_text(json.dumps({"pid": os.getpid(), "bundle": bundle_path}))
    server = HTTPServer(("127.0.0.1", 0), Control)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    (DATA / "control.json").write_text(
        json.dumps({"port": server.server_address[1], "pid": os.getpid()})
    )
    Foundation.NSNotificationCenter.defaultCenter().addObserverForName_object_queue_usingBlock_(
        AppKit.NSApplicationDidBecomeActiveNotification,
        None,
        None,
        lambda _note: activations.__setitem__("count", activations["count"] + 1),
    )
    Foundation.NSNotificationCenter.defaultCenter().addObserverForName_object_queue_usingBlock_(
        AppKit.NSApplicationWillTerminateNotification,
        None,
        None,
        lambda _note: (
            log("NSApplicationWillTerminateNotification received"),
            shutdown("will-terminate notification"),
        ),
    )
    AppKit.NSWorkspace.sharedWorkspace().notificationCenter().addObserverForName_object_queue_usingBlock_(
        AppKit.NSWorkspaceWillPowerOffNotification,
        None,
        None,
        lambda _note: (
            quit_state.__setitem__("session_ending", True),
            log("NSWorkspaceWillPowerOffNotification received"),
        ),
    )
    start_worker()
    open_window(NAME)
    log("starting the window")
    if os.environ.get("Q24_PYWEBVIEW_MENU"):
        from webview.menu import Menu, MenuAction

        webview.start(
            menu=[Menu("Channel", [MenuAction("Check Now", lambda: fired.append("check_now"))])]
        )
    else:
        webview.start()
    log("the window loop ended")
    shutdown("end of the window loop")
    (DATA / "control.json").unlink(missing_ok=True)
    log("main returned")


if __name__ == "__main__":
    main()
