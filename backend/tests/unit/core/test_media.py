"""Tests of ``ytmirror.core.media``."""

import dataclasses

import pytest

from ytmirror.core.media import MediaFacts, verification_problem

GOOD = MediaFacts(
    container="matroska,webm",
    duration_s=600.4,
    width=1920,
    height=1080,
    fps=30.0,
    vcodec="av1",
    acodec="opus",
    audio_channels=2,
)


def test_a_complete_mkv_of_the_right_length_passes() -> None:
    """R-QL-03, R-QA-06: a finished MKV with video and audio of the right length is accepted."""
    assert verification_problem(GOOD, expected_duration_s=600) is None
    assert verification_problem(GOOD, expected_duration_s=None) is None


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"container": "mov,mp4,m4a,3gp,3g2,mj2"}, "not MKV"),
        ({"vcodec": None}, "no video stream"),
        ({"acodec": None}, "no audio stream"),
        ({"duration_s": 597.9}, "YouTube said 600 s"),
        ({"duration_s": None}, "YouTube said 600 s"),
    ],
)
def test_a_file_that_is_not_complete_fails(change: dict[str, object], reason: str) -> None:
    """R-QA-06: a file without a stream, of another length or not MKV never looks finished."""
    facts = dataclasses.replace(GOOD, **change)  # pyright: ignore[reportArgumentType]

    problem = verification_problem(facts, expected_duration_s=600)

    assert problem is not None
    assert reason in problem


def test_two_seconds_off_is_still_the_same_video() -> None:
    """R-QA-06: the duration may differ from YouTube's by up to two seconds."""
    assert verification_problem(dataclasses.replace(GOOD, duration_s=602.0), 600) is None
