"""Tests of the bridge endpoints and events: the menu state, the commands and the quit question."""

import dataclasses
import threading
from pathlib import Path

from fastapi.testclient import TestClient

from tests.api.conftest import PORT, TOKEN, Api, make_services
from tests.fixtures.fakes.clock import FakeClock
from ytmirror.api.app import ApiConfig, create_app
from ytmirror.api.security import SecurityPolicy
from ytmirror.core.models import MenuCommand, MenuCommanded, UiState, ViewKind
from ytmirror.services.ui_bridge import UiBridge

STATE = {
    "channel_open": True,
    "paused": True,
    "checking": False,
    "has_missing": True,
    "folder_available": True,
    "view": "grid",
    "any_unpaused": False,
}


def test_the_interface_reports_its_state_for_the_menu_bar(api: Api) -> None:
    """R-NA-04, D-094: PUT /api/ui/state keeps what the menu bar is enabled from."""
    assert api.world is not None
    client = api.signed_in_client()

    answer = client.put("/api/ui/state", json=STATE)

    assert answer.status_code == 204
    assert api.world.ui.state() == UiState(
        channel_open=True, paused=True, has_missing=True, view=ViewKind.GRID
    )


def test_a_state_with_an_unknown_field_is_refused(api: Api) -> None:
    """R-NA-04: the report is checked, so a mistake of the interface shows."""
    client = api.signed_in_client()

    answer = client.put("/api/ui/state", json={**STATE, "extra": 1})

    assert answer.status_code == 422


def test_confirming_the_quit_asks_the_app_to_quit(api: Api) -> None:
    """R-QU-12: "Quit" in the question ends the app through the quit path."""
    assert api.world is not None
    quits: list[int] = []
    api.world.ui.on_quit(lambda: quits.append(1))
    client = api.signed_in_client()

    answer = client.post("/api/ui/quit")

    assert answer.status_code == 204
    assert quits == [1]


def test_menu_commands_and_the_quit_question_reach_the_window(
    tmp_path: Path, frontend_dir: Path, clock: FakeClock
) -> None:
    """R-QU-12, D-094: the stream carries the commands and the question, and counts as asked.

    An open stream is an interface that can be asked before a quit.
    """
    services = make_services(tmp_path)
    bridge = UiBridge(services.events, lambda: 1)
    services = dataclasses.replace(services, ui=bridge)
    config = ApiConfig(SecurityPolicy.for_local_server(TOKEN, PORT), frontend_dir)
    client = Api(create_app(config, services, clock), frontend_dir).signed_in_client()
    assert bridge.may_quit(ending_session=False) is True, "Nobody listens yet"
    text: list[str] = []
    listening = threading.Event()

    def read(client: TestClient) -> None:
        with client.stream("GET", "/api/events") as response:
            for line in response.iter_lines():
                if line.startswith(": connected"):
                    listening.set()
                text.append(line)

    reader = threading.Thread(target=read, args=(client,))
    reader.start()
    assert listening.wait(timeout=10)

    held = bridge.may_quit(ending_session=False)
    services.events.publish(MenuCommanded(MenuCommand.SHOW_DOWNLOADS))
    services.events.close()
    reader.join(timeout=10)

    assert held is False
    assert "event: quit.asked" in text
    assert "data: {}" in text
    assert "event: menu.command" in text
    assert 'data: {"command":"show_downloads"}' in text
    assert bridge.may_quit(ending_session=False) is True, "The stream ended"
