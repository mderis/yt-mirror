"""Tests of ``ytmirror.core.progress``: one progress for the whole Mirror."""

from hypothesis import given
from hypothesis import strategies as st

from ytmirror.core.progress import (
    SUBTITLES_ESTIMATE,
    THUMBNAIL_ESTIMATE,
    PartKind,
    PlannedPart,
    ProgressTracker,
    stream_size,
)

MB = 1_000_000


def mirror(video: int | None = 400 * MB, audio: int | None = 100 * MB) -> ProgressTracker:
    """A download of a thumbnail, subtitles, a video stream and an audio stream."""
    return ProgressTracker(
        [
            PlannedPart("thumbnail", PartKind.THUMBNAIL, None),
            PlannedPart("subtitles", PartKind.SUBTITLES, None),
            PlannedPart("397", PartKind.VIDEO, video),
            PlannedPart("251", PartKind.AUDIO, audio),
        ]
    )


def test_video_and_audio_count_together_from_0_to_100_percent_once() -> None:
    """R-QU-04: the second stream does not start again at 0%."""
    tracker = mirror()
    tracker.finish_kind(PartKind.THUMBNAIL, 0)
    tracker.finished("subtitles", PartKind.SUBTITLES, 50_000, 0)

    halfway_video = tracker.arrived("397", PartKind.VIDEO, 200 * MB, 400 * MB, 1)
    video_done = tracker.finished("397", PartKind.VIDEO, 400 * MB, 2)
    audio_started = tracker.arrived("251", PartKind.AUDIO, 10 * MB, 100 * MB, 3)
    done = tracker.finished("251", PartKind.AUDIO, 100 * MB, 4)

    assert 0.39 < halfway_video.fraction < 0.41
    assert 0.79 < video_done.fraction < 0.81
    assert audio_started.fraction > video_done.fraction
    assert done.fraction == 1.0
    assert done.total_bytes == 500 * MB + 50_000 + THUMBNAIL_ESTIMATE


def test_unknown_sizes_are_estimated_and_corrected() -> None:
    """R-QU-04: a size YouTube did not give is estimated, then the real one is used."""
    tracker = mirror(audio=None)

    early = tracker.arrived("397", PartKind.VIDEO, 0, None, 0)
    told = tracker.arrived("251", PartKind.AUDIO, 1, 90 * MB, 1)

    audio = next(part for part in early.parts if part.kind is PartKind.AUDIO)
    assert audio.estimated
    assert audio.size == SUBTITLES_ESTIMATE
    corrected = next(part for part in told.parts if part.kind is PartKind.AUDIO)
    assert (corrected.size, corrected.estimated) == (90 * MB, False)


def test_the_percent_never_goes_down_when_an_estimate_was_too_small() -> None:
    """R-QU-04, D-088: a larger real size makes the percent wait, never go back."""
    tracker = mirror(video=None, audio=None)
    before = tracker.arrived("397", PartKind.VIDEO, 90_000, None, 0)

    after = tracker.arrived("397", PartKind.VIDEO, 100_000, 400 * MB, 1)

    assert after.fraction >= before.fraction
    assert after.fraction < 1.0


def test_the_percent_stays_below_100_until_every_part_is_finished() -> None:
    """R-QU-04: estimates that were too small never show 100% before the end."""
    tracker = ProgressTracker([PlannedPart("251", PartKind.AUDIO, 1000)])

    over = tracker.arrived("251", PartKind.AUDIO, 5000, None, 0)

    assert over.fraction < 1.0


@given(
    st.lists(
        st.tuples(
            st.sampled_from(["397", "251", "subtitles"]),
            st.integers(0, 600 * MB),
            st.one_of(st.none(), st.integers(1, 600 * MB)),
        ),
        max_size=40,
    )
)
def test_whatever_yt_dlp_reports_the_percent_never_goes_down(
    reports: list[tuple[str, int, int | None]],
) -> None:
    """R-QU-04, D-088: property: the percent shown only grows."""
    tracker = mirror(video=None, audio=50 * MB)
    kinds = {"397": PartKind.VIDEO, "251": PartKind.AUDIO, "subtitles": PartKind.SUBTITLES}
    shown = 0.0
    for second, (key, done, size) in enumerate(reports):
        fraction = tracker.arrived(key, kinds[key], done, size, float(second)).fraction
        assert fraction >= shown
        assert 0.0 <= fraction <= 1.0
        shown = fraction


def test_the_time_left_is_told_only_once_the_speed_is_stable() -> None:
    """R-QU-04: the time left comes from the measured speed, left out at first."""
    tracker = mirror(video=100 * MB, audio=None)

    first = tracker.arrived("397", PartKind.VIDEO, 0, 100 * MB, 0)
    soon = tracker.arrived("397", PartKind.VIDEO, 2 * MB, 100 * MB, 2)
    stable = tracker.arrived("397", PartKind.VIDEO, 6 * MB, 100 * MB, 6)

    assert first.left_s is None
    assert soon.left_s is None
    assert stable.speed_bps == 1 * MB
    assert stable.left_s is not None
    assert 90 < stable.left_s < 100


def test_a_part_that_was_not_planned_is_added() -> None:
    """R-QU-04: a stream yt-dlp fetches that the plan did not name still counts."""
    tracker = ProgressTracker([])

    totals = tracker.arrived("140", PartKind.AUDIO, 10, 100, 0)

    assert [part.kind for part in totals.parts] == [PartKind.AUDIO]


def test_the_size_of_a_stream_comes_from_what_yt_dlp_knows() -> None:
    """R-QU-04: exact size, else yt-dlp's estimate, else bitrate and length."""
    assert stream_size(1000, 900, 128.0, 60.0) == 1000
    assert stream_size(None, 900, 128.0, 60.0) == 900
    assert stream_size(None, None, 128.0, 60.0) == 960_000
    assert stream_size(None, None, None, 60.0) is None


def test_a_plan_without_streams_is_not_done_when_only_the_small_parts_are() -> None:
    """R-QU-04: 100% needs a finished stream, not only the subtitles and the thumbnail."""
    tracker = ProgressTracker(
        [
            PlannedPart("thumbnail", PartKind.THUMBNAIL, None),
            PlannedPart("subtitles", PartKind.SUBTITLES, None),
        ]
    )
    tracker.finish_kind(PartKind.THUMBNAIL, 0)

    early = tracker.finished("subtitles", PartKind.SUBTITLES, 40_000, 1)

    assert early.fraction < 1.0


def test_streams_that_differ_from_the_plan_replace_it_and_the_percent_ends_at_100() -> None:
    """R-QU-04, D-088: the planned streams that never come do not hold the percent back."""
    tracker = mirror()
    shown = tracker.arrived("399", PartKind.VIDEO, 100 * MB, 300 * MB, 0).fraction

    tracker.finished("399", PartKind.VIDEO, 300 * MB, 1)
    tracker.arrived("140", PartKind.AUDIO, 10 * MB, 50 * MB, 2)
    done = tracker.finished("140", PartKind.AUDIO, 50 * MB, 3)
    tracker.finish_kind(PartKind.THUMBNAIL, 3)
    done = tracker.finished("subtitles", PartKind.SUBTITLES, 40_000, 4)

    assert done.fraction == 1.0 > shown
    assert {part.kind for part in done.parts} == set(PartKind)
    assert done.total_bytes == 350 * MB + 40_000 + THUMBNAIL_ESTIMATE


def test_an_estimate_grows_as_its_bytes_arrive() -> None:
    """R-QU-04: an estimated size never stays below the bytes that came."""
    tracker = mirror(audio=None)

    grown = tracker.arrived("251", PartKind.AUDIO, 3 * SUBTITLES_ESTIMATE, None, 0)

    audio = next(part for part in grown.parts if part.kind is PartKind.AUDIO)
    assert audio.size == 3 * SUBTITLES_ESTIMATE
    assert audio.estimated
