"""Fixtures for the API tests: the real app with fake ports behind it."""

from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.fixtures.builders import make_toolchain
from tests.fixtures.fakes.clock import FakeClock
from tests.fixtures.fakes.database_schema import FakeDatabaseSchema
from tests.fixtures.fakes.system_probe import FakeSystemProbe
from tests.fixtures.world import World
from ytmirror.api.app import ApiConfig, ApiServices, create_app
from ytmirror.api.security import SecurityPolicy
from ytmirror.core.models import AppInfo, InstallKind
from ytmirror.services.diagnostics import DiagnosticsService
from ytmirror.services.events import EventBus
from ytmirror.services.toolchain import ToolchainService

PORT = 8000
TOKEN = "test-session-token"
BASE_URL = f"http://127.0.0.1:{PORT}"
INDEX_HTML = "<!doctype html><title>yt-mirror</title><div id='app'></div>"


@dataclass
class Api:
    """The app under test and how to reach it."""

    app: FastAPI
    frontend_dir: Path
    world: World | None = None

    def client(self) -> TestClient:
        """Return a client that looks like the app window before it has a session."""
        return TestClient(
            self.app, base_url=BASE_URL, follow_redirects=False, raise_server_exceptions=False
        )

    def signed_in_client(self) -> TestClient:
        """Return a client that already holds the session cookie."""
        client = self.client()
        client.get("/", params={"token": TOKEN})
        return client


def make_diagnostics(tmp_path: Path) -> DiagnosticsService:
    """Return diagnostics over a fake database at schema version 0002."""
    info = AppInfo(
        version="1.2.3",
        install_kind=InstallKind.CLONE,
        home_dir=tmp_path,
        data_dir=tmp_path / "data",
        database_file=tmp_path / "data" / "yt-mirror.db",
        frontend_dir=tmp_path / "dist",
        uv_executable=tmp_path / "tools" / "uv" / "uv",
    )
    return DiagnosticsService(
        info, FakeDatabaseSchema(current="0002"), FakeSystemProbe(), make_toolchain()
    )


def services_around(tmp_path: Path, toolchain: ToolchainService, world: World) -> ApiServices:
    """Return the services of the app: a toolchain of the test, and the catalogue of a world."""
    return ApiServices(
        diagnostics=make_diagnostics(tmp_path),
        toolchain=toolchain,
        events=world.bus,
        state=world.state,
        youtube=world.youtube,
        channels=world.channels,
        catalogue=world.catalogue,
        views=world.views,
        thumbnails=world.thumbnails,
    )


def make_services(tmp_path: Path, world: World | None = None) -> ApiServices:
    """Return the services of the app over fakes, on a Mac where every tool is in place."""
    used_world = world if world is not None else new_world(tmp_path)
    toolchain = make_toolchain(events=used_world.bus)
    toolchain.verify()
    return services_around(tmp_path, toolchain, used_world)


def new_world(tmp_path: Path, bus: EventBus | None = None) -> World:
    """Return the catalogue services over fakes, in a folder of their own."""
    folder = tmp_path / "world"
    folder.mkdir(exist_ok=True)
    return World(folder, bus=bus)


@pytest.fixture
def frontend_dir(tmp_path: Path) -> Path:
    """A built interface: an index page and one asset."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('app')", encoding="utf-8")
    return dist


@pytest.fixture
def api(tmp_path: Path, frontend_dir: Path, clock: FakeClock) -> Api:
    """The app as a normal run builds it."""
    config = ApiConfig(
        security=SecurityPolicy.for_local_server(TOKEN, PORT), frontend_dir=frontend_dir
    )
    world = new_world(tmp_path)
    return Api(create_app(config, make_services(tmp_path, world), clock), frontend_dir, world)
