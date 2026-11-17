"""Tests of the key setting endpoints (``ytmirror.api.routers.settings``)."""

import pytest
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from tests.api.conftest import Api
from tests.fixtures.world import World

KEY = "fixture-good-key-0042"


@pytest.fixture
def world(api: Api) -> World:
    """The services behind the app under test."""
    assert api.world is not None
    return api.world


@pytest.fixture
def client(api: Api) -> TestClient:
    """A signed-in client of the app."""
    return api.signed_in_client()


def test_without_a_key_the_setting_says_none(client: TestClient) -> None:
    """R-DT-12: the key is off by default."""
    answer = client.get("/api/settings/api-key")

    assert answer.status_code == 200
    assert answer.json() == {"status": "none", "until": None}


def test_a_saved_key_is_kept_and_never_sent_back(client: TestClient, world: World) -> None:
    """R-DT-12, R-SE-03: the answer says how the key stands, never what it is."""
    answer = client.put("/api/settings/api-key", json={"key": KEY})

    assert answer.status_code == 200
    assert answer.json() == {"status": "saved", "until": None}
    assert KEY not in answer.text
    assert world.keys.key == KEY
    assert KEY not in client.get("/api/state").text


def test_the_key_never_reaches_the_log(client: TestClient) -> None:
    """R-LG-07: a planted key travels in the body only, and no log line holds it."""
    with capture_logs() as logs:
        client.put("/api/settings/api-key", json={"key": KEY})
        client.post("/api/settings/api-key/test", json={"key": KEY})
        client.post("/api/settings/api-key/test", json={"key": "fixture-invalid-planted"})

    assert logs
    assert all(KEY not in str(line) for line in logs)
    assert all("fixture-invalid-planted" not in str(line) for line in logs)


def test_a_key_can_be_tested_before_it_is_saved(client: TestClient, world: World) -> None:
    """R-DT-12: "Test key" says whether the key works, without saving it."""
    good = client.post("/api/settings/api-key/test", json={"key": KEY}).json()
    bad = client.post("/api/settings/api-key/test", json={"key": "fixture-quota-key"}).json()

    assert good == {"works": True, "error_code": None, "api_key": {"status": "none", "until": None}}
    assert bad["works"] is False
    assert bad["error_code"] == "API_QUOTA_EXCEEDED"
    assert world.keys.key is None


def test_testing_without_a_key_saved_or_given_is_a_bad_request(client: TestClient) -> None:
    """R-DT-12: there is nothing to test."""
    answer = client.post("/api/settings/api-key/test", json={})

    assert answer.status_code == 422
    assert answer.json()["error"]["code"] == "INVALID_REQUEST"


def test_a_key_with_spaces_inside_is_refused(client: TestClient, world: World) -> None:
    """R-DT-12: what is no key is not saved."""
    answer = client.put("/api/settings/api-key", json={"key": "two words"})

    assert answer.status_code == 422
    assert world.keys.key is None


def test_removing_the_key_deletes_it(client: TestClient, world: World) -> None:
    """R-DT-12: removing it changes nothing except speed."""
    client.put("/api/settings/api-key", json={"key": KEY})

    answer = client.delete("/api/settings/api-key")

    assert answer.json() == {"status": "none", "until": None}
    assert world.keys.key is None
