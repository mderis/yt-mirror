"""Live tests of the YouTube gateway: the only tests that ask the real YouTube.

Opt-in with ``uv run pytest -m live`` and never run in CI (docs/TESTING.md
section 8). They fail when the network or YouTube is not reachable, which
says nothing about the code.
"""

import itertools

import pytest

from ytmirror.adapters.system_clock import SystemClock
from ytmirror.adapters.ytdlp_gateway import YtDlpGateway
from ytmirror.core.catalogue import QUICK_CHECK_STOPS_AFTER
from ytmirror.core.channel_input import parse_channel_input
from ytmirror.core.dates import precision_of

pytestmark = pytest.mark.live

# The first channel of YouTube: one video since 2005, so the test stays small and stable.
SMALL_CHANNEL = "@jawed"
SMALL_CHANNEL_ID = "UC4QobU6STFB0P71PMvOGN5A"


def test_a_known_public_channel_is_looked_up_and_listed() -> None:
    """R-QA-02, R-CH-03, R-CH-12: the real YouTube answers a lookup and a listing."""
    gateway = YtDlpGateway(SystemClock())

    facts = gateway.lookup_channel(parse_channel_input(SMALL_CHANNEL))
    listing = gateway.list_channel(facts.channel_id)
    videos = list(itertools.islice(listing.videos, QUICK_CHECK_STOPS_AFTER))

    assert facts.channel_id == SMALL_CHANNEL_ID
    assert facts.handle == SMALL_CHANNEL
    assert facts.avatar_url
    assert listing.facts.channel_id == SMALL_CHANNEL_ID
    assert len(videos) >= 1
    oldest = videos[-1]
    assert len(oldest.id) == 11
    assert oldest.title
    assert oldest.published_at is not None
    assert precision_of(oldest.published_at, oldest.listed_at).value == "year"


def test_the_pictures_of_a_real_channel_are_fetched() -> None:
    """R-QA-02, R-CH-16: an avatar and a thumbnail of the real YouTube arrive as pictures."""
    gateway = YtDlpGateway(SystemClock())
    listing = gateway.list_channel(SMALL_CHANNEL_ID)
    video = next(listing.videos)
    assert listing.facts.avatar_url is not None
    assert video.thumbnail_url is not None

    avatar = gateway.fetch_image(listing.facts.avatar_url)
    thumbnail = gateway.fetch_image(video.thumbnail_url)

    assert len(avatar) > 1000
    assert len(thumbnail) > 1000


def test_the_video_count_of_a_real_channel_is_given() -> None:
    """R-QA-02, R-CH-03: the playlist of long videos still gives the count of a channel."""
    assert YtDlpGateway(SystemClock()).preview_video_count(SMALL_CHANNEL_ID) == 1
