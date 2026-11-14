"""Contract of the FolderPicker port, run against the fake and the real adapter.

The real adapter is given a stand-in for pywebview: a real dialog needs a
real click. That the real dialog returns the chosen folder was checked by
hand (open question Q-09).
"""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.fixtures.fakes.folder_picker import FakeFolderPicker
from ytmirror.adapters.folder_picker_webview import WebviewFolderPicker
from ytmirror.ports.folder_picker import FolderPicker

FOLDER_DIALOG = 20


class StandInWindow:
    """A window whose folder dialog returns what a test tells it."""

    def __init__(self, returns: object) -> None:
        """Remember what the dialog returns."""
        self.returns = returns
        self.calls: list[tuple[object, str]] = []

    def create_file_dialog(self, dialog_type: object, directory: str = "") -> object:
        """Record the call and return the configured value."""
        self.calls.append((dialog_type, directory))
        return self.returns


def webview_with(*windows: StandInWindow) -> Any:
    """Return a stand-in for the pywebview module with the given windows."""
    return SimpleNamespace(windows=list(windows), FileDialog=SimpleNamespace(FOLDER=FOLDER_DIALOG))


def picker(kind: str, *, has_window: bool, answer: Path | None) -> FolderPicker:
    """Return the fake or the real picker in the described situation."""
    if kind == "fake":
        return FakeFolderPicker(has_window=has_window, answer=answer)
    window = StandInWindow((str(answer),) if answer is not None else None)
    module = webview_with(window) if has_window else webview_with()
    return WebviewFolderPicker(lambda: module)


@pytest.mark.parametrize("kind", ["fake", "webview"])
def test_the_chosen_folder_is_returned(kind: str, tmp_path: Path) -> None:
    """R-CH-05: the folder the user chooses in the dialog is the folder the app gets."""
    subject = picker(kind, has_window=True, answer=tmp_path / "Chosen")

    assert subject.available() is True
    assert subject.choose(tmp_path) == tmp_path / "Chosen"


@pytest.mark.parametrize("kind", ["fake", "webview"])
def test_cancel_returns_nothing(kind: str, tmp_path: Path) -> None:
    """R-CH-05: a cancelled dialog chooses nothing."""
    subject = picker(kind, has_window=True, answer=None)

    assert subject.choose(tmp_path) is None


@pytest.mark.parametrize("kind", ["fake", "webview"])
def test_without_a_window_there_is_no_dialog(kind: str) -> None:
    """R-CH-05: with --browser and in tests there is no window, so no folder can be chosen."""
    subject = picker(kind, has_window=False, answer=Path("/never"))

    assert subject.available() is False
    assert subject.choose(None) is None


def test_the_dialog_is_a_folder_dialog_that_opens_in_the_given_folder(tmp_path: Path) -> None:
    """R-CH-05: the dialog chooses folders, and starts where the app tells it."""
    window = StandInWindow((str(tmp_path / "Chosen"),))
    subject = WebviewFolderPicker(lambda: webview_with(window, StandInWindow(None)))

    subject.choose(tmp_path)
    subject.choose(None)

    assert window.calls == [(FOLDER_DIALOG, str(tmp_path)), (FOLDER_DIALOG, "")]


@pytest.mark.parametrize(
    ("returned", "expected"),
    [
        (["/Users/someone/Movies"], Path("/Users/someone/Movies")),
        ("/Users/someone/Movies", Path("/Users/someone/Movies")),
        ((), None),
        ("", None),
        ([""], None),
        ([None], None),
        (None, None),
    ],
)
def test_every_form_of_answer_of_the_dialog_is_understood(
    returned: object, expected: Path | None
) -> None:
    """R-CH-05: a list with the folder is a choice, everything empty is Cancel."""
    subject = WebviewFolderPicker(lambda: webview_with(StandInWindow(returned)))

    assert subject.choose(None) == expected


def test_a_run_that_never_loaded_the_window_library_has_no_dialog() -> None:
    """R-NA-08: asking for the dialog never loads the window library by itself."""
    subject = WebviewFolderPicker(lambda: None)

    assert subject.available() is False
    assert subject.choose(None) is None


def test_by_default_the_picker_looks_for_the_loaded_window_library(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """infra: the real picker finds pywebview among the loaded modules, and only there."""
    monkeypatch.delitem(__import__("sys").modules, "webview", raising=False)
    assert WebviewFolderPicker().available() is False

    monkeypatch.setitem(__import__("sys").modules, "webview", webview_with(StandInWindow(None)))
    assert WebviewFolderPicker().available() is True
