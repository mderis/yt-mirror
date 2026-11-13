"""Tests of ``ytmirror.app.window``."""

from ytmirror.app.window import DEFAULT_SIZE, MINIMUM_SIZE, WINDOW_TITLE, open_window


class FakeWebview:
    """Records what the app asks of pywebview."""

    def __init__(self) -> None:
        """Start with the setting pywebview has by default."""
        self.settings: dict[str, object] = {"OPEN_DEVTOOLS_IN_DEBUG": True}
        self.windows: list[dict[str, object]] = []
        self.started_with_debug: bool | None = None

    def create_window(
        self, title: str, url: str, *, width: int, height: int, min_size: tuple[int, int]
    ) -> object:
        """Remember the window."""
        self.windows.append(
            {"title": title, "url": url, "width": width, "height": height, "min_size": min_size}
        )
        return object()

    def start(self, *, debug: bool) -> None:
        """Remember how the window loop was started."""
        self.started_with_debug = debug


def test_the_window_shows_the_app_address_under_the_app_name() -> None:
    """R-PL-02: the UI runs in a dedicated window."""
    webview = FakeWebview()

    open_window("http://127.0.0.1:5000/?token=t", debug=False, webview=webview)

    (window,) = webview.windows
    assert window["title"] == "yt-mirror" == WINDOW_TITLE
    assert window["url"] == "http://127.0.0.1:5000/?token=t"
    assert webview.started_with_debug is False


def test_the_window_cannot_be_made_smaller_than_1100_by_700() -> None:
    """R-PL-03: minimum window size 1100 x 700 points."""
    webview = FakeWebview()

    open_window("http://127.0.0.1:5000/", debug=False, webview=webview)

    (window,) = webview.windows
    assert window["min_size"] == (1100, 700) == MINIMUM_SIZE
    assert (window["width"], window["height"]) == DEFAULT_SIZE
    assert DEFAULT_SIZE[0] >= MINIMUM_SIZE[0]
    assert DEFAULT_SIZE[1] >= MINIMUM_SIZE[1]


def test_debug_makes_the_developer_tools_available_without_opening_them() -> None:
    """R-IN-06: ``./start --debug`` enables the developer tools in the window."""
    webview = FakeWebview()

    open_window("http://127.0.0.1:5000/", debug=True, webview=webview)

    assert webview.started_with_debug is True
    assert webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] is False
