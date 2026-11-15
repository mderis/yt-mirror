"""The ChildProcesses port: the programs this app started and still runs.

When the app quits, a download may be in the middle of an ffmpeg step. That
ffmpeg is stopped, so that the job ends and cleans up before the app exits
(R-PL-13, R-QA-06). Only a child process of the app itself whose program is
one of the app's own tools is ever stopped.

Tests: backend/tests/integration/test_child_processes.py
"""

from collections.abc import Collection
from pathlib import Path
from typing import Protocol


class ChildProcesses(Protocol):
    """Stops programs that this app started."""

    def stop(self, programs: Collection[Path], wait_s: float) -> list[int]:
        """Stop the child processes of this app that run one of these programs.

        Each is asked to end, and killed when it has not ended after ``wait_s``.
        A child that runs another program is never touched.

        Args:
            programs: The programs, for example the ffmpeg of the app folder.
            wait_s: How long a process may take to end before it is killed.

        Returns:
            The process IDs that were stopped.
        """
        ...
