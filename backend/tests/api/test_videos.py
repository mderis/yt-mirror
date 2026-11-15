"""Tests of the catalogue endpoints and of the pictures they serve."""

import dataclasses

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import Api
from tests.fixtures.world import SMALL_ID, World
from ytmirror.api.pictures import content_type_of
from ytmirror.core.catalogue import CheckChanges
from ytmirror.core.channels import CheckKind
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.ports.image_cache import ImageKind

PNG = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def world(api: Api) -> World:
    """The catalogue services behind the app under test, with the small channel added."""
    assert api.world is not None
    api.world.add_and_list()
    return api.world


@pytest.fixture
def client(api: Api) -> TestClient:
    """A signed-in client of the app."""
    return api.signed_in_client()


def test_the_catalogue_of_a_channel_is_listed_newest_first(
    client: TestClient, world: World
) -> None:
    """R-CH-10: every video comes with title, duration, view count, date and status."""
    videos = client.get(f"/api/channels/{SMALL_ID}/videos").json()["videos"]

    assert [video["id"] for video in videos] == world.ids(SMALL_ID)
    assert videos[0] == {
        "id": "sm000000005",
        "title": "Video 5",
        "duration_s": 245,
        "view_count": 39595,
        "published_at": None,
        "published_around": 1794528000 - 43200,
        "published_precision": "day",
        "status": "not_downloaded",
        "is_new": False,
        "gone": False,
        "excluded": False,
        "job_id": None,
        "download": None,
        "height": None,
        "file_size": None,
        "error_code": None,
    }


def test_an_approximate_date_is_never_sent_as_an_exact_one(
    client: TestClient, world: World
) -> None:
    """R-DT-04: a date from the listing is sent as "around", with its unit, never as exact."""
    videos = client.get(f"/api/channels/{SMALL_ID}/videos").json()["videos"]

    assert all(video["published_at"] is None for video in videos)
    assert all(video["published_around"] is not None for video in videos)
    assert {video["published_precision"] for video in videos} == {"day"}


def test_a_new_and_a_removed_video_are_marked(client: TestClient, world: World) -> None:
    """R-CH-14, R-CH-15: the list knows which videos are new and which are removed from YouTube."""
    first, second = world.repository.videos(SMALL_ID)[:2]
    channel = world.repository.channel(SMALL_ID)
    assert channel is not None
    world.repository.apply_check(
        channel,
        CheckChanges(
            inserted=(),
            updated=(
                dataclasses.replace(first, seen_in_first_listing=False),
                dataclasses.replace(second, gone=True, missing_checks=2),
            ),
            new=0,
            changed=0,
            removed=0,
            returned=0,
            read=0,
        ),
    )

    videos = client.get(f"/api/channels/{SMALL_ID}/videos").json()["videos"]

    assert [(video["is_new"], video["gone"]) for video in videos[:3]] == [
        (True, False),
        (False, True),
        (False, False),
    ]


def test_a_cached_thumbnail_is_served_as_a_picture(client: TestClient, world: World) -> None:
    """R-CH-16: the list gets its thumbnails from the local server."""
    answer = client.get("/api/videos/sm000000005/thumbnail")

    assert answer.status_code == 200
    assert answer.headers["content-type"] == "image/png"
    assert answer.headers["cache-control"] == "private, max-age=86400"
    assert answer.headers["x-content-type-options"] == "nosniff"
    assert answer.content.startswith(PNG)


def test_a_thumbnail_that_is_not_cached_is_not_found_at_once(
    client: TestClient, world: World
) -> None:
    """R-CH-16: asking for a picture never waits for YouTube."""
    world.cache.remove(ImageKind.THUMBNAIL, ["sm000000005"])
    asked = list(world.gateway.asked)

    answer = client.get("/api/videos/sm000000005/thumbnail")

    assert answer.status_code == 404
    assert answer.json()["error"]["code"] == "NOT_FOUND"
    assert world.gateway.asked == asked


@pytest.mark.parametrize("bad", ["..", "a b", "x" * 65, "%2e%2e%2fsecret"])
def test_a_thumbnail_is_named_by_an_id_and_by_nothing_else(
    client: TestClient, world: World, bad: str
) -> None:
    """R-PL-11: nothing but cached pictures can be reached through the picture addresses."""
    assert client.get(f"/api/videos/{bad}/thumbnail").status_code == 404
    assert client.get(f"/api/channels/{bad}/avatar").status_code == 404


def test_the_thumbnail_of_a_video_that_was_removed_from_youtube_is_still_served(
    client: TestClient, api: Api
) -> None:
    """R-CH-16: the list works for removed videos."""
    assert api.world is not None
    api.world.add_and_list()
    api.world.check(SMALL_ID, CheckKind.FULL)

    assert client.get("/api/videos/sm000000001/thumbnail").status_code == 200


@pytest.mark.parametrize(
    ("picture", "content_type"),
    [
        (PNG + b"...", "image/png"),
        (b"\xff\xd8\xff\xe0 jpeg", "image/jpeg"),
        (b"GIF89a...", "image/gif"),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp"),
        (b"RIFF\x00\x00\x00\x00WAVEfmt ", "application/octet-stream"),
        (b"<html>", "application/octet-stream"),
        (b"", "application/octet-stream"),
    ],
)
def test_the_kind_of_a_picture_is_read_from_its_first_bytes(
    picture: bytes, content_type: str
) -> None:
    """R-CH-16: a cached picture is served as what it is, and nothing else as a picture."""
    assert content_type_of(picture) == content_type


# --- downloads (milestone M3)


def test_mirror_puts_videos_in_line_in_the_order_given(client: TestClient, world: World) -> None:
    """R-MI-01: Mirror answers at once with the jobs that were put in line."""
    answer = client.post("/api/videos/mirror", json={"ids": ["sm000000004", "sm000000005"]})

    assert answer.status_code == 202
    assert [job["video_id"] for job in answer.json()["jobs"]] == ["sm000000004", "sm000000005"]
    listed = client.get(f"/api/channels/{SMALL_ID}/videos").json()["videos"]
    queued = {video["id"]: video for video in listed if video["status"] == "queued"}
    assert set(queued) == {"sm000000004", "sm000000005"}
    assert queued["sm000000004"]["job_id"] == answer.json()["jobs"][0]["job_id"]


def test_a_synced_video_has_its_details_play_and_show_in_finder(
    client: TestClient, world: World
) -> None:
    """R-UI-08, R-UI-10: the details of a synced video, and Play and Show in Finder by its ID."""
    client.post("/api/videos/mirror", json={"ids": ["sm000000005"]})
    world.download_all()

    details = client.get("/api/videos/sm000000005").json()
    played = client.post("/api/videos/sm000000005/play")
    revealed = client.post("/api/videos/sm000000005/reveal")

    file = world.library / "Small Channel" / details["file"]["name"]
    assert details["video"]["status"] == "synced"
    assert details["file"]["height"] == 270
    assert details["file"]["vcodec"] == "av1"
    assert details["file"]["subtitles"] == "manual"
    assert details["file"]["cover_embedded"] is True
    assert details["video"]["published_at"] == 1_793_379_761
    assert details["downloaded_at"] == world.now()
    assert details["thumbnail_saved"] is True
    assert details["url"] == "https://www.youtube.com/watch?v=sm000000005"
    assert (played.status_code, revealed.status_code) == (204, 204)
    assert world.files.played == [file]
    assert world.files.revealed == [file]


def test_a_video_without_a_file_has_details_but_no_file(client: TestClient, world: World) -> None:
    """R-UI-08: a video that is not downloaded shows no file facts."""
    details = client.get("/api/videos/sm000000005").json()

    assert details["file"] is None
    assert details["chapters"] == []


def test_a_failed_video_says_why_and_can_be_retried(client: TestClient, world: World) -> None:
    """R-QU-08, R-ER-03: a failed video carries its code, and Retry puts it in line."""
    world.download.fail = AppError(ErrorCode.MEMBERS_ONLY)
    client.post("/api/videos/mirror", json={"ids": ["sm000000005"]})
    world.download_all()

    failed = client.get("/api/videos/sm000000005").json()["video"]
    retried = client.post("/api/videos/sm000000005/retry")

    assert (failed["status"], failed["error_code"]) == ("failed", "MEMBERS_ONLY")
    assert retried.status_code == 202
    assert retried.json()["status"] == "queued"


def test_cancel_takes_a_waiting_video_out_of_line(client: TestClient, world: World) -> None:
    """R-QU-02: Cancel by job ID; a second Cancel finds nothing."""
    job_id = client.post("/api/videos/mirror", json={"ids": ["sm000000005"]}).json()["jobs"][0][
        "job_id"
    ]

    first = client.post(f"/api/jobs/{job_id}/cancel").json()
    second = client.post(f"/api/jobs/{job_id}/cancel").json()

    assert (first, second) == ({"cancelled": True}, {"cancelled": False})
    assert client.get("/api/videos/sm000000005").json()["video"]["status"] == "not_downloaded"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/videos/nosuchvideo"),
        ("post", "/api/videos/nosuchvideo/play"),
        ("post", "/api/videos/nosuchvideo/reveal"),
        ("post", "/api/videos/nosuchvideo/retry"),
    ],
)
def test_an_unknown_video_is_not_found(client: TestClient, method: str, path: str) -> None:
    """R-ER-02: every action on a video needs a video of a catalogue."""
    answer = getattr(client, method)(path)

    assert answer.status_code == 404
    assert answer.json()["error"]["code"] == "NOT_FOUND"
