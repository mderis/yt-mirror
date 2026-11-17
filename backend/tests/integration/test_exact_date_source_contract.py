"""Contract of the ExactDateSource port, run against the fake and the real adapter.

The fake reads the videos of a fake YouTube. The real adapter asks a local
server that answers for the same videos as the API would.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.fixtures.youtube_api_server import (
    ApiServer,
    Asked,
    api_server,
    error_body,
    premiere,
    regular,
)
from ytmirror.adapters.fixture_youtube import FixtureYouTube
from ytmirror.adapters.fixture_youtube_api import FixtureYouTubeApi
from ytmirror.adapters.youtube_api import YouTubeApi
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.ports.exact_date_source import ExactDateSource

GOOD = "fixture-good-key"
BAD = "fixture-invalid-key"
SPENT = "fixture-quota-key"
REGULAR, PREMIERE, UPCOMING, MISSING = "reg00000001", "pre00000001", "up000000001", "mis00000001"


def fake(folder: Path) -> ExactDateSource:
    """Return the fake API over a fake YouTube with the four kinds of video."""
    channel: dict[str, Any] = {
        "id": "UCcontractchannel0000001",
        "title": "Contract",
        "listed_at": "2026-11-14T06:42:00Z",
        "video_count": 4,
        "videos": [
            {
                "id": REGULAR,
                "title": "R",
                "point": "2026-11-05",
                "published_at": "2026-11-03T08:30:15Z",
            },
            {
                "id": PREMIERE,
                "title": "P",
                "point": "2026-11-05",
                "published_at": "2018-10-27T17:13:22Z",
                "release_at": "2018-10-27T17:15:10Z",
            },
            {"id": UPCOMING, "title": "U", "point": "2026-11-05", "upcoming": True},
            {"id": MISSING, "title": "M", "point": "2026-11-05", "api_missing": True},
        ],
    }
    (folder / "contract.json").write_text(json.dumps(channel), encoding="utf-8")
    return FixtureYouTubeApi(FixtureYouTube(folder).api_date)


def _answer(state: ApiServer, asked: Asked) -> tuple[int, Any]:
    key = asked.headers.get("x-goog-api-key", "")
    if key.startswith("fixture-invalid"):
        return 400, error_body("keyInvalid")
    if key.startswith("fixture-quota"):
        return 403, error_body("quotaExceeded")
    ids = asked.query.get("id", [""])[0].split(",")
    return 200, {"items": [state.items[i] for i in ids if i in state.items]}


@pytest.fixture(params=["fake", "real"])
def source(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[ExactDateSource]:
    """Each adapter, with the same four videos."""
    if request.param == "fake":
        yield fake(tmp_path)
        return
    with api_server(_answer) as server:
        server.items = {
            REGULAR: regular(REGULAR, "2026-11-03T08:30:15Z"),
            PREMIERE: premiere(PREMIERE, "2018-10-27T17:13:22Z", "2018-10-27T17:15:10Z"),
            UPCOMING: premiere(UPCOMING, "2026-11-20T10:00:00Z", None),
        }
        yield YouTubeApi(server.address)


def test_the_dates_of_the_videos_the_api_returns(source: ExactDateSource) -> None:
    """R-DT-03, R-DT-05, D-082, D-083: release time, upload time, none yet, left out."""
    dates = source.video_dates(GOOD, [REGULAR, PREMIERE, UPCOMING, MISSING])

    assert dict(dates) == {REGULAR: 1_793_694_615, PREMIERE: 1_540_660_510, UPCOMING: None}


def test_a_key_that_works_passes_the_test(source: ExactDateSource) -> None:
    """R-DT-12: "Test key" with a good key raises nothing."""
    source.test_key(GOOD)


@pytest.mark.parametrize(
    ("key", "code"), [(BAD, ErrorCode.API_KEY_INVALID), (SPENT, ErrorCode.API_QUOTA_EXCEEDED)]
)
def test_a_failing_key_has_its_code(source: ExactDateSource, key: str, code: ErrorCode) -> None:
    """R-DT-12: an invalid key and a used-up quota fail with their own codes."""
    with pytest.raises(AppError) as asked:
        source.video_dates(key, [REGULAR])
    with pytest.raises(AppError) as tested:
        source.test_key(key)

    assert asked.value.code is tested.value.code is code


def test_more_than_50_ids_are_refused(source: ExactDateSource) -> None:
    """R-DT-05: one request takes at most 50 IDs."""
    with pytest.raises(ValueError, match="50"):
        source.video_dates(GOOD, [REGULAR] * 51)
