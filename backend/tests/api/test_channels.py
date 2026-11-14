"""Tests of the channel endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from tests.api.conftest import Api
from tests.fixtures.world import SMALL_ID, World
from ytmirror.core.channels import CheckKind
from ytmirror.core.errors import ErrorCode

PNG = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def world(api: Api) -> World:
    """The catalogue services behind the app under test."""
    assert api.world is not None
    return api.world


@pytest.fixture
def client(api: Api) -> TestClient:
    """A signed-in client of the app."""
    return api.signed_in_client()


def looked_up(client: TestClient, world: World, text: str = "@small") -> dict[str, object]:
    """Look a channel up and let its video count arrive."""
    answer = client.post("/api/channels/lookup", json={"text": text})
    world.run_background()
    return answer.json()


def added(client: TestClient, world: World) -> str:
    """Add the small channel and let its first listing run. Returns its ID."""
    looked_up(client, world)
    client.post("/api/channels", json={"channel_id": SMALL_ID})
    world.work()
    return SMALL_ID


def error_code(response: Response) -> str:
    """Return the error code of an error response."""
    return str(response.json()["error"]["code"])


# --- lookup


def test_a_lookup_returns_the_preview_of_the_channel(client: TestClient, world: World) -> None:
    """R-CH-03: name, handle and avatar of the channel are shown before the user confirms."""
    answer = client.post("/api/channels/lookup", json={"text": "https://youtube.com/@small"})

    assert answer.status_code == 200
    assert answer.json() == {
        "channel_id": SMALL_ID,
        "title": "Small Channel",
        "handle": "@small",
        "has_avatar": True,
        "existing": False,
        "folder": str(world.library / "Small Channel"),
        "video_files": 0,
    }


def test_what_is_no_channel_is_refused_with_the_reason(client: TestClient) -> None:
    """R-CH-02, R-ER-02: a video address is rejected with a code and what was wrong."""
    answer = client.post("/api/channels/lookup", json={"text": "https://youtu.be/abcdefghijk"})

    assert answer.status_code == 422
    assert error_code(answer) == "INVALID_CHANNEL_INPUT"
    assert answer.json()["error"]["details"] == {"reason": "video"}


def test_an_unknown_channel_is_not_found(client: TestClient) -> None:
    """R-CH-03, R-ER-02: a channel YouTube does not have is answered with its own code."""
    answer = client.post("/api/channels/lookup", json={"text": "@nobody"})

    assert answer.status_code == 404
    assert error_code(answer) == "CHANNEL_NOT_FOUND"


def test_a_lookup_that_youtube_refuses_carries_the_code_of_the_refusal(
    client: TestClient, world: World
) -> None:
    """R-ER-05, R-ER-02: the "not a bot" check reaches the interface under its own code."""
    world.gateway.refuse["lookup"] = ErrorCode.BOT_CHECK

    answer = client.post("/api/channels/lookup", json={"text": "@small"})

    assert answer.status_code == 503
    assert error_code(answer) == "BOT_CHECK"


def test_the_video_count_is_fetched_apart_from_the_preview(
    client: TestClient, world: World
) -> None:
    """R-CH-03: the count has a call of its own, so it never delays the preview."""
    looked_up(client, world)

    answer = client.get(f"/api/channels/lookup/{SMALL_ID}/video-count")

    assert answer.status_code == 200
    assert answer.json() == {"video_count": 5}


def test_without_a_count_the_answer_is_null_not_an_error(client: TestClient, world: World) -> None:
    """R-CH-03: a count that YouTube does not give is no failure of anything."""
    world.gateway.refuse["count"] = ErrorCode.NETWORK_UNREACHABLE
    looked_up(client, world)

    answers = [
        client.get(f"/api/channels/lookup/{SMALL_ID}/video-count"),
        client.get("/api/channels/lookup/UCneverlookedup000000000/video-count"),
    ]

    assert [answer.status_code for answer in answers] == [200, 200]
    assert [answer.json() for answer in answers] == [{"video_count": None}] * 2


def test_the_avatar_of_a_preview_is_a_picture(client: TestClient, world: World) -> None:
    """R-CH-03: the avatar of a channel that was looked up is shown in the preview."""
    looked_up(client, world)

    answer = client.get(f"/api/channels/lookup/{SMALL_ID}/avatar")

    assert answer.status_code == 200
    assert answer.headers["content-type"] == "image/png"
    assert answer.content.startswith(PNG)


def test_a_preview_avatar_that_cannot_be_had_is_not_found(client: TestClient, world: World) -> None:
    """R-CH-03: without the avatar the preview still works."""
    not_looked_up = client.get(f"/api/channels/lookup/{SMALL_ID}/avatar")
    world.gateway.refuse["image"] = ErrorCode.NETWORK_UNREACHABLE
    looked_up(client, world)
    not_fetched = client.get(f"/api/channels/lookup/{SMALL_ID}/avatar")

    assert [not_looked_up.status_code, not_fetched.status_code] == [404, 404]
    assert error_code(not_fetched) == "NOT_FOUND"


# --- the folder dialog


def test_the_folder_dialog_returns_the_chosen_folder(
    client: TestClient, world: World, tmp_path: Path
) -> None:
    """R-CH-05, R-CH-06: the chosen folder comes back with the number of its video files."""
    world.picker.answer = tmp_path / "Chosen"
    world.files.add_files(tmp_path / "Chosen", ["a.mkv", "b.mkv"])

    answer = client.post("/api/folders/choose")

    assert answer.json() == {"folder": str(tmp_path / "Chosen"), "video_files": 2}


def test_a_cancelled_folder_dialog_returns_no_folder(client: TestClient) -> None:
    """R-CH-05: Cancel is an answer, not an error."""
    answer = client.post("/api/folders/choose")

    assert answer.status_code == 200
    assert answer.json() == {"folder": None, "video_files": 0}


# --- adding


def test_adding_a_channel_answers_at_once_while_the_listing_runs(
    client: TestClient, world: World
) -> None:
    """R-CH-05, R-CH-11: the channel is there at once, and it is being listed."""
    looked_up(client, world)

    answer = client.post(
        "/api/channels",
        json={"channel_id": SMALL_ID, "quality": "1080", "auto_mirror": True, "mirror_after": 5},
    )

    channel = answer.json()["channel"]
    assert answer.status_code == 201
    assert answer.json()["existing"] is False
    assert (channel["id"], channel["title"], channel["status"]) == (
        SMALL_ID,
        "Small Channel",
        "checking",
    )
    assert (channel["quality"], channel["auto_mirror"], channel["mirror_after"]) == (
        "1080",
        True,
        5,
    )
    assert (channel["videos"], channel["first_listed_at"]) == (0, None)
    assert channel["folder"] == str(world.library / "Small Channel")


def test_adding_a_channel_twice_opens_the_existing_one(client: TestClient, world: World) -> None:
    """R-CH-04: a channel that already exists is returned, and the answer says so."""
    added(client, world)
    looked_up(client, world)

    answer = client.post("/api/channels", json={"channel_id": SMALL_ID})

    assert answer.status_code == 200
    assert answer.json()["existing"] is True
    assert answer.json()["channel"]["videos"] == 5


def test_a_channel_that_was_not_looked_up_or_a_foreign_folder_is_refused(
    client: TestClient, world: World
) -> None:
    """R-PL-04: a channel is added from its preview, into a folder the dialog gave."""
    unknown = client.post("/api/channels", json={"channel_id": SMALL_ID})
    looked_up(client, world)
    foreign = client.post("/api/channels", json={"channel_id": SMALL_ID, "folder": "/etc"})

    assert [unknown.status_code, foreign.status_code] == [422, 422]
    assert [error_code(unknown), error_code(foreign)] == ["INVALID_REQUEST"] * 2
    assert world.repository.channels() == ()


def test_a_request_without_a_channel_is_malformed(client: TestClient) -> None:
    """R-ER-02: a malformed request is answered with INVALID_REQUEST."""
    answer = client.post("/api/channels", json={"quality": "8000"})

    assert answer.status_code == 422
    assert error_code(answer) == "INVALID_REQUEST"


# --- one channel


def test_a_channel_is_returned_with_its_totals_and_times(client: TestClient, world: World) -> None:
    """R-CH-35: the header gets the totals and the times of the last check and full check."""
    added(client, world)

    channel = client.get(f"/api/channels/{SMALL_ID}").json()

    assert (channel["videos"], channel["synced"], channel["excluded"], channel["size_bytes"]) == (
        5,
        0,
        0,
        0,
    )
    assert channel["status"] == "up_to_date"
    assert channel["new_videos"] == 0
    assert channel["last_check_at"] == channel["last_full_check_at"] == world.now()
    assert channel["last_check_error"] is None
    assert channel["progress"] is None
    assert channel["url"] == f"https://www.youtube.com/channel/{SMALL_ID}"


def test_pausing_and_resuming_a_channel(client: TestClient, world: World) -> None:
    """R-CH-30, R-CH-31: a channel is paused and resumed through its address."""
    added(client, world)

    paused = client.patch(f"/api/channels/{SMALL_ID}", json={"paused": True})
    resumed = client.patch(f"/api/channels/{SMALL_ID}", json={"paused": False})

    assert (paused.json()["paused"], paused.json()["status"]) == (True, "paused")
    assert (resumed.json()["paused"], resumed.json()["status"]) == (False, "up_to_date")


def test_removing_a_channel(client: TestClient, world: World) -> None:
    """R-CH-32: a removed channel and its catalogue are gone."""
    added(client, world)

    removed = client.delete(f"/api/channels/{SMALL_ID}")

    assert removed.status_code == 204
    assert client.get(f"/api/channels/{SMALL_ID}").status_code == 404
    assert world.repository.videos(SMALL_ID) == ()


def test_opening_the_folder_of_a_channel(client: TestClient, world: World) -> None:
    """R-CH-30: the folder of the channel is shown in Finder."""
    added(client, world)

    answer = client.post(f"/api/channels/{SMALL_ID}/open-folder")

    assert answer.status_code == 204
    assert world.files.opened == [world.library / "Small Channel"]


def test_the_avatar_of_a_channel_is_served_from_the_cache(client: TestClient, world: World) -> None:
    """R-CH-16: the sidebar gets the avatar from the local server."""
    before = client.get(f"/api/channels/{SMALL_ID}/avatar")
    added(client, world)

    after = client.get(f"/api/channels/{SMALL_ID}/avatar")

    assert before.status_code == 404
    assert after.status_code == 200
    assert after.content.startswith(PNG)


# --- checks


def test_check_now_starts_a_quick_check(client: TestClient, world: World) -> None:
    """R-CH-23: "Check now" answers at once with the channel being checked."""
    added(client, world)

    answer = client.post(f"/api/channels/{SMALL_ID}/check")
    world.work()

    assert answer.status_code == 202
    assert answer.json()["status"] == "checking"
    assert world.fixture.listings_started[SMALL_ID] == 2
    assert world.repository.channel(SMALL_ID).last_full_check_at == world.now()  # pyright: ignore[reportOptionalMemberAccess]


def test_a_full_check_is_asked_for_by_its_kind(client: TestClient, world: World) -> None:
    """R-CH-23: "Full check" starts a full check of the channel."""
    added(client, world)
    world.clock.advance(60)

    client.post(f"/api/channels/{SMALL_ID}/check", json={"kind": CheckKind.FULL.value})
    world.work()

    assert world.repository.channel(SMALL_ID).last_full_check_at == world.now()  # pyright: ignore[reportOptionalMemberAccess]


def test_a_full_check_that_waits_can_be_cancelled(client: TestClient, world: World) -> None:
    """R-CH-27: a full check is cancelled through the channel."""
    added(client, world)
    client.post(f"/api/channels/{SMALL_ID}/check", json={"kind": "full"})

    cancelled = client.post(f"/api/channels/{SMALL_ID}/check/cancel")
    nothing = client.post(f"/api/channels/{SMALL_ID}/check/cancel")

    assert cancelled.json() == {"cancelled": True}
    assert nothing.json() == {"cancelled": False}
    assert client.get(f"/api/channels/{SMALL_ID}").json()["status"] == "up_to_date"


def test_a_paused_channel_cannot_be_checked(client: TestClient, world: World) -> None:
    """R-CH-31: a paused channel is not checked by hand either."""
    added(client, world)
    client.patch(f"/api/channels/{SMALL_ID}", json={"paused": True})

    answer = client.post(f"/api/channels/{SMALL_ID}/check")

    assert answer.status_code == 422
    assert error_code(answer) == "INVALID_REQUEST"
    assert answer.json()["error"]["details"]["reason"] == "paused"


def test_check_all_channels(client: TestClient, world: World) -> None:
    """R-CH-23: "Check all channels now" starts a check of every channel that is not paused."""
    added(client, world)

    answer = client.post("/api/channels/check-all")
    world.work()

    assert answer.status_code == 202
    assert answer.json() == {"channels": 1}
    assert world.fixture.listings_started[SMALL_ID] == 2


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/channels/UCunknown"),
        ("patch", "/api/channels/UCunknown"),
        ("delete", "/api/channels/UCunknown"),
        ("post", "/api/channels/UCunknown/check"),
        ("post", "/api/channels/UCunknown/check/cancel"),
        ("post", "/api/channels/UCunknown/open-folder"),
        ("get", "/api/channels/UCunknown/videos"),
    ],
)
def test_an_unknown_channel_is_answered_with_not_found(
    client: TestClient, method: str, path: str
) -> None:
    """R-ER-02: every address of a channel that was not added answers NOT_FOUND."""
    body = {"paused": True} if method == "patch" else None
    answer = client.request(method, path, json=body)

    assert answer.status_code == 404
    assert error_code(answer) == "NOT_FOUND"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/state"),
        ("put", "/api/state/open-channel"),
        ("post", "/api/youtube/try-now"),
        ("post", "/api/channels/lookup"),
        ("get", f"/api/channels/lookup/{SMALL_ID}/video-count"),
        ("get", f"/api/channels/lookup/{SMALL_ID}/avatar"),
        ("post", "/api/folders/choose"),
        ("post", "/api/channels"),
        ("post", "/api/channels/check-all"),
        ("get", f"/api/channels/{SMALL_ID}"),
        ("delete", f"/api/channels/{SMALL_ID}"),
        ("post", f"/api/channels/{SMALL_ID}/check"),
        ("post", f"/api/channels/{SMALL_ID}/open-folder"),
        ("get", f"/api/channels/{SMALL_ID}/avatar"),
        ("get", f"/api/channels/{SMALL_ID}/videos"),
        ("get", "/api/videos/sm000000001/thumbnail"),
    ],
)
def test_every_new_endpoint_needs_the_session_token(api: Api, method: str, path: str) -> None:
    """R-PL-10: no call of the API works without the session token, also not a picture."""
    answer = api.client().request(method, path)

    assert answer.status_code == 401
    assert error_code(answer) == "UNAUTHORIZED"
