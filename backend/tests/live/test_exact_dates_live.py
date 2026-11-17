"""Live tests of the exact dates: one light lookup and one request of the YouTube API.

Opt-in with ``uv run pytest -m live`` and never run in CI (docs/TESTING.md
section 8). The test of the API runs only when ``YTM_YOUTUBE_API_KEY`` is set
in the environment; the key is taken from there and nowhere else, and never
written anywhere (R-LG-07).
"""

import os

import pytest

from ytmirror.adapters.system_clock import SystemClock
from ytmirror.adapters.youtube_api import YouTubeApi
from ytmirror.adapters.ytdlp_gateway import YtDlpGateway

pytestmark = pytest.mark.live

FIRST_VIDEO = "jNQXAC9IVRw"
"""The first video of YouTube, uploaded on 23 April 2005."""

PREMIERE = "F-00NhYUnH4"
"""A premiere measured in M4: uploaded at 1540660402, released at 1540660510."""
PREMIERE_RELEASE = 1_540_660_510


def test_the_light_lookup_gives_the_exact_time_of_a_video_and_of_a_premiere() -> None:
    """R-DT-03, R-DT-05: the lookup without a key, as measured in M4."""
    gateway = YtDlpGateway(SystemClock())

    first = gateway.exact_date(FIRST_VIDEO)
    premiere = gateway.exact_date(PREMIERE)

    assert first is not None
    assert 1_114_200_000 < first < 1_114_400_000
    assert premiere == PREMIERE_RELEASE


@pytest.mark.skipif(
    not os.environ.get("YTM_YOUTUBE_API_KEY"), reason="no YTM_YOUTUBE_API_KEY in the environment"
)
def test_the_youtube_api_gives_the_release_time_of_a_premiere() -> None:
    """R-DT-03, R-DT-05, D-082: videos.list by ID; a premiere's time is its actual start."""
    key = os.environ["YTM_YOUTUBE_API_KEY"]
    api = YouTubeApi()

    api.test_key(key)
    dates = api.video_dates(key, [FIRST_VIDEO, PREMIERE])

    assert dates[PREMIERE] == PREMIERE_RELEASE
    assert dates[FIRST_VIDEO] is not None
