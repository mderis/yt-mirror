# ruff: noqa
# Temporary: the experiment of open question Q-24. Removed again once it has run on macOS 15.
"""Q-24 throwaway experiment: build the bundle, run every check, print a report.

Usage: run_checks.py <python with pywebview> <site-packages> <icon.svg> <work folder>

Environment:
  Q24_SCREENSHOTS=1  also save screenshots of the whole screen (CI only)
  Q24_REAL_KEYS=1    also press shortcuts through System Events (CI only)
"""

import json
import os
import platform
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PYTHON, SITE, ICON_SVG, WORK = sys.argv[1], sys.argv[2], sys.argv[3], Path(sys.argv[4]).resolve()
NAME = "yt-mirror"
BUNDLE_ID = "io.github.mderis.yt-mirror.q24"
APP = WORK / f"{NAME}.app"
DATA = WORK / "data"
LAUNCH = APP / "Contents" / "MacOS" / "launch"
results: list[tuple[str, str, bool, str]] = []
WINDOW = "[w for w in app.windows() if str(w.title())][-1]"
WINDOW_INFO = (
    "(lambda w: dict(active=bool(app.isActive()), hidden=bool(app.isHidden()),"
    " mini=bool(w.isMiniaturized()), key=bool(w.isKeyWindow()),"
    " width=[int(i['kCGWindowBounds']['Width']) for i in"
    " __import__('Quartz').CGWindowListCopyWindowInfo(8, w.windowNumber())]))(" + WINDOW + ")"
)
FIELD = (
    'JSON.stringify({v:document.getElementById("field").value,'
    's:document.getElementById("field").selectionStart,'
    'e:document.getElementById("field").selectionEnd,load:window.loadId})'
)


def record(point: str, name: str, ok: bool, detail: object = "") -> None:
    results.append((point, name, bool(ok), str(detail)))
    print(f"[{'PASS' if ok else 'FAIL'}] ({point}) {name}: {detail}", flush=True)


def run(*command: str, **kwargs: object) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=60, **kwargs)  # type: ignore[call-overload]
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(command, 124, "", "timed out")


def control(path: str, **query: str) -> object:
    port = json.loads((DATA / "control.json").read_text())["port"]
    url = f"http://127.0.0.1:{port}{path}"
    if query:
        url += "?" + urllib.parse.urlencode(query)
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
        return json.loads(response.read())


def state() -> dict:
    return control("/state")  # type: ignore[return-value]


def evaluate(code: str) -> object:
    return control("/eval", code=code)


def js(code: str, window: int = -1) -> object:
    return control("/js", code=code, w=str(window))["value"]  # type: ignore[index]


def field(window: int = -1) -> dict:
    return json.loads(js(FIELD, window))  # type: ignore[arg-type]


def key(letter: str, mods: str = "cmd") -> None:
    control("/key", k=letter, mods=mods)
    time.sleep(0.4)


def wait_for(condition, seconds: float = 20.0) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        try:
            if condition():
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.2)
    return False


def app_pids() -> list[int]:
    found = run("/usr/bin/pgrep", "-f", str(HERE / "app.py")).stdout.split()
    return [int(pid) for pid in found]


def front_name() -> str:
    asn = run("/usr/bin/lsappinfo", "front").stdout.strip()
    return run("/usr/bin/lsappinfo", "info", "-only", "name", asn).stdout.strip()


def launch_services(pid: int) -> str:
    asn = run("/usr/bin/lsappinfo", "find", f"pid={pid}").stdout.strip()
    info = run("/usr/bin/lsappinfo", "info", "-only", "name,bundleid", asn).stdout
    return " ".join(info.split())


def start(route: str) -> bool:
    (DATA / "control.json").unlink(missing_ok=True)
    if route == "open":
        run("/usr/bin/open", str(APP))
    else:
        subprocess.Popen(  # noqa: S603
            [str(LAUNCH)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    up = wait_for(lambda: (DATA / "control.json").exists(), 40)
    time.sleep(2)
    return up


def bring_forward() -> bool:
    run("/usr/bin/open", str(APP))
    return wait_for(lambda: evaluate(WINDOW_INFO)["active"] and evaluate(WINDOW_INFO)["key"], 10)  # type: ignore[index]


def put_other_app_in_front() -> None:
    run("/usr/bin/open", "-a", "Finder")
    wait_for(lambda: "Finder" in front_name(), 10)
    time.sleep(0.5)


def quit_app() -> bool:
    control("/quit")
    return wait_for(lambda: not app_pids(), 15)


def screenshot(name: str) -> None:
    if os.environ.get("Q24_SCREENSHOTS"):
        run("/usr/sbin/screencapture", "-x", str(WORK / f"shot-{name}.png"))


def menu_titles(snapshot: dict) -> list[list[str]]:
    return [
        [item["title"] for item in top.get("items", []) if "title" in item]
        for top in snapshot["menu"]
    ]


def flat_items(snapshot: dict) -> dict[str, dict]:
    return {
        item["title"]: item
        for top in snapshot["menu"]
        for item in top.get("items", [])
        if "title" in item
    }


OURS = [
    ["Hide yt-mirror", "Hide Others", "Show All", "Quit yt-mirror"],
    ["Add Channel...", "Close Window"],
    ["Undo", "Redo", "Cut", "Copy", "Paste", "Select All"],
    ["Check Now", "Pause Channel"],
    ["Minimize", "Zoom"],
    ["yt-mirror Help"],
]
PYWEBVIEW_LEFTOVERS = ["About yt-mirror", "Services", "Enter Fullscreen"]


def check_identity(route: str) -> None:
    snapshot = state()
    pid = snapshot["pid"]
    record(
        "b",
        f"{route}: app name as the app itself sees it",
        snapshot["localized_name"] == NAME,
        snapshot["localized_name"],
    )
    record(
        "b",
        f"{route}: bundle identifier",
        snapshot["bundle_identifier"] == BUNDLE_ID,
        snapshot["bundle_identifier"],
    )
    record(
        "b", f"{route}: process name", snapshot["process_name"] == NAME, snapshot["process_name"]
    )
    services = launch_services(pid)
    record(
        "b",
        f"{route}: Launch Services record (Dock, app switcher)",
        f'"{NAME}"' in services and BUNDLE_ID in services,
        services,
    )
    comm = run("/bin/ps", "-c", "-o", "comm=", "-p", str(pid)).stdout.strip()
    record("b", f"{route}: name in the process list", comm == NAME, comm)
    record(
        "b",
        f"{route}: no process is called Python",
        "python"
        not in (snapshot["localized_name"] + snapshot["process_name"] + comm + services).lower(),
        "",
    )
    record(
        "b",
        f"{route}: the app has an icon image",
        bool(snapshot["icon_size"]),
        snapshot["icon_size"],
    )


def check_menu(label: str) -> None:
    snapshot = state()
    titles = menu_titles(snapshot)
    record(
        "a",
        f"{label}: six menus of our own, in order",
        len(titles) == 6
        and all(
            titles[i][: len(OURS[i])] == OURS[i] or all(t in titles[i] for t in OURS[i])
            for i in range(len(titles[:6]))
        ),
        [t[:4] for t in titles],
    )
    everything = [title for group in titles for title in group]
    left = [title for title in PYWEBVIEW_LEFTOVERS if title in everything]
    record("a", f"{label}: nothing left of pywebview's menus", not left, left or "none")
    extra = [title for i, group in enumerate(titles[:6]) for title in group if title not in OURS[i]]
    print(f"       items macOS adds by itself ({label}): {extra}", flush=True)


def check_text_shortcuts(label: str, window: int = -1) -> None:
    control("/pb_save")
    try:
        js(
            'document.getElementById("field").value=""; document.getElementById("field").focus(); document.execCommand("insertText", false, "hello world"); 1',
            window,
        )
        ok_front = bring_forward()
        record(
            "a",
            f"{label}: window is in front and has the keyboard",
            ok_front,
            evaluate(WINDOW_INFO),
        )
        key("a")
        now = field(window)
        record(
            "a",
            f"{label}: Cmd+A selects all in the text field",
            (now["s"], now["e"]) == (0, 11),
            now,
        )
        key("c")
        record("a", f"{label}: Cmd+C copies", control("/pb_is", text="hello world")["matches"], "")  # type: ignore[index]
        key("x")
        now = field(window)
        record(
            "a",
            f"{label}: Cmd+X cuts",
            now["v"] == "" and control("/pb_is", text="hello world")["matches"],
            now,
        )  # type: ignore[index]
        key("v")
        now = field(window)
        record("a", f"{label}: Cmd+V pastes", now["v"] == "hello world", now)
        key("a")
        key("x")
        before = field(window)
        key("z")
        now = field(window)
        record(
            "a",
            f"{label}: Cmd+Z undoes one step",
            before["v"] == "" and now["v"] == "hello world",
            now,
        )
        key("z", "cmd,shift")
        now = field(window)
        record("a", f"{label}: Shift+Cmd+Z redoes one step", now["v"] == "", now)
    finally:
        control("/pb_restore")


def check_custom_shortcuts(label: str, window: int = -1) -> None:
    bring_forward()
    load_before = field(window)["load"]
    fired_before = len(state()["fired"])
    key("n")
    key("r")
    fired = state()["fired"][fired_before:]
    record(
        "a",
        f"{label}: Cmd+N and Cmd+R reach our own menu items",
        fired == ["add_channel", "check_now"],
        fired,
    )
    record(
        "a", f"{label}: Cmd+R does not reload the page", field(window)["load"] == load_before, ""
    )


def check_enable_disable() -> None:
    bring_forward()
    control("/enable", cmd="check_now", on="0")
    fired_before = len(state()["fired"])
    key("r")
    picked = control("/pick", menu="Channel", item="Check Now")
    snapshot = state()
    record(
        "a",
        "a disabled item shows as disabled",
        flat_items(snapshot)["Check Now"]["enabled"] is False,
        picked,
    )
    record(
        "a",
        "a disabled item does nothing (shortcut and click)",
        len(snapshot["fired"]) == fired_before,
        snapshot["fired"][fired_before:],
    )
    control("/enable", cmd="check_now", on="1")
    key("r")
    snapshot = state()
    record(
        "a",
        "the item works again after it is enabled",
        flat_items(snapshot)["Check Now"]["enabled"] is True
        and len(snapshot["fired"]) == fired_before + 1,
        snapshot["fired"][fired_before:],
    )


def check_real_keys() -> None:
    if not os.environ.get("Q24_REAL_KEYS"):
        return
    bring_forward()
    fired_before = len(state()["fired"])
    done = run(
        "/usr/bin/osascript",
        "-e",
        'tell application "System Events" to keystroke "n" using command down',
    )
    time.sleep(1)
    fired = state()["fired"][fired_before:]
    if done.returncode != 0:
        print(
            f"       real key presses through System Events were not allowed here: {done.stderr.strip()}",
            flush=True,
        )
        return
    record(
        "a",
        "a real Cmd+N key press (System Events) reaches our menu item",
        fired == ["add_channel"],
        fired,
    )
    js(
        'document.getElementById("field").value=""; document.getElementById("field").focus(); document.execCommand("insertText", false, "real keys"); 1'
    )
    bring_forward()
    run(
        "/usr/bin/osascript",
        "-e",
        'tell application "System Events" to keystroke "a" using command down',
    )
    time.sleep(0.6)
    now = field()
    record(
        "a",
        "a real Cmd+A key press selects all in the text field",
        (now["s"], now["e"]) == (0, 9),
        now,
    )
    run(
        "/usr/bin/osascript",
        "-e",
        'tell application "System Events" to keystroke "x" using command down',
    )
    time.sleep(0.6)
    run(
        "/usr/bin/osascript",
        "-e",
        'tell application "System Events" to keystroke "z" using command down',
    )
    time.sleep(0.6)
    now = field()
    record("a", "real Cmd+X then Cmd+Z key presses cut and undo", now["v"] == "real keys", now)


def set_aside() -> bool:
    """Minimize the window. With Stage Manager the window is set aside instead."""
    control("/minimize")
    return wait_for(
        lambda: evaluate(WINDOW_INFO)["mini"] or max(evaluate(WINDOW_INFO)["width"] or [0]) < 300,
        10,
    )  # type: ignore[index]


def is_back() -> bool:
    info = evaluate(WINDOW_INFO)
    return bool(
        info["active"]
        and info["key"]
        and not info["mini"]
        and not info["hidden"]
        and max(info["width"] or [0]) >= 300
    )  # type: ignore[index]


def check_single_instance() -> None:
    first_pid = state()["pid"]
    for route in ("terminal", "open"):
        put_other_app_in_front()
        before = front_name()
        if route == "terminal":
            done = run(str(LAUNCH))
            detail = f"second start ended with code {done.returncode}"
        else:
            run("/usr/bin/open", str(APP))
            detail = "open returned"
        ok = wait_for(is_back, 10)
        record(
            "c",
            f"second start ({route}) with another app in front: the first window comes forward",
            ok and NAME in front_name(),
            f"front before: {before.split(' ASN')[0]}, after: {front_name().split(' ASN')[0]}, {detail}",
        )
        record(
            "c",
            f"second start ({route}): still one process, the first one",
            app_pids() == [first_pid],
            app_pids(),
        )

        took = set_aside()
        info = evaluate(WINDOW_INFO)
        put_other_app_in_front()
        if route == "terminal":
            run(str(LAUNCH))
        else:
            run("/usr/bin/open", str(APP))
        ok = wait_for(is_back, 10)
        how = "minimized to the Dock" if info["mini"] else "set aside by Stage Manager"  # type: ignore[index]
        record(
            "c",
            f"second start ({route}) with the window {how}: it is restored and in front",
            took and ok,
            evaluate(WINDOW_INFO),
        )

        control("/hide")
        wait_for(lambda: evaluate(WINDOW_INFO)["hidden"], 10)  # type: ignore[index]
        if route == "terminal":
            run(str(LAUNCH))
        else:
            run("/usr/bin/open", str(APP))
        ok = wait_for(is_back, 10)
        record(
            "c",
            f"second start ({route}) with the app hidden: it is shown and in front",
            ok,
            evaluate(WINDOW_INFO),
        )
    print(
        "       'open' on a running app sends the same reopen event as a click on its Dock icon.",
        flush=True,
    )


def check_icon() -> None:
    code = (
        "(lambda rep: [[round(c, 2) for c in (rep.colorAtX_y_(x, y).redComponent(),"
        " rep.colorAtX_y_(x, y).greenComponent(), rep.colorAtX_y_(x, y).blueComponent(),"
        " rep.colorAtX_y_(x, y).alphaComponent())] for x, y in ((253, 256), (60, 256), (2, 2))])"
        "(AppKit.NSBitmapImageRep.imageRepWithContentsOfFile_("
        + repr(str(WORK / f"{NAME}-icon-512.png"))
        + "))"
    )
    centre, side, corner = evaluate(code)  # type: ignore[misc]
    record(
        "b",
        "rendered icon: white play triangle in the centre",
        centre[:3] == [1.0, 1.0, 1.0] and centre[3] == 1.0,
        centre,
    )
    record(
        "b",
        "rendered icon: accent colour on the square",
        side[3] == 1.0 and abs(side[0] - 0.12) < 0.05 and abs(side[2] - 0.82) < 0.05,
        side,
    )
    record("b", "rendered icon: transparent outside the rounded square", corner[3] == 0.0, corner)


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    print(f"macOS {platform.mac_ver()[0]} on {platform.machine()}", flush=True)
    built = run(
        PYTHON, str(HERE / "build_bundle.py"), "--out", str(APP), "--name", NAME,
        "--bundle-id", BUNDLE_ID, "--python", PYTHON, "--site", SITE,
        "--script", str(HERE / "app.py"), "--data", str(DATA), "--icon-svg", ICON_SVG,
    )  # fmt: skip
    record(
        "b",
        "the unsigned bundle is built locally",
        built.returncode == 0,
        built.stdout.strip() or built.stderr.strip(),
    )
    signed = run("/usr/bin/codesign", "-dv", str(APP))
    print(
        f"       codesign says: {signed.stderr.strip().splitlines()[0] if signed.stderr.strip() else signed.stdout.strip()}",
        flush=True,
    )

    # First launch, through Launch Services, as Finder or the Dock would.
    record("b", "open: the app starts", start("open"), "")
    print(
        f"       pywebview's own default menus before ours replaces them: {menu_titles({'menu': state()['facts']['pywebview_default_menu']})}",
        flush=True,
    )
    check_identity("open")
    check_icon()
    screenshot("1-open")
    check_menu("first launch")
    check_text_shortcuts("first launch")
    check_custom_shortcuts("first launch")
    check_enable_disable()
    check_real_keys()
    screenshot("2-after-keys")

    # A second window is opened and the first one closed.
    control("/new_window", title="second window")
    wait_for(lambda: state()["facts"]["menu_installs"] >= 2, 15)
    time.sleep(1)
    control("/close_window", w="0")
    time.sleep(1.5)
    check_menu("window closed, another opened")
    check_text_shortcuts("window closed, another opened", window=1)
    check_custom_shortcuts("window closed, another opened", window=1)

    check_single_instance()
    screenshot("3-single-instance")

    # Quit as Cmd+Q does, then a second launch from a terminal, as ./start would.
    record("a", "Quit ends the app", quit_app(), "")
    log = (DATA / "app.log").read_text()
    print(
        f"       quit told the app first (NSApplicationWillTerminateNotification): {'received' in log}",
        flush=True,
    )
    record("b", "terminal: the app starts", start("terminal"), "")
    check_identity("terminal")
    check_menu("second launch")
    check_text_shortcuts("second launch")
    check_custom_shortcuts("second launch")
    screenshot("4-terminal")
    snapshot = state()
    print(
        f"       after a terminal start the app was in front by itself: {snapshot['active']}",
        flush=True,
    )
    control("/close_window", w="0")
    closed = wait_for(lambda: not app_pids(), 15)
    record(
        "a",
        "closing the window ends the app",
        closed and "the window loop ended" in (DATA / "app.log").read_text(),
        "",
    )

    # pywebview's own menu API, for comparison.
    os.environ["Q24_PYWEBVIEW_MENU"] = "1"
    start("terminal")
    del os.environ["Q24_PYWEBVIEW_MENU"]
    snapshot = state()
    items = flat_items(snapshot)
    bring_forward()
    key("r")
    print(
        "       pywebview's own menu API: "
        f"leftovers present: {[t for t in PYWEBVIEW_LEFTOVERS if t in items]}, "
        f"shortcut of its custom item: {items['Check Now']['key']!r}, "
        f"Cmd+R reached the item: {state()['fired'] == ['check_now']}, "
        f"Undo in its Edit menu: {'Undo' in items}",
        flush=True,
    )
    control("/close_window", w="0")
    wait_for(lambda: not app_pids(), 15)

    failed = [result for result in results if not result[2]]
    (WORK / "report.json").write_text(json.dumps(results, indent=1))
    for point, label in (
        ("a", "custom menus"),
        ("b", "appears as yt-mirror"),
        ("c", "single instance"),
    ):
        mine = [result for result in results if result[0] == point]
        bad = [result for result in mine if not result[2]]
        print(
            f"POINT ({point}) {label}: {len(mine) - len(bad)} of {len(mine)} checks passed",
            flush=True,
        )
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        for pid in app_pids():
            run("/bin/kill", str(pid))
    sys.exit(code)
