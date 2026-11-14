"""Tests of the tool endpoints."""

from pathlib import Path

import pytest

from tests.api.conftest import PORT, TOKEN, Api, make_diagnostics
from tests.fixtures.builders import make_toolchain, tool_box_with
from tests.fixtures.fakes.clock import FakeClock
from tests.fixtures.fakes.tool_box import FakeToolBox
from ytmirror.api.app import ApiConfig, ApiServices, create_app
from ytmirror.api.security import SecurityPolicy
from ytmirror.core.models import ToolName
from ytmirror.services.events import EventBus


def api_with(tool_box: FakeToolBox, tmp_path: Path, frontend_dir: Path, clock: FakeClock) -> Api:
    """Return the app over a tool box in a chosen state, after the check of a start."""
    events = EventBus()
    toolchain = make_toolchain(tool_box=tool_box, events=events)
    toolchain.verify()
    services = ApiServices(make_diagnostics(tmp_path), toolchain, events)
    config = ApiConfig(SecurityPolicy.for_local_server(TOKEN, PORT), frontend_dir)
    return Api(create_app(config, services, clock), frontend_dir)


@pytest.fixture
def fresh(tmp_path: Path, frontend_dir: Path, clock: FakeClock) -> Api:
    """The app on a Mac where nothing was downloaded yet."""
    return api_with(tool_box_with([]), tmp_path, frontend_dir, clock)


def test_the_tools_are_listed_in_the_order_of_the_first_run_screen(fresh: Api) -> None:
    """R-IN-03: the app shows which tools it needs: Python, yt-dlp, ffmpeg, Deno."""
    response = fresh.signed_in_client().get("/api/tools")

    body = response.json()
    assert response.status_code == 200
    assert [(tool["name"], tool["status"]) for tool in body["tools"]] == [
        ("python", "ok"),
        ("ytdlp", "ok"),
        ("ffmpeg", "missing"),
        ("deno", "missing"),
    ]
    assert body["setup_required"] is True
    assert body["tools"][2] == {
        "name": "ffmpeg",
        "status": "missing",
        "version": None,
        "source": None,
        "progress": None,
        "error_code": None,
        "installable": True,
    }


def test_installing_a_tool_is_accepted_and_the_tool_is_there_afterwards(fresh: Api) -> None:
    """R-IN-03, R-IN-04: "Install now" downloads the tool, with its source named afterwards."""
    client = fresh.signed_in_client()

    started = client.post("/api/tools/deno/install")
    after = client.get("/api/tools").json()

    deno = next(tool for tool in after["tools"] if tool["name"] == "deno")
    assert started.status_code == 202
    assert started.json()["name"] == "deno"
    assert started.json()["status"] == "installing"
    assert deno["status"] == "ok"
    assert deno["version"] == "2.9.8"
    assert deno["source"] == "deno"
    assert after["setup_required"] is True


def test_once_every_tool_is_there_the_first_run_screen_is_no_longer_needed(fresh: Api) -> None:
    """R-IN-03: the first-run screen is shown until setup has completed once."""
    client = fresh.signed_in_client()

    client.post("/api/tools/ffmpeg/install")
    client.post("/api/tools/deno/install")

    assert client.get("/api/tools").json()["setup_required"] is False


def test_a_failed_installation_names_its_error_code(
    tmp_path: Path, frontend_dir: Path, clock: FakeClock
) -> None:
    """R-IN-03, R-ER-02: a failed step carries the code its user text is written for."""
    tool_box = tool_box_with([ToolName.FFMPEG])
    tool_box.unreachable.update(tool_box.downloads)
    client = api_with(tool_box, tmp_path, frontend_dir, clock).signed_in_client()

    client.post("/api/tools/deno/install")

    deno = next(tool for tool in client.get("/api/tools").json()["tools"] if tool["name"] == "deno")
    assert deno["status"] == "failed"
    assert deno["error_code"] == "NETWORK_UNREACHABLE"


@pytest.mark.parametrize("name", ["python", "ytdlp"])
def test_a_tool_that_comes_with_the_launcher_cannot_be_installed_here(api: Api, name: str) -> None:
    """R-IN-04: only tools the app downloads have an "Install now"."""
    response = api.signed_in_client().post(f"/api/tools/{name}/install")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert response.json()["error"]["details"] == {"tool": name}


def test_an_unknown_tool_is_an_invalid_request(api: Api) -> None:
    """R-ER-02: a tool the app does not know is refused in the one error shape."""
    response = api.signed_in_client().post("/api/tools/winamp/install")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_the_tool_endpoints_need_the_session(api: Api) -> None:
    """R-PL-10: every call to the local API must carry the session token."""
    client = api.client()

    assert client.get("/api/tools").status_code == 401
    assert client.post("/api/tools/deno/install").status_code == 401
    assert client.get("/api/events").status_code == 401
