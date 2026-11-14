"""Tests of the snapshot of the app, the pause of YouTube and the favicon."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import PORT, TOKEN, Api, make_services
from tests.fixtures.fakes.clock import FakeClock
from tests.fixtures.world import SMALL_ID, World
from ytmirror.api.app import ApiConfig, create_app
from ytmirror.api.security import SecurityPolicy
from ytmirror.core.errors import ErrorCode
from ytmirror.ports.file_system import Disk

SVG = "<svg xmlns='http://www.w3.org/2000/svg'><rect fill='#1f5fd1'/></svg>"


@pytest.fixture
def world(api: Api) -> World:
    """The catalogue services behind the app under test."""
    assert api.world is not None
    return api.world


@pytest.fixture
def client(api: Api) -> TestClient:
    """A signed-in client of the app."""
    return api.signed_in_client()


def test_the_snapshot_of_a_new_app(client: TestClient, world: World) -> None:
    """R-UI-02, R-UI-01: without channels the window shows the welcome screen and the free space."""
    world.files.disk = Disk("Media", 182_000_000_000)

    answer = client.get("/api/state")

    assert answer.status_code == 200
    assert answer.json() == {
        "channels": [],
        "open_channel_id": None,
        "library_folder": str(world.library),
        "disk": {"name": "Media", "free_bytes": 182_000_000_000},
        "can_choose_folder": True,
        "youtube_pause": None,
    }


def test_the_snapshot_lists_the_channels_of_the_sidebar(client: TestClient, world: World) -> None:
    """R-CH-34: every channel comes with its name, status and count of new videos."""
    world.add_and_list()

    channels = client.get("/api/state").json()["channels"]

    assert [(channel["id"], channel["title"], channel["status"]) for channel in channels] == [
        (SMALL_ID, "Small Channel", "up_to_date")
    ]
    assert channels[0]["new_videos"] == 0


def test_the_open_channel_is_remembered_for_the_next_start(
    client: TestClient, world: World
) -> None:
    """R-UI-02: the app opens on the channel that was open last."""
    world.add_and_list()

    answer = client.put("/api/state/open-channel", json={"channel_id": SMALL_ID})
    cleared = client.put("/api/state/open-channel", json={"channel_id": None})

    assert answer.json()["open_channel_id"] == SMALL_ID
    assert cleared.json()["open_channel_id"] is None


def test_an_unknown_channel_cannot_be_the_open_one(client: TestClient) -> None:
    """R-UI-02: only a channel that was added is remembered."""
    answer = client.put("/api/state/open-channel", json={"channel_id": "UCunknown"})

    assert answer.status_code == 404


def test_the_pause_of_youtube_is_in_the_snapshot_and_try_now_ends_it(
    client: TestClient, world: World
) -> None:
    """R-ER-05, R-FB-04: the banner has what it needs, and its action ends the pause."""
    world.gateway.refuse["lookup"] = ErrorCode.BOT_CHECK
    client.post("/api/channels/lookup", json={"text": "@small"})

    paused = client.get("/api/state").json()["youtube_pause"]
    tried = client.post("/api/youtube/try-now")

    assert paused == {"code": "BOT_CHECK", "until": world.now() + 900}
    assert tried.status_code == 200
    assert tried.json()["youtube_pause"] is None


def with_favicon(tmp_path: Path, frontend_dir: Path, svg: str | None) -> TestClient:
    """Return a client of an app with or without an icon source, not signed in."""
    drawn: list[int] = []

    def draw() -> bytes:
        drawn.append(1)
        return b"\x89PNG\r\n\x1a\n" + bytes([len(drawn)])

    config = ApiConfig(
        security=SecurityPolicy.for_local_server(TOKEN, PORT),
        frontend_dir=frontend_dir,
        favicon_svg=svg,
        favicon_png=None if svg is None else draw,
    )
    return Api(create_app(config, make_services(tmp_path), FakeClock()), frontend_dir).client()


def test_the_favicon_is_the_app_icon_and_needs_no_token(tmp_path: Path, frontend_dir: Path) -> None:
    """R-PL-11: the server serves the app's own icon, made from the icon source file."""
    client = with_favicon(tmp_path, frontend_dir, SVG)

    svg = client.get("/favicon.svg")
    png = client.get("/favicon.png")
    again = client.get("/favicon.png")

    assert (svg.status_code, svg.headers["content-type"]) == (200, "image/svg+xml")
    assert svg.text == SVG
    assert (png.status_code, png.headers["content-type"]) == (200, "image/png")
    assert png.content == again.content


def test_without_an_icon_source_there_is_no_favicon(tmp_path: Path, frontend_dir: Path) -> None:
    """R-PL-11: a missing icon source is answered plainly, not with a broken picture."""
    client = with_favicon(tmp_path, frontend_dir, None)

    assert client.get("/favicon.svg").status_code == 404
    assert client.get("/favicon.png").status_code == 404
