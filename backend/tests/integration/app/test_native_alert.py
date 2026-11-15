"""The real alert of ``MacNativeApp.show_alert``, in a child process of the test.

The alert is modal: a timer in the child closes it after half a second, as a
user would. The child is started by the test and ended by its own timeout.
"""

import subprocess
import sys

import pytest

pytestmark = pytest.mark.window

CHILD = """
import Foundation, AppKit
from ytmirror.adapters.native_app_mac import MacNativeApp

class Closer(Foundation.NSObject):
    def close_(self, _timer):
        AppKit.NSApp.abortModal()

closer = Closer.alloc().init()
timer = Foundation.NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
    0.5, closer, "close:", None, False
)
Foundation.NSRunLoop.currentRunLoop().addTimer_forMode_(timer, AppKit.NSModalPanelRunLoopMode)
MacNativeApp().show_alert("yt-mirror could not update its database", "A test of the alert.")
print("closed")
"""


def test_the_alert_shows_and_returns_when_it_is_closed() -> None:
    """R-QA-07: the message of a failed database update is a real alert of macOS."""
    done = subprocess.run(
        [sys.executable, "-c", CHILD], capture_output=True, text=True, timeout=30, check=False
    )

    assert (done.returncode, done.stdout.strip()) == (0, "closed"), done.stderr
