"""Tests of the catalogue repository on a real, migrated database."""

import dataclasses
from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from tests.fixtures.catalogue import (
    CHANNEL_ID,
    NOW,
    OTHER_CHANNEL_ID,
    listing_of,
    make_channel,
    make_video,
    video_id,
)
from tests.fixtures.database import migrated_engine
from tests.fixtures.fakes.clock import FakeClock
from ytmirror.adapters.db.catalogue_repository import SqlCatalogueRepository
from ytmirror.core.catalogue import CheckChanges, changes_of_check
from ytmirror.core.channels import (
    Channel,
    ChannelTotals,
    CheckKind,
    DatePrecision,
    Quality,
    Video,
    VideoStatus,
)
from ytmirror.core.errors import ErrorCode
from ytmirror.core.status import NEW_FOR_S, is_new
from ytmirror.ports.catalogue_repository import CatalogueRepository


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    """A migrated database in a temp folder."""
    return migrated_engine(tmp_path)


@pytest.fixture
def repository(engine: Engine, clock: FakeClock) -> CatalogueRepository:
    """The repository under test."""
    return SqlCatalogueRepository(engine, clock)


def changes(
    inserted: list[Video] | None = None, updated: list[Video] | None = None
) -> CheckChanges:
    """Return the changes of a check that inserts and updates the given videos."""
    return CheckChanges(
        inserted=tuple(inserted or ()),
        updated=tuple(updated or ()),
        new=0,
        changed=0,
        removed=0,
        returned=0,
        read=0,
    )


def stored_times(engine: Engine, table: str, row_id: str) -> tuple[int, int]:
    """Return ``created_at`` and ``updated_at`` of one row."""
    with engine.connect() as connection:
        row = connection.execute(
            text(f"SELECT created_at, updated_at FROM {table} WHERE id = :id"),
            {"id": row_id},
        ).one()
    return row[0], row[1]


def test_a_new_database_has_no_channels(repository: CatalogueRepository) -> None:
    """R-UI-02: with nothing added there are no channels, which leads to the welcome screen."""
    assert repository.channels() == ()
    assert repository.channel(CHANNEL_ID) is None
    assert repository.videos(CHANNEL_ID) == ()
    assert repository.totals(new_since=0) == {}


def test_a_channel_is_stored_with_every_value(repository: CatalogueRepository) -> None:
    """R-CH-05: the folder, the quality and what to mirror of a channel are stored with it."""
    channel = dataclasses.replace(
        make_channel(folder="/Volumes/Media/Sample", folder_is_custom=True, paused=True),
        quality=Quality.P1080,
        auto_mirror=True,
        mirror_after=NOW - 1000,
        last_check_error=ErrorCode.NETWORK_UNREACHABLE,
        position=3,
    )

    repository.add_channel(channel)

    assert repository.channel(CHANNEL_ID) == channel
    assert repository.channels() == (channel,)


def test_a_channel_without_optional_values_is_stored_as_it_is(
    repository: CatalogueRepository,
) -> None:
    """R-CH-05: "use default" for the quality and no date limit are stored as nothing."""
    channel = dataclasses.replace(
        make_channel(
            handle=None, first_listed_at=None, last_check_at=None, last_full_check_at=None
        ),
        avatar_url=None,
    )

    repository.add_channel(channel)

    assert repository.channel(CHANNEL_ID) == channel


def test_channels_come_in_the_order_of_the_sidebar(repository: CatalogueRepository) -> None:
    """R-CH-34: the channels are listed by their position in the sidebar."""
    repository.add_channel(make_channel(OTHER_CHANNEL_ID, position=1))
    repository.add_channel(make_channel(CHANNEL_ID, position=0))

    assert [channel.id for channel in repository.channels()] == [CHANNEL_ID, OTHER_CHANNEL_ID]


def test_saving_a_channel_stores_its_current_values(
    repository: CatalogueRepository, engine: Engine, clock: FakeClock
) -> None:
    """R-CH-31: pausing a channel is stored, and the row says when it changed."""
    repository.add_channel(make_channel())
    created = stored_times(engine, "channels", CHANNEL_ID)
    clock.advance(60)

    repository.save_channel(make_channel(paused=True, title="A new name"))

    stored = repository.channel(CHANNEL_ID)
    assert stored is not None
    assert (stored.paused, stored.title) == (True, "A new name")
    assert stored_times(engine, "channels", CHANNEL_ID) == (created[0], created[1] + 60)


def test_saving_an_unchanged_channel_does_not_touch_the_row(
    repository: CatalogueRepository, engine: Engine, clock: FakeClock
) -> None:
    """infra: ``updated_at`` moves only when a value changed."""
    repository.add_channel(make_channel())
    before = stored_times(engine, "channels", CHANNEL_ID)
    clock.advance(60)

    repository.save_channel(make_channel())

    assert stored_times(engine, "channels", CHANNEL_ID) == before


def test_saving_a_channel_that_was_removed_does_not_bring_it_back(
    repository: CatalogueRepository,
) -> None:
    """R-CH-32: a removed channel stays removed, also when work on it finishes later."""
    repository.save_channel(make_channel())

    assert repository.channels() == ()


def test_the_catalogue_is_stored_and_read_in_channel_order(
    repository: CatalogueRepository,
) -> None:
    """R-CH-10: every video of a check is stored and comes back in the order of the channel."""
    repository.add_channel(make_channel())
    videos = [make_video(number, position=3 - number) for number in (1, 2, 3)]

    stored = repository.apply_check(make_channel(), changes(inserted=videos))

    assert stored is True
    assert repository.videos(CHANNEL_ID) == (videos[2], videos[1], videos[0])
    assert repository.video_ids(CHANNEL_ID) == {video_id(1), video_id(2), video_id(3)}
    assert repository.video(video_id(2)) == videos[1]
    assert repository.video("unknown") is None


def test_a_video_is_stored_with_every_value(repository: CatalogueRepository) -> None:
    """R-CH-10, R-DT-04: a video keeps all it has, also the precision of its date."""
    repository.add_channel(make_channel())
    video = dataclasses.replace(
        make_video(1, published_precision=DatePrecision.YEAR, missing_checks=2, gone=True),
        status=VideoStatus.FAILED,
        excluded=True,
        excluded_by="manual",
        exclude_exception=True,
        file_name="A video.mkv",
        file_size=431_821_004,
        height=1080,
        vcodec="av01",
        acodec="opus",
        has_subtitles="auto",
        downloaded_at=NOW,
        last_error_code=ErrorCode.RATE_LIMITED,
        last_error_at=NOW,
        attempts=2,
    )

    repository.apply_check(make_channel(), changes(inserted=[video]))

    assert repository.video(video.id) == video


def test_a_video_without_optional_values_is_stored_as_it_is(
    repository: CatalogueRepository,
) -> None:
    """R-DT-04: a video without duration, views or any date is stored without them."""
    repository.add_channel(make_channel())
    video = make_video(
        1, duration_s=None, view_count=None, published_at=None, published_precision=None
    )

    repository.apply_check(make_channel(), changes(inserted=[video]))

    assert repository.video(video.id) == video


def test_a_check_stores_the_channel_and_its_videos_together(
    repository: CatalogueRepository, engine: Engine, clock: FakeClock
) -> None:
    """R-CH-12: what a check changes is stored as one: inserted, updated and the channel."""
    repository.add_channel(make_channel(last_check_at=None, title="Old name"))
    repository.apply_check(make_channel(), changes(inserted=[make_video(1), make_video(2)]))
    created = stored_times(engine, "videos", video_id(1))
    clock.advance(60)
    checked = make_channel(last_check_at=NOW + 60, title="New name")

    repository.apply_check(
        checked,
        changes(inserted=[make_video(3)], updated=[make_video(1, title="New title", position=5)]),
    )

    assert repository.channel(CHANNEL_ID) == checked
    titles = {video.id: video.title for video in repository.videos(CHANNEL_ID)}
    assert titles == {video_id(1): "New title", video_id(2): "Video 2", video_id(3): "Video 3"}
    assert stored_times(engine, "videos", video_id(1)) == (created[0], created[1] + 60)
    assert stored_times(engine, "videos", video_id(2)) == created


def test_a_check_of_a_removed_channel_stores_nothing(repository: CatalogueRepository) -> None:
    """R-CH-32: a check that ends after its channel was removed leaves no catalogue behind."""
    stored = repository.apply_check(make_channel(), changes(inserted=[make_video(1)]))

    assert stored is False
    assert repository.video(video_id(1)) is None


def test_a_video_belongs_to_the_channel_that_listed_it_first(
    repository: CatalogueRepository,
) -> None:
    """R-CH-10: a video that two channels list is stored once, for the first of them."""
    repository.add_channel(make_channel(CHANNEL_ID))
    repository.add_channel(make_channel(OTHER_CHANNEL_ID, position=1))
    repository.apply_check(make_channel(CHANNEL_ID), changes(inserted=[make_video(1)]))
    shared = [
        make_video(1, channel_id=OTHER_CHANNEL_ID),
        make_video(2, channel_id=OTHER_CHANNEL_ID),
    ]

    repository.apply_check(make_channel(OTHER_CHANNEL_ID, position=1), changes(inserted=shared))

    assert repository.video_ids(CHANNEL_ID) == {video_id(1)}
    assert repository.video_ids(OTHER_CHANNEL_ID) == {video_id(2)}


def test_a_large_check_is_stored(repository: CatalogueRepository) -> None:
    """R-CH-11: the first listing of a large channel is stored in one piece."""
    repository.add_channel(make_channel())
    first = changes_of_check(
        CheckKind.FULL,
        [],
        listing_of(range(1, 1301)),
        channel_id=CHANNEL_ID,
        now=NOW,
        first_listing=True,
    )

    repository.apply_check(make_channel(), first)
    known = repository.videos(CHANNEL_ID)
    again = changes_of_check(
        CheckKind.FULL,
        known,
        listing_of(range(0, 1301)),
        channel_id=CHANNEL_ID,
        now=NOW + 60,
        first_listing=False,
    )
    repository.apply_check(make_channel(), again)

    stored = repository.videos(CHANNEL_ID)
    assert len(stored) == 1301
    assert [video.channel_position for video in stored] == list(range(1301))
    assert stored[0].id == video_id(0)


def test_removing_a_channel_removes_its_catalogue_and_nothing_else(
    repository: CatalogueRepository,
) -> None:
    """R-CH-32: the catalogue of a removed channel is deleted from the database."""
    repository.add_channel(make_channel(CHANNEL_ID))
    repository.add_channel(make_channel(OTHER_CHANNEL_ID, position=1))
    repository.apply_check(make_channel(CHANNEL_ID), changes(inserted=[make_video(1)]))
    repository.apply_check(
        make_channel(OTHER_CHANNEL_ID, position=1),
        changes(inserted=[make_video(2, channel_id=OTHER_CHANNEL_ID)]),
    )

    repository.remove_channel(CHANNEL_ID)
    repository.remove_channel("UCunknown")

    assert [channel.id for channel in repository.channels()] == [OTHER_CHANNEL_ID]
    assert repository.video(video_id(1)) is None
    assert repository.video(video_id(2)) is not None


def test_the_totals_of_a_channel_count_its_videos(repository: CatalogueRepository) -> None:
    """R-CH-35: the totals are the videos, the synced and excluded ones, and the size on disk."""
    repository.add_channel(make_channel())
    synced = dataclasses.replace(make_video(1, status=VideoStatus.SYNCED), file_size=400)
    also_synced = dataclasses.replace(make_video(2, status=VideoStatus.SYNCED), file_size=100)
    partly = dataclasses.replace(make_video(3), file_size=999)
    videos = [synced, also_synced, partly, make_video(4, excluded=True), make_video(5, gone=True)]
    repository.apply_check(make_channel(), changes(inserted=videos))

    totals = repository.totals(new_since=NOW)

    assert totals == {CHANNEL_ID: ChannelTotals(videos=5, synced=2, excluded=1, size_bytes=500)}


def test_the_count_of_new_videos_agrees_with_the_rule_for_one_video(
    repository: CatalogueRepository,
) -> None:
    """R-CH-34, R-CH-15: the count of new videos is the number of videos that are new."""
    now = NOW + NEW_FOR_S
    repository.add_channel(make_channel())
    videos = [
        make_video(1, seen_in_first_listing=False, first_seen_at=NOW + 1),
        make_video(2, seen_in_first_listing=False, first_seen_at=NOW),
        make_video(3, seen_in_first_listing=True, first_seen_at=NOW + 1),
        make_video(4, seen_in_first_listing=False, first_seen_at=NOW + 1, excluded=True),
        make_video(
            5, seen_in_first_listing=False, first_seen_at=NOW + 1, status=VideoStatus.SYNCED
        ),
        make_video(6, seen_in_first_listing=False, first_seen_at=now),
    ]
    repository.apply_check(make_channel(), changes(inserted=videos))

    totals = repository.totals(new_since=now - NEW_FOR_S)

    assert [is_new(video, now) for video in videos] == [True, False, False, False, False, True]
    assert totals[CHANNEL_ID].new == 2


def test_totals_are_kept_apart_by_channel(repository: CatalogueRepository) -> None:
    """R-CH-34: every channel has its own numbers."""
    other = make_channel(OTHER_CHANNEL_ID, position=1)
    repository.add_channel(make_channel())
    repository.add_channel(other)
    repository.apply_check(make_channel(), changes(inserted=[make_video(1), make_video(2)]))
    repository.apply_check(other, changes(inserted=[make_video(3, channel_id=OTHER_CHANNEL_ID)]))

    totals = repository.totals(new_since=NOW)

    assert (totals[CHANNEL_ID].videos, totals[OTHER_CHANNEL_ID].videos) == (2, 1)


def test_a_channel_read_back_is_a_plain_value(repository: CatalogueRepository) -> None:
    """infra: what the repository returns is a frozen value, not a row of the database."""
    repository.add_channel(make_channel())

    channel = repository.channel(CHANNEL_ID)

    assert type(channel) is Channel
