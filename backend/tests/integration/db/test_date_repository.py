"""Tests of ``ytmirror.adapters.db.date_repository`` on a migrated database."""

from pathlib import Path

import pytest
from sqlalchemy import Engine

from tests.fixtures.catalogue import NOW, make_channel, make_video, video_id
from tests.fixtures.database import migrated_engine
from tests.fixtures.fakes.clock import FakeClock
from ytmirror.adapters.db.catalogue_repository import SqlCatalogueRepository
from ytmirror.adapters.db.date_repository import SqlDateRepository
from ytmirror.core.catalogue import CheckChanges
from ytmirror.core.channels import Channel, Video
from ytmirror.core.errors import ErrorCode
from ytmirror.core.exact_dates import FetchState, PendingDate
from ytmirror.ports.catalogue_repository import CatalogueRepository

DAY = 86_400
OTHER = "UCotherotherotherother02"


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    """A migrated database in a temp folder."""
    return migrated_engine(tmp_path)


@pytest.fixture
def catalogue(engine: Engine, clock: FakeClock) -> CatalogueRepository:
    """The catalogue, to store channels and videos."""
    return SqlCatalogueRepository(engine, clock)


@pytest.fixture
def dates(engine: Engine, clock: FakeClock) -> SqlDateRepository:
    """The repository under test."""
    return SqlDateRepository(engine, clock)


def store(catalogue: CatalogueRepository, channel: Channel, *videos: Video) -> None:
    """Store a channel with its videos."""
    catalogue.add_channel(channel)
    catalogue.apply_check(
        channel,
        CheckChanges(
            inserted=tuple(videos), updated=(), new=0, changed=0, removed=0, returned=0, read=0
        ),
    )


def ids(pending: tuple[PendingDate, ...]) -> list[str]:
    """Return the video IDs of pending videos."""
    return [entry.video_id for entry in pending]


def test_videos_without_an_exact_date_wait_newest_first(
    catalogue: CatalogueRepository, dates: SqlDateRepository
) -> None:
    """R-DT-05: the background fetch takes the newest videos first, across channels."""
    store(
        catalogue,
        make_channel(),
        make_video(1, published_at=NOW - 3 * DAY),
        make_video(2, published_at=NOW - 1 * DAY),
        make_video(3, published_at=NOW - 2 * DAY, published_exact=True, published_precision=None),
    )
    store(
        catalogue,
        make_channel(OTHER, folder="Other", position=1),
        make_video(4, channel_id=OTHER, published_at=NOW - 2 * DAY),
    )

    assert ids(dates.pending(NOW, limit=10, by_api=False)) == [
        video_id(2),
        video_id(4),
        video_id(1),
    ]
    assert dates.waiting_channels(NOW, by_api=False) == (
        make_channel().id,
        OTHER,
        make_channel().id,
    )


def test_a_decision_waiting_for_a_date_puts_the_video_first(
    catalogue: CatalogueRepository, dates: SqlDateRepository
) -> None:
    """R-DT-05, R-MI-03: videos whose exact date a decision waits for go to the front."""
    store(
        catalogue,
        make_channel(),
        make_video(1, published_at=NOW - 3 * DAY),
        make_video(2, published_at=NOW - 1 * DAY),
    )

    dates.prioritize([video_id(1), "unknown0001"])

    assert ids(dates.pending(NOW, limit=1, by_api=False)) == [video_id(1)]


def test_removed_videos_and_paused_channels_do_not_wait(
    catalogue: CatalogueRepository, dates: SqlDateRepository
) -> None:
    """R-DT-05: a removed video and a paused channel are not looked up."""
    store(catalogue, make_channel(), make_video(1, gone=True))
    store(
        catalogue,
        make_channel(OTHER, folder="Other", position=1, paused=True),
        make_video(2, channel_id=OTHER),
    )

    assert dates.pending(NOW, limit=10, by_api=False) == ()


def test_a_failed_lookup_waits_until_its_next_try(
    catalogue: CatalogueRepository, dates: SqlDateRepository
) -> None:
    """R-DT-13: a failed video is counted, and waits until it may be tried again."""
    store(catalogue, make_channel(), make_video(1))

    first = dates.failed(video_id(1), ErrorCode.VIDEO_PRIVATE, NOW, lambda attempts: 3600)
    second = dates.failed(video_id(1), ErrorCode.VIDEO_PRIVATE, NOW, lambda attempts: attempts * 10)

    assert first == FetchState(1, NOW + 3600, ErrorCode.VIDEO_PRIVATE)
    assert second == FetchState(2, NOW + 20, ErrorCode.VIDEO_PRIVATE)
    assert dates.pending(NOW + 19, limit=10, by_api=False) == ()
    assert ids(dates.pending(NOW + 20, limit=10, by_api=False)) == [video_id(1)]
    assert dates.fetch_states(make_channel().id) == {video_id(1): second}


def test_an_exact_time_is_stored_once_and_ends_the_wait(
    catalogue: CatalogueRepository, dates: SqlDateRepository
) -> None:
    """R-DT-05: the exact time replaces the approximate one and its precision."""
    store(catalogue, make_channel(), make_video(1))
    dates.failed(video_id(1), ErrorCode.VIDEO_PRIVATE, NOW - 7200, lambda attempts: 3600)

    assert dates.set_exact(video_id(1), NOW - 5000)
    assert not dates.set_exact(video_id(1), NOW - 1)

    video = catalogue.video(video_id(1))
    assert video is not None
    assert (video.published_at, video.published_exact, video.published_precision) == (
        NOW - 5000,
        True,
        None,
    )
    assert dates.fetch_states(make_channel().id) == {}
    assert dates.pending(NOW, limit=10, by_api=False) == ()


def test_an_exact_time_is_not_stored_for_a_removed_or_unknown_video(
    catalogue: CatalogueRepository, dates: SqlDateRepository
) -> None:
    """R-DT-05: only a video that waits gets an exact time from the fetch."""
    store(catalogue, make_channel(), make_video(1, gone=True))

    assert not dates.set_exact(video_id(1), NOW)
    assert not dates.set_exact("unknown0001", NOW)


def test_a_video_the_api_left_out_waits_for_the_next_check_of_its_channel(
    catalogue: CatalogueRepository, dates: SqlDateRepository, clock: FakeClock
) -> None:
    """R-DT-05, D-083: not asked of the API again before the next check; lookups still may."""
    channel = make_channel(last_check_at=NOW)
    store(catalogue, channel, make_video(1))

    dates.left_out([video_id(1)], NOW + 10)

    assert dates.pending(NOW + 20, limit=10, by_api=True) == ()
    assert ids(dates.pending(NOW + 20, limit=10, by_api=False)) == [video_id(1)]
    catalogue.update_channel(channel.id, last_check_at=NOW + 30)
    assert ids(dates.pending(NOW + 40, limit=10, by_api=True)) == [video_id(1)]


def test_the_state_of_a_video_goes_with_its_channel(
    catalogue: CatalogueRepository, dates: SqlDateRepository
) -> None:
    """R-QA-04: removing a channel removes what the fetch kept for its videos."""
    store(catalogue, make_channel(), make_video(1))
    dates.failed(video_id(1), ErrorCode.VIDEO_PRIVATE, NOW, lambda attempts: 3600)

    catalogue.remove_channel(make_channel().id)

    assert dates.fetch_states(make_channel().id) == {}
