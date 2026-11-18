"""The shapes of the bridge between the interface and the app window (D-094).

The state the interface reports for the menu bar, and the events the window
sends it: a command of the menu bar and the quit question (R-NA-04, R-QU-12).

Tests: backend/tests/api/test_ui.py
"""

from pydantic import BaseModel, ConfigDict

from ytmirror.core.models import MenuCommand, UiState, ViewKind


class UiStateRequest(BaseModel):
    """What the interface tells the app about itself, for the menu bar (R-NA-04)."""

    model_config = ConfigDict(extra="forbid")

    channel_open: bool
    paused: bool
    checking: bool
    has_missing: bool
    folder_available: bool
    view: ViewKind
    any_unpaused: bool

    def to_state(self) -> UiState:
        """Return the state as the services know it."""
        return UiState(
            channel_open=self.channel_open,
            paused=self.paused,
            checking=self.checking,
            has_missing=self.has_missing,
            folder_available=self.folder_available,
            view=self.view,
            any_unpaused=self.any_unpaused,
        )


class MenuCommandEvent(BaseModel):
    """Data of the event ``menu.command``: run the command of a menu item (D-094)."""

    command: MenuCommand


class QuitAskedEvent(BaseModel):
    """Data of the event ``quit.asked``: a quit waits while downloads run; ask (R-QU-12)."""
