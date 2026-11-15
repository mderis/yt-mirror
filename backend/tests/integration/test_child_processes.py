"""Tests of ``ytmirror.adapters.child_processes_mac``: the real processes of macOS.

Every process here is started by the test itself and stopped by its own ID.
"""

import subprocess
from pathlib import Path

from ytmirror.adapters.child_processes_mac import MacChildProcesses


def test_only_a_child_that_runs_one_of_the_programs_is_stopped(tmp_path: Path) -> None:
    """R-PL-13: at quit the app stops its own ffmpeg, and no other process."""
    ffmpeg = tmp_path / "ffmpeg"
    ffmpeg.symlink_to("/bin/sleep")
    ours = subprocess.Popen([str(ffmpeg), "30"])
    other = subprocess.Popen(["/bin/cat"], stdin=subprocess.PIPE)
    try:
        stopped = MacChildProcesses().stop([ffmpeg], wait_s=5)

        assert stopped == [ours.pid]
        assert ours.wait(5) is not None
        assert other.poll() is None
    finally:
        for process in (ours, other):
            if process.poll() is None:
                process.kill()
            process.wait(5)
        assert other.stdin is not None
        other.stdin.close()


def test_a_child_that_does_not_end_is_killed(tmp_path: Path) -> None:
    """R-PL-13: a program that ignores the request to end is killed after the wait."""
    script = "trap '' TERM; echo ready; while :; do sleep 0.05; done"
    shell = tmp_path / "ffmpeg"
    shell.symlink_to("/bin/bash")
    stubborn = subprocess.Popen([str(shell), "-c", script], stdout=subprocess.PIPE)
    assert stubborn.stdout is not None
    try:
        assert stubborn.stdout.readline() == b"ready\n"
        stopped = MacChildProcesses().stop([shell], wait_s=0.3)

        assert stopped == [stubborn.pid]
        assert stubborn.wait(5) == -9
    finally:
        if stubborn.poll() is None:
            stubborn.kill()
        stubborn.wait(5)
        stubborn.stdout.close()


def test_nothing_is_stopped_when_no_child_runs_the_programs(tmp_path: Path) -> None:
    """R-PL-13: without a running tool there is nothing to stop."""
    assert MacChildProcesses().stop([tmp_path / "ffmpeg"], wait_s=0.1) == []
