"""Tests of the queue endpoints."""

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import Api
from tests.fixtures.world import World

FIRST = "sm000000005"
SECOND = "sm000000004"
THIRD = "sm000000003"


@pytest.fixture
def world(api: Api) -> World:
    """The services behind the app under test, with the small channel added."""
    assert api.world is not None
    api.world.add_and_list()
    return api.world


@pytest.fixture
def client(api: Api) -> TestClient:
    """A signed-in client of the app."""
    return api.signed_in_client()


def test_the_queue_lists_waiting_downloads_in_order(client: TestClient, world: World) -> None:
    """R-QU-02: GET /api/queue gives the waiting downloads in the order they will run."""
    client.post("/api/videos/mirror", json={"ids": [FIRST, SECOND]})
    client.post("/api/videos/mirror", json={"ids": [THIRD], "first": True})

    answer = client.get("/api/queue").json()

    assert [item["video_id"] for item in answer["waiting"]] == [THIRD, FIRST, SECOND]
    assert answer["waiting"][0] == {
        "job_id": answer["waiting"][0]["job_id"],
        "video_id": THIRD,
        "channel_id": world.repository.video(THIRD).channel_id,  # type: ignore[union-attr]
        "channel_title": "Small Channel",
        "title": "Video 3",
        "duration_s": world.repository.video(THIRD).duration_s,  # type: ignore[union-attr]
        "quality": "best",
        "by_hand": True,
        "download": None,
        "paced_until": None,
    }
    assert answer["queue"] == {
        "downloading": 0,
        "waiting": 3,
        "failed": 0,
        "paused": False,
        "places": 2,
    }


def test_reorder_and_clear_waiting(client: TestClient, world: World) -> None:
    """R-QU-02: the waiting downloads can be reordered and cleared."""
    jobs = client.post("/api/videos/mirror", json={"ids": [FIRST, SECOND]}).json()["jobs"]

    assert (
        client.post(
            "/api/queue/reorder", json={"job_ids": [jobs[1]["job_id"], jobs[0]["job_id"]]}
        ).status_code
        == 204
    )
    order = [item["video_id"] for item in client.get("/api/queue").json()["waiting"]]
    assert order == [SECOND, FIRST]

    assert client.post("/api/queue/clear-waiting").json() == {"removed": 2}
    assert client.get("/api/queue").json()["waiting"] == []


def test_pause_and_resume_all(client: TestClient, world: World) -> None:
    """R-QU-02: pause all and resume all answer with the queue as it stands."""
    assert client.post("/api/queue/pause").json()["paused"] is True
    assert client.get("/api/state").json()["queue"]["paused"] is True
    assert client.post("/api/queue/resume").json()["paused"] is False
