"""A folder dialog that answers what a test tells it. Fake of the FolderPicker port."""

from pathlib import Path


class FakeFolderPicker:
    """Plays the user in front of the dialog.

    Attributes:
        has_window: Whether the app has a window to show the dialog in.
        answer: The folder the user chooses, or None for Cancel.
        asked_from: The folders the dialog was opened in, in order.
    """

    def __init__(self, *, has_window: bool = True, answer: Path | None = None) -> None:
        """Start with a window and a user who cancels, unless told otherwise."""
        self.has_window = has_window
        self.answer = answer
        self.asked_from: list[Path | None] = []

    def available(self) -> bool:
        """Return whether there is a window."""
        return self.has_window

    def choose(self, start: Path | None) -> Path | None:
        """Return the configured answer. Without a window there is none."""
        if not self.has_window:
            return None
        self.asked_from.append(start)
        return self.answer
