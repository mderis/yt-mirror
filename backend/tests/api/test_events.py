"""Tests of the event stream."""

import json
import threading
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import PORT, TOKEN, Api, new_world, services_around
from tests.fixtures.builders import make_toolchain, tool_box_with
from tests.fixtures.fakes.clock import FakeClock
from tests.fixtures.world import SMALL_ID, World, channel_file
from ytmirror.api import sse
from ytmirror.api.app import ApiConfig, create_app
from ytmirror.api.schemas import Tool
from ytmirror.api.security import SecurityPolicy
from ytmirror.core.channels import YouTubePause, YouTubePauseChanged
from ytmirror.core.errors import ErrorCode
from ytmirror.core.models import AppEvent, ToolName, ToolReport, ToolStatus, ToolUpdated
from ytmirror.services.events import EventBus, Listener
from ytmirror.services.toolchain import ToolchainService


class WatchedBus(EventBus):
    """An event bus that says when a stream has started to listen."""

    def __init__(self) -> None:
        """Start with nobody listening."""
        super().__init__()
        self.listening = threading.Event()

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        """Subscribe as usual and raise the flag."""
        leave = super().subscribe(listener)
        self.listening.set()
        return leave


class Stream:
    """One open event stream, read in a thread, and what arrived on it."""

    def __init__(self, client: TestClient, bus: WatchedBus) -> None:
        """Open the stream and wait until it listens."""
        self.status = 0
        self.content_type = ""
        self.text = ""
        # Others listen to the bus as well. Only a listener that comes from now on is the stream.
        bus.listening.clear()
        self._thread = threading.Thread(target=self._read, args=(client,))
        self._thread.start()
        assert bus.listening.wait(timeout=10), "the stream did not start to listen"

    def _read(self, client: TestClient) -> None:
        response = client.get("/api/events")
        self.status = response.status_code
        self.content_type = response.headers["content-type"]
        self.text = response.text

    def events(self) -> list[tuple[str, dict[str, object]]]:
        """Wait for the end of the stream and return its events: name and data."""
        self._thread.join(timeout=10)
        assert not self._thread.is_alive(), "the stream did not end"
        found: list[tuple[str, dict[str, object]]] = []
        for block in self.text.split("\n\n"):
            lines = dict(
                line.split(": ", maxsplit=1) for line in block.splitlines() if ": " in line
            )
            if "event" in lines:
                found.append((lines["event"], json.loads(lines["data"])))
        return found


@pytest.fixture
def bus() -> WatchedBus:
    """The event bus of the app under test."""
    return WatchedBus()


@pytest.fixture
def toolchain(bus: WatchedBus) -> ToolchainService:
    """A toolchain on a Mac where nothing was downloaded yet."""
    service = make_toolchain(tool_box=tool_box_with([]), events=bus)
    service.verify()
    return service


@pytest.fixture
def client(
    bus: WatchedBus,
    toolchain: ToolchainService,
    tmp_path: Path,
    frontend_dir: Path,
    clock: FakeClock,
) -> TestClient:
    """A signed-in client of the app."""
    services = services_around(tmp_path, toolchain, new_world(tmp_path, bus))
    config = ApiConfig(SecurityPolicy.for_local_server(TOKEN, PORT), frontend_dir)
    return Api(create_app(config, services, clock), frontend_dir).signed_in_client()


def test_a_change_of_a_tool_arrives_on_the_stream(client: TestClient, bus: WatchedBus) -> None:
    """R-FB-03: status changes appear in the interface without a manual refresh."""
    stream = Stream(client, bus)

    bus.publish(ToolUpdated(ToolReport(ToolName.DENO, ToolStatus.INSTALLING, progress=0.64)))
    bus.close()

    assert stream.events() == [
        (
            "tool.updated",
            {
                "tool": {
                    "name": "deno",
                    "status": "installing",
                    "version": None,
                    "source": None,
                    "progress": 0.64,
                    "error_code": None,
                    "installable": False,
                },
                "setup_required": True,
            },
        )
    ]
    assert stream.status == 200
    assert stream.content_type.startswith("text/event-stream")


def test_an_installation_is_followed_live_from_start_to_end(
    client: TestClient, bus: WatchedBus, toolchain: ToolchainService
) -> None:
    """R-IN-03: the download of a tool shows its progress in the first-run screen."""
    stream = Stream(client, bus)

    toolchain.start_install(ToolName.FFMPEG)
    toolchain.start_install(ToolName.DENO)
    bus.close()

    events = stream.events()
    ffmpeg = [data["tool"] for name, data in events if data["tool"]["name"] == "ffmpeg"]  # type: ignore[index]
    assert {name for name, _data in events} == {"tool.updated"}
    assert ffmpeg[0]["status"] == "installing"  # type: ignore[index]
    assert ffmpeg[0]["progress"] == 0.0  # type: ignore[index]
    assert ffmpeg[-1]["status"] == "ok"  # type: ignore[index]
    assert ffmpeg[-1]["source"] == "martin-riedl"  # type: ignore[index]
    assert [data["setup_required"] for _name, data in events][-1] is False


def test_when_the_app_stops_an_open_stream_ends(client: TestClient, bus: WatchedBus) -> None:
    """R-PL-13: an open window does not hold up the shutdown."""
    stream = Stream(client, bus)

    bus.close()

    assert stream.events() == []
    assert stream.text.startswith(": connected")


def test_a_stream_that_is_opened_while_the_app_stops_ends_at_once(
    client: TestClient, bus: WatchedBus
) -> None:
    """R-PL-13: nothing new starts to listen once the app is stopping."""
    bus.close()

    response = client.get("/api/events")

    assert response.status_code == 200
    assert "event:" not in response.text


def test_a_quiet_stream_is_kept_open_with_comment_lines(
    client: TestClient, bus: WatchedBus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-FB-03: the stream stays connected while nothing happens."""
    monkeypatch.setattr(sse, "KEEP_ALIVE_S", 0.05)
    stream = Stream(client, bus)
    seen = threading.Event()
    waited: list[AppEvent | None] = []
    bus.subscribe(waited.append)

    seen.wait(timeout=0.4)
    bus.close()
    stream.events()

    assert ": keep-alive" in stream.text


def test_one_event_is_one_name_line_and_one_data_line() -> None:
    """R-FB-03: events are written in the wire format of Server-Sent Events."""
    tool = Tool.of(ToolReport(ToolName.DENO, ToolStatus.OK, version="2.9.8", source="deno"))

    text = sse.encode("tool.updated", tool)

    name_line, data_line, *rest = text.split("\n")
    assert name_line == "event: tool.updated"
    assert data_line.startswith("data: {")
    assert json.loads(data_line.removeprefix("data: "))["version"] == "2.9.8"
    assert rest == ["", ""]


def test_the_events_of_the_catalogue_arrive_on_the_stream(
    client: TestClient, bus: WatchedBus, tmp_path: Path
) -> None:
    """R-FB-03, R-CH-11: a channel that changes and the progress of its listing reach the window."""
    folder = tmp_path / "catalogue-world"
    folder.mkdir()
    world = World(folder, channel_file(videos=35), bus=bus)
    stream = Stream(client, bus)

    world.add_and_list()
    bus.close()

    events = stream.events()
    names = [name for name, _data in events]
    progress = [data["progress"] for name, data in events if name == "task.progress"]
    last_channel = [data["channel"] for name, data in events if name == "channel.updated"][-1]
    assert set(names) == {"channel.updated", "task.progress"}
    assert progress == [
        {"channel_id": SMALL_ID, "kind": "first_listing", "done": 0, "total": None},
        {"channel_id": SMALL_ID, "kind": "first_listing", "done": 30, "total": None},
    ]
    assert (last_channel["id"], last_channel["videos"], last_channel["status"]) == (  # type: ignore[index]
        SMALL_ID,
        35,
        "up_to_date",
    )
    assert last_channel["pictures"] > 0  # type: ignore[index, operator]


def test_the_pause_of_youtube_arrives_on_the_stream_as_a_banner(
    client: TestClient, bus: WatchedBus
) -> None:
    """R-ER-05, R-FB-04: the window hears at once when the app pauses and when it goes on."""
    stream = Stream(client, bus)

    bus.publish(YouTubePauseChanged(YouTubePause(ErrorCode.BOT_CHECK, 1794641000)))
    bus.publish(YouTubePauseChanged(None))
    bus.close()

    assert stream.events() == [
        ("banner.changed", {"youtube_pause": {"code": "BOT_CHECK", "until": 1794641000}}),
        ("banner.changed", {"youtube_pause": None}),
    ]
