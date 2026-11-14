"""Tests of ``ytmirror.core.quality``."""

import pytest

from ytmirror.core.channels import Quality
from ytmirror.core.quality import BEST_SELECTOR, effective_quality, format_selector


def test_best_available_asks_for_the_best_video_and_audio() -> None:
    """R-QL-01, R-QL-04: "Best available" takes the best video and audio streams."""
    assert format_selector(Quality.BEST) == BEST_SELECTOR == "bv*+ba/b"


@pytest.mark.parametrize(
    ("quality", "height"),
    [
        (Quality.P2160, 2160),
        (Quality.P1440, 1440),
        (Quality.P1080, 1080),
        (Quality.P720, 720),
        (Quality.P480, 480),
    ],
)
def test_a_height_means_the_best_not_above_it_and_else_the_lowest(
    quality: Quality, height: int
) -> None:
    """R-QL-01: the best quality not above the height, else the lowest available."""
    assert format_selector(quality) == f"bv*[height<={height}]+ba/b[height<={height}]/wv*+ba/w"


def test_every_quality_chooses_streams_and_never_a_conversion() -> None:
    """R-QL-04: the selector only chooses streams. Merging into MKV copies them."""
    for quality in Quality:
        selector = format_selector(quality)
        assert "+ba" in selector
        assert "ext" not in selector
        assert "vcodec" not in selector


def test_a_channel_quality_overrides_the_default() -> None:
    """R-QL-02: a channel with its own quality uses it."""
    assert effective_quality(Quality.P720, default_quality=Quality.BEST) is Quality.P720


def test_a_channel_without_a_quality_uses_the_default() -> None:
    """R-QL-02: a channel without an override uses the default quality."""
    assert effective_quality(None, default_quality=Quality.P1080) is Quality.P1080
