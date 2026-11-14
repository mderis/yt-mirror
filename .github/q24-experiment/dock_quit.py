# ruff: noqa
# Temporary: the experiment of open question Q-24, point (d), the quit path. Removed again once it has run on macOS 15.
"""Ask a running app to quit the way the Dock's Quit item does: from outside, through AppKit."""

import site
import sys

site.addsitedir(sys.argv[2])
import AppKit

app = AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(int(sys.argv[1]))
print("terminate sent:", bool(app.terminate()))
