"""Tests of how the app serves the built interface."""

from pathlib import Path

from tests.api.conftest import INDEX_HTML, PORT, TOKEN, Api, make_diagnostics
from tests.fixtures.fakes.clock import FakeClock
from ytmirror.api.app import ApiConfig, create_app
from ytmirror.api.security import SecurityPolicy


def test_the_start_page_is_the_built_interface(api: Api) -> None:
    """infra: the backend serves the built frontend."""
    response = api.client().get("/")

    assert response.status_code == 200
    assert response.text == INDEX_HTML
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-cache"


def test_assets_of_the_interface_are_served(api: Api) -> None:
    """infra: scripts, styles and fonts come from the same server."""
    response = api.client().get("/assets/app.js")

    assert response.status_code == 200
    assert response.text == "console.log('app')"


def test_files_outside_the_interface_folder_cannot_be_read(api: Api, tmp_path: Path) -> None:
    """R-PL-04: the server gives out the interface and nothing else from the disk."""
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    client = api.client()

    for path in ("/../secret.txt", "/assets/../../secret.txt", "/%2e%2e/secret.txt"):
        response = client.get(path)

        assert response.status_code == 404, path
        assert "secret" not in response.text.replace("secret.txt", ""), path


def test_a_missing_build_is_reported_as_not_found(tmp_path: Path, clock: FakeClock) -> None:
    """infra: without a built interface the server says so instead of crashing."""
    empty = tmp_path / "not-built"
    config = ApiConfig(security=SecurityPolicy.for_local_server(TOKEN, PORT), frontend_dir=empty)
    api = Api(create_app(config, make_diagnostics(tmp_path), clock), empty)

    response = api.client().get("/")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["error"]["details"] == {"missing": "the built interface"}
