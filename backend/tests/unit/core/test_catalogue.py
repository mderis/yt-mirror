"""Tests of ``ytmirror.core.catalogue``."""

from collections.abc import Iterator

import pytest

from tests.fixtures.catalogue import CHANNEL_ID, NOW, listed, listing_of, make_video, video_id
from ytmirror.core.catalogue import (
    MISSES_UNTIL_GONE,
    QUICK_CHECK_STOPS_AFTER,
    CheckChanges,
    changes_of_check,
    listing_is_implausible,
    read_for_quick_check,
)
from ytmirror.core.channels import CheckKind, DatePrecision, ListedVideo, Video

LATER = NOW + 3600
DAY = 24 * 60 * 60


def check(
    kind: CheckKind,
    known: list[Video],
    read: list[ListedVideo],
    *,
    now: int = LATER,
    first_listing: bool = False,
) -> CheckChanges:
    """Run the rules of one check for the test channel."""
    return changes_of_check(
        kind, known, read, channel_id=CHANNEL_ID, now=now, first_listing=first_listing
    )


def after(known: list[Video], changes: CheckChanges) -> list[Video]:
    """Return the catalogue as it is once the changes are stored, in channel order."""
    by_id = {video.id: video for video in known}
    by_id.update({video.id: video for video in changes.updated})
    by_id.update({video.id: video for video in changes.inserted})
    return sorted(by_id.values(), key=lambda video: video.channel_position)


def numbers(videos: list[Video]) -> list[int]:
    """Return the numbers the videos were built from, in their order."""
    return [int(video.id.removeprefix("vid")) for video in videos]


def counting(videos: list[ListedVideo], taken: list[int]) -> Iterator[ListedVideo]:
    """Hand out a listing one video at a time and count how many were taken."""
    for video in videos:
        taken.append(1)
        yield video


# --- reading for a quick check


def test_a_quick_check_stops_after_a_full_page_of_known_videos() -> None:
    """R-CH-12: a quick check reads 30 known videos in a row and asks for nothing more."""
    taken: list[int] = []
    known = {video_id(number) for number in range(1, 201)}

    read = read_for_quick_check(counting(listing_of(range(1, 201)), taken), known)

    assert [entry.id for entry in read] == [video_id(number) for number in range(1, 31)]
    assert len(taken) == QUICK_CHECK_STOPS_AFTER == 30


def test_a_new_video_starts_the_count_of_known_videos_again() -> None:
    """R-CH-12: a new video between known ones is followed by a full page of known ones."""
    known = {video_id(number) for number in range(1, 201)} - {video_id(10)}
    taken: list[int] = []

    read = read_for_quick_check(counting(listing_of(range(1, 201)), taken), known)

    assert len(read) == 10 + QUICK_CHECK_STOPS_AFTER
    assert read[-1].id == video_id(40)


def test_new_videos_on_top_are_read_until_a_full_page_is_known() -> None:
    """R-CH-12: three new videos on top cost three more videos, not a whole listing."""
    known = {video_id(number) for number in range(4, 201)}

    read = read_for_quick_check(iter(listing_of(range(1, 201))), known)

    assert [entry.id for entry in read[:3]] == [video_id(1), video_id(2), video_id(3)]
    assert len(read) == 3 + QUICK_CHECK_STOPS_AFTER


def test_a_channel_shorter_than_a_page_is_read_to_its_end() -> None:
    """R-CH-12: a quick check of a small channel simply reads all of it."""
    known = {video_id(number) for number in range(1, 13)}

    read = read_for_quick_check(iter(listing_of(range(1, 13))), known)

    assert len(read) == 12


def test_a_quick_check_of_an_unknown_channel_reads_everything() -> None:
    """R-CH-12: with nothing known there is never a page of known videos."""
    read = read_for_quick_check(iter(listing_of(range(1, 101))), set())

    assert len(read) == 100


# --- the first listing


def test_the_first_listing_inserts_every_video_in_channel_order() -> None:
    """R-CH-12, R-CH-10: the first listing fills the catalogue, newest first."""
    changes = check(CheckKind.FULL, [], listing_of([3, 1, 2]), first_listing=True)

    assert numbers(list(changes.inserted)) == [3, 1, 2]
    assert [video.channel_position for video in changes.inserted] == [0, 1, 2]
    assert changes.updated == ()
    assert changes.read == 3


def test_videos_of_the_first_listing_cannot_be_new() -> None:
    """R-CH-15: only videos seen after the first listing are new."""
    changes = check(CheckKind.FULL, [], listing_of([1, 2]), first_listing=True)

    assert all(video.seen_in_first_listing for video in changes.inserted)
    assert changes.new == 0


def test_an_inserted_video_takes_what_the_listing_gives() -> None:
    """R-CH-10: title, duration, view count, date and thumbnail come from the listing."""
    entry = listed(
        1, title="A title", duration_s=754, view_count=4_100_000, published_at=LATER - 9 * DAY
    )

    video = check(CheckKind.FULL, [], [entry], first_listing=True).inserted[0]

    assert (video.id, video.channel_id) == (video_id(1), CHANNEL_ID)
    assert (video.title, video.duration_s, video.view_count) == ("A title", 754, 4_100_000)
    assert video.thumbnail_url == entry.thumbnail_url
    assert (video.first_seen_at, video.last_seen_at) == (LATER, LATER)
    assert (video.missing_checks, video.gone, video.excluded) == (0, False, False)


def test_an_approximate_date_is_stored_with_its_precision() -> None:
    """R-DT-04: the listed date is stored as approximate, with the unit it came in."""
    point = ((NOW // DAY) - 365) * DAY
    entry = listed(1, published_at=point, listed_at=NOW)

    video = check(CheckKind.FULL, [], [entry], first_listing=True).inserted[0]

    assert video.published_at == point
    assert video.published_exact is False
    assert video.published_precision is DatePrecision.YEAR


def test_a_video_without_a_listed_date_has_no_date_and_no_precision() -> None:
    """R-DT-04: when the listing gives no date at all, nothing is made up."""
    video = check(CheckKind.FULL, [], [listed(1, published_at=None)], first_listing=True).inserted[
        0
    ]

    assert video.published_at is None
    assert video.published_precision is None
    assert video.published_exact is False


def test_a_video_listed_twice_is_stored_once() -> None:
    """R-CH-12: a listing that repeats a video does not produce it twice."""
    changes = check(CheckKind.FULL, [], listing_of([1, 2, 1]), first_listing=True)

    assert numbers(list(changes.inserted)) == [1, 2]
    assert changes.read == 2


# --- what both kinds do


@pytest.mark.parametrize("kind", list(CheckKind))
def test_a_new_video_on_top_is_added_and_can_be_new(kind: CheckKind) -> None:
    """R-CH-12, R-CH-15: both kinds of check add a new video, and it counts as new."""
    known = [make_video(number, position=number - 1) for number in (1, 2, 3)]

    changes = check(kind, known, listing_of([9, 1, 2, 3]))

    assert numbers(list(changes.inserted)) == [9]
    assert changes.inserted[0].seen_in_first_listing is False
    assert changes.new == 1
    assert numbers(after(known, changes)) == [9, 1, 2, 3]


@pytest.mark.parametrize("kind", list(CheckKind))
def test_title_duration_and_views_of_a_read_video_are_updated(kind: CheckKind) -> None:
    """R-CH-12: both kinds of check update the title, duration and view count of what they read."""
    known = [make_video(1, title="Old title", duration_s=100, view_count=10, position=0)]
    entry = listed(1, title="New title", duration_s=101, view_count=25)

    changes = check(kind, known, [entry])

    video = changes.updated[0]
    assert (video.title, video.duration_s, video.view_count) == ("New title", 101, 25)
    assert changes.changed == 1
    assert changes.inserted == ()


@pytest.mark.parametrize("kind", list(CheckKind))
def test_a_value_the_listing_did_not_give_never_replaces_a_known_one(kind: CheckKind) -> None:
    """R-CH-12: a listing without duration, views or title leaves the known values alone."""
    known = [make_video(1, title="Known", duration_s=100, view_count=10, position=0)]
    entry = listed(1, title="", duration_s=None, view_count=None)

    changes = check(kind, known, [entry])

    video = after(known, changes)[0]
    assert (video.title, video.duration_s, video.view_count) == ("Known", 100, 10)
    assert changes.changed == 0


@pytest.mark.parametrize("kind", list(CheckKind))
def test_a_read_video_is_marked_as_seen_now(kind: CheckKind) -> None:
    """R-DT-01: "last seen" is the time of the last successful check that listed the video."""
    known = [make_video(1, last_seen_at=NOW, first_seen_at=NOW, position=0)]

    changes = check(kind, known, listing_of([1]), now=LATER)

    assert changes.updated[0].last_seen_at == LATER
    assert changes.updated[0].first_seen_at == NOW


@pytest.mark.parametrize("kind", list(CheckKind))
def test_the_first_approximate_date_is_kept(kind: CheckKind) -> None:
    """R-DT-04: a later listing never replaces a date, because it can only be coarser."""
    first_point = NOW - 13 * DAY
    known = [
        make_video(1, published_at=first_point, published_precision=DatePrecision.DAY, position=0)
    ]
    later_entry = listed(1, published_at=NOW - 30 * DAY)

    video = after(known, check(kind, known, [later_entry]))[0]

    assert video.published_at == first_point
    assert video.published_precision is DatePrecision.DAY


@pytest.mark.parametrize("kind", list(CheckKind))
def test_an_exact_date_is_never_touched_by_a_listing(kind: CheckKind) -> None:
    """R-DT-04: once a date is exact, the approximate date of a listing does not come back."""
    exact = NOW - 400 * DAY + 4711
    known = [make_video(1, published_at=exact, published_exact=True, published_precision=None)]

    video = after(known, check(kind, known, listing_of([1])))[0]

    assert (video.published_at, video.published_exact) == (exact, True)
    assert video.published_precision is None


@pytest.mark.parametrize("kind", list(CheckKind))
def test_a_video_without_a_date_takes_the_first_one_a_listing_gives(kind: CheckKind) -> None:
    """R-DT-04: "date pending" ends as soon as a listing has a date."""
    known = [make_video(1, published_at=None, published_precision=None, position=0)]
    point = ((LATER // DAY) - 3) * DAY

    video = after(known, check(kind, known, [listed(1, published_at=point, listed_at=LATER)]))[0]

    assert video.published_at == point
    assert video.published_precision is DatePrecision.DAY


@pytest.mark.parametrize("kind", list(CheckKind))
def test_a_removed_video_that_is_listed_again_is_no_longer_removed(kind: CheckKind) -> None:
    """R-CH-13: a video that is listed again is no longer removed from YouTube."""
    known = [make_video(1, missing_checks=2, gone=True, position=0)]

    changes = check(kind, known, listing_of([1]))

    assert (changes.updated[0].gone, changes.updated[0].missing_checks) == (False, 0)
    assert changes.returned == 1


@pytest.mark.parametrize("kind", list(CheckKind))
def test_a_check_that_changes_nothing_but_the_time_reports_no_change(kind: CheckKind) -> None:
    """R-CH-12: an unchanged channel has nothing new, changed, removed or returned."""
    known = [make_video(number, position=number - 1) for number in (1, 2, 3)]

    changes = check(kind, known, listing_of([1, 2, 3]))

    assert (changes.new, changes.changed, changes.removed, changes.returned) == (0, 0, 0, 0)
    assert changes.inserted == ()
    assert numbers(after(known, changes)) == [1, 2, 3]


# --- what only a quick check does


def test_a_quick_check_never_counts_a_video_it_did_not_read_as_missing() -> None:
    """R-CH-13: a quick check never marks anything as removed and does not count."""
    known = [make_video(number, position=number - 1) for number in range(1, 6)]

    changes = check(CheckKind.QUICK, known, listing_of([1, 2]))

    unread = [
        video for video in after(known, changes) if video.id not in (video_id(1), video_id(2))
    ]
    assert all((video.missing_checks, video.gone) == (0, False) for video in unread)
    assert changes.removed == 0


def test_a_quick_check_leaves_the_count_of_misses_as_it_was() -> None:
    """R-CH-13: a quick check neither counts as a miss nor breaks the sequence of misses."""
    known = [make_video(1, position=0), make_video(2, missing_checks=1, position=1)]

    changes = check(CheckKind.QUICK, known, listing_of([1]))

    video = next(video for video in after(known, changes) if video.id == video_id(2))
    assert (video.missing_checks, video.gone) == (1, False)
    assert video.last_seen_at == NOW


def test_a_quick_check_keeps_the_rest_of_the_channel_behind_what_it_read() -> None:
    """R-CH-12: videos a quick check did not read keep their order after the new ones."""
    known = [make_video(number, position=number - 1) for number in range(1, 61)]

    changes = check(CheckKind.QUICK, known, listing_of([91, 92, *range(1, 31)]))

    assert numbers(after(known, changes)) == [91, 92, *range(1, 61)]


def test_a_new_video_between_two_older_known_ones_takes_its_place() -> None:
    """R-CH-12: a new video that YouTube lists between known ones is placed between them."""
    known = [make_video(number, position=number - 1) for number in range(1, 41)]
    read = listing_of([1, 2, 99, *range(3, 33)])

    changes = check(CheckKind.QUICK, known, read)

    assert numbers(after(known, changes)) == [1, 2, 99, *range(3, 41)]
    assert changes.new == 1


def test_a_known_video_that_a_quick_check_did_not_meet_keeps_its_place() -> None:
    """R-CH-14: a video that vanished from the top of the listing stays where it was in the list."""
    known = [make_video(number, position=number - 1) for number in range(1, 36)]
    read = listing_of([1, 2, 4, 5, *range(6, 34)])

    changes = check(CheckKind.QUICK, known, read)

    assert numbers(after(known, changes)) == list(range(1, 36))
    assert next(v for v in after(known, changes) if v.id == video_id(3)).missing_checks == 0


# --- what only a full check does


def test_a_full_check_counts_a_video_that_is_not_listed() -> None:
    """R-CH-13: one full check without a video counts one miss and marks nothing."""
    known = [make_video(number, position=number - 1) for number in (1, 2, 3)]

    changes = check(CheckKind.FULL, known, listing_of([1, 3]))

    missed = next(video for video in changes.updated if video.id == video_id(2))
    assert (missed.missing_checks, missed.gone) == (1, False)
    assert changes.removed == 0


def test_two_full_checks_in_a_row_without_a_video_mark_it_as_removed() -> None:
    """R-CH-13: a video is removed from YouTube after two consecutive full checks without it."""
    known = [make_video(1, position=0), make_video(2, missing_checks=1, position=1)]

    changes = check(CheckKind.FULL, known, listing_of([1]))

    missed = next(video for video in changes.updated if video.id == video_id(2))
    assert (missed.missing_checks, missed.gone) == (MISSES_UNTIL_GONE, True)
    assert changes.removed == 1


def test_a_removed_video_stays_in_the_catalogue_in_its_place() -> None:
    """R-CH-14: a removed video stays in the list, where it was, and is never deleted."""
    known = [make_video(number, position=number - 1) for number in (1, 2, 3)]
    known[1] = make_video(2, missing_checks=1, position=1)

    changes = check(CheckKind.FULL, known, listing_of([9, 1, 3]))

    assert numbers(after(known, changes)) == [9, 1, 2, 3]
    assert next(v for v in after(known, changes) if v.id == video_id(2)).gone is True


def test_a_video_that_stays_removed_is_not_counted_as_removed_again() -> None:
    """R-CH-13: the count of removed videos of a check names only the newly removed ones."""
    known = [make_video(1, position=0), make_video(2, missing_checks=2, gone=True, position=1)]

    changes = check(CheckKind.FULL, known, listing_of([1]))

    assert changes.removed == 0
    assert next(v for v in after(known, changes) if v.id == video_id(2)).gone is True


def test_being_listed_once_ends_the_sequence_of_misses() -> None:
    """R-CH-13: the two misses must be consecutive: a listing in between starts over."""
    known = [make_video(1, missing_checks=1, position=0)]

    listed_again = after(known, check(CheckKind.FULL, known, listing_of([1])))
    missed_again = check(CheckKind.FULL, listed_again, listing_of([2]))

    video = next(v for v in missed_again.updated if v.id == video_id(1))
    assert (video.missing_checks, video.gone) == (1, False)


def test_a_full_check_takes_the_order_of_the_listing() -> None:
    """R-CH-12: after a full check the videos are in the order of the channel."""
    known = [make_video(number, position=number - 1) for number in (1, 2, 3, 4)]

    changes = check(CheckKind.FULL, known, listing_of([4, 3, 2, 1]))

    assert numbers(after(known, changes)) == [4, 3, 2, 1]


def test_missing_videos_at_the_end_of_the_channel_stay_at_the_end() -> None:
    """R-CH-14: a removed video keeps its place also when it was the oldest."""
    known = [make_video(number, position=number - 1) for number in (1, 2, 3)]

    changes = check(CheckKind.FULL, known, listing_of([1, 2]))

    assert numbers(after(known, changes)) == [1, 2, 3]


# --- an empty listing


def test_an_empty_full_listing_of_a_channel_with_videos_is_not_believed() -> None:
    """R-CH-13: an empty check never marks anything as removed: it counts as failed."""
    assert listing_is_implausible(CheckKind.FULL, known=12, read=0) is True


@pytest.mark.parametrize(
    ("kind", "known", "read"),
    [
        (CheckKind.FULL, 0, 0),
        (CheckKind.FULL, 12, 11),
        (CheckKind.QUICK, 12, 0),
        (CheckKind.QUICK, 0, 0),
    ],
)
def test_every_other_listing_is_believed(kind: CheckKind, known: int, read: int) -> None:
    """R-CH-13: a channel without videos may be empty, and a quick check marks nothing anyway."""
    assert listing_is_implausible(kind, known=known, read=read) is False
