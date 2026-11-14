# ruff: noqa
# Temporary: the experiment of open question Q-24, point (d), the quit path. Removed again once it has run on macOS 15.
"""Q-24 point (d), throwaway experiment: every way of quitting goes through one quit path.

Usage: run_quit_checks.py <python with pywebview> <site-packages> <icon.svg> <work folder>
"""

import os
import signal
import sqlite3
import sys
import time

import run_checks as base
from run_checks import APP, DATA, HERE, NAME, PYTHON, SITE, control, record, run, wait_for

LOG = DATA / "app.log"
SESSION = {"logout": "rlgo", "restart": "rrst", "shutdown": "rsdn"}


def alive(pid: int) -> bool:
    """True while the process runs. A process that has ended but was not collected yet is not alive."""
    status = run("/bin/ps", "-o", "stat=", "-p", str(pid)).stdout.strip()
    return bool(status) and not status.startswith("Z")


def fresh_start(route: str = "terminal") -> int:
    for pid in base.app_pids():
        run("/bin/kill", "-9", str(pid))
    time.sleep(0.5)
    for name in ("app.log", "work.db", "work.db-wal", "work.db-shm"):
        (DATA / name).unlink(missing_ok=True)
    assert base.start(route), "the app did not start"
    return int(base.state()["pid"])


def lines() -> list[str]:
    return [line.split(" ", 2)[2] for line in LOG.read_text().splitlines()]


def stamps() -> dict[str, float]:
    found: dict[str, float] = {}
    for line in LOG.read_text().splitlines():
        _pid, at, text = line.split(" ", 2)
        found.setdefault(text.split(" (")[0].split(":")[0], float(at))
    return found


def ticks() -> int:
    database = sqlite3.connect(f"file:{DATA / 'work.db'}?mode=ro", uri=True)
    try:
        return int(database.execute("SELECT count(*) FROM ticks").fetchone()[0])
    finally:
        database.close()


def do(way: str, pid: int) -> None:
    if way == "Cmd+Q":
        base.bring_forward()
        control("/key", k="q", mods="cmd")
    elif way == "Quit item in the app menu":
        try:
            control("/pick", menu=NAME, item=f"Quit {NAME}")
        except OSError:
            pass  # the app ended while it answered: that is the quit
    elif way == "Quit from the Dock (quit event from outside)":
        run(PYTHON, str(HERE / "dock_quit.py"), str(pid), SITE)
    elif way == "window close button":
        control("/perform_close")
    elif way == "Cmd+W":
        base.bring_forward()
        control("/key", k="w", mods="cmd")
    elif way == "Ctrl+C (SIGINT)":
        os.kill(pid, signal.SIGINT)
    elif way == "termination signal (SIGTERM)":
        os.kill(pid, signal.SIGTERM)
    elif way in SESSION:
        control("/send_quit_event", why=SESSION[way])
    elif way == "real Cmd+Q key press":
        base.bring_forward()
        run(
            "/usr/bin/osascript",
            "-e",
            'tell application "System Events" to keystroke "q" using command down',
        )
    elif way == "real Quit in the Dock icon's menu":
        script = (
            'tell application "System Events" to tell process "Dock"\n'
            f'  set tile to UI element "{NAME}" of list 1\n'
            '  perform action "AXShowMenu" of tile\n'
            "  delay 1\n"
            '  click menu item "Quit" of menu 1 of tile\n'
            "end tell"
        )
        done = run("/usr/bin/osascript", "-e", script)
        print(f"       Dock menu script: code {done.returncode} {done.stderr.strip()}", flush=True)
    else:
        raise ValueError(way)


def check_shutdown_ran(way: str, pid: int, label: str) -> None:
    ended = wait_for(lambda: not alive(pid), 20)
    log = lines()
    at = stamps()
    order = [
        "quit asked",
        "shutdown started",
        "worker stopped, database closed",
        "shutdown finished",
    ]
    present = all(any(line.startswith(step) for line in log) for step in order)
    in_order = present and all(at[a] <= at[b] for a, b in zip(order, order[1:], strict=False))
    took = at.get("shutdown finished", 0) - at.get("shutdown started", 0)
    asked = next((line for line in log if line.startswith("quit asked")), "no quit asked line")
    started = next((line for line in log if line.startswith("shutdown started")), "no shutdown")
    record("d", f"{way} ({label}): the process ended", ended, "")
    record(
        "d",
        f"{way} ({label}): our code ran first, in order, and had time ({took:.1f} s of work)",
        in_order and took >= 0.9,
        f"{asked} | {started}",
    )
    record(
        "d",
        f"{way} ({label}): the database was closed cleanly",
        present and not (DATA / "work.db-wal").exists() and ticks() > 0,
        f"{ticks()} rows, no write-ahead file left",
    )


def scenario(way: str) -> None:
    print(f"--- {way}", flush=True)
    session = way in SESSION
    pid = fresh_start()
    do(way, pid)
    check_shutdown_ran(way, pid, "nothing running")

    pid = fresh_start()
    control("/busy", on="1")
    do(way, pid)
    if session:
        check_shutdown_ran(
            way, pid, "downloads running: held only for the shutdown work, then goes on"
        )
        record(
            "d",
            f"{way}: not held back for a confirmation",
            not any("held for a confirmation" in line for line in lines()),
            "",
        )
        return
    time.sleep(2.5)
    before = ticks()
    time.sleep(1.0)
    state = control("/quit_state")
    record(
        "d",
        f"{way} (downloads running): the quit is held, the app and its worker keep running",
        alive(pid) and len(state["held"]) == 1 and state["shutdown"] is None and ticks() > before,
        f"held: {state['held']}",
    )  # type: ignore[index,arg-type]
    control("/confirm_quit")
    check_shutdown_ran(way, pid, "after the confirmation")


def main() -> int:
    ways = [
        "Cmd+Q",
        "Quit item in the app menu",
        "Quit from the Dock (quit event from outside)",
        "window close button",
        "Cmd+W",
        "Ctrl+C (SIGINT)",
        "termination signal (SIGTERM)",
    ]
    if os.environ.get("Q24_REAL_KEYS"):
        ways += ["real Cmd+Q key press", "real Quit in the Dock icon's menu"]
    only = os.environ.get("Q24_ONLY")
    if not APP.exists():
        built = run(
            PYTHON, str(HERE / "build_bundle.py"), "--out", str(APP), "--name", NAME,
            "--bundle-id", base.BUNDLE_ID, "--python", PYTHON, "--site", SITE,
            "--script", str(HERE / "app.py"), "--data", str(DATA), "--icon-svg", base.ICON_SVG,
        )  # fmt: skip
        print(built.stdout.strip() or built.stderr.strip(), flush=True)
    for way in ways:
        if only and only not in way:
            continue
        try:
            scenario(way)
        except Exception as error:  # noqa: BLE001
            record("d", f"{way}: the scenario ran", False, repr(error))
    if not only:
        print("--- the quit event of a logout, sent by the app to itself", flush=True)
        fresh_start()
        control("/send_quit_event", why="rlgo")
        time.sleep(1.5)
        record(
            "d",
            "a quit event with the reason 'logout' makes AppKit announce the end of the session (NSWorkspaceWillPowerOffNotification)",
            any("NSWorkspaceWillPowerOffNotification" in line for line in lines()),
            "a real logout is tested separately",
        )
    mine = [result for result in base.results if result[0] == "d"]
    bad = [result for result in mine if not result[2]]
    print(f"POINT (d) quit path: {len(mine) - len(bad)} of {len(mine)} checks passed", flush=True)
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        for pid in base.app_pids():
            run("/bin/kill", "-9", str(pid))
    sys.exit(code)
