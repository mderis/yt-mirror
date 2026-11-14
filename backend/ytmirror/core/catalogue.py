"""What a check changes in the catalogue of a channel.

Implements R-CH-12 to R-CH-15 as functions of plain values: the known videos
and what a check read give the videos to insert and to update. A quick check
adds and updates and never marks anything as removed. Only a full check
counts the videos that were not listed, and marks a video as removed from
YouTube after two full checks in a row without it (docs/DECISIONS.md D-059).

This module must not read a clock, a database or YouTube.

Tests: backend/tests/unit/core/test_catalogue.py
"""

from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, replace

from ytmirror.core.channels import CheckKind, DatePrecision, ListedVideo, Video
from ytmirror.core.dates import precision_of

QUICK_CHECK_STOPS_AFTER = 30
"""A quick check stops after this many known videos in a row: one full page (R-CH-12)."""

MISSES_UNTIL_GONE = 2
"""Full checks in a row without a video until it counts as removed from YouTube (R-CH-13)."""


@dataclass(frozen=True, slots=True)
class CheckChanges:
    """What one successful check changes.

    Attributes:
        inserted: Videos the catalogue did not have.
        updated: Known videos with at least one changed value, as they are afterwards.
        new: How many of the inserted videos can be "new" (R-CH-15).
        changed: How many known videos got a new title, duration or view count.
        removed: How many videos this check marked as removed from YouTube.
        returned: How many videos that were removed are listed again.
        read: How many videos the check read.
    """

    inserted: tuple[Video, ...]
    updated: tuple[Video, ...]
    new: int
    changed: int
    removed: int
    returned: int
    read: int


def read_for_quick_check(
    videos: Iterable[ListedVideo], known_ids: Collection[str]
) -> list[ListedVideo]:
    """Read a listing from the newest video, as far as a quick check needs it (R-CH-12).

    Reading stops after 30 known videos in a row. A video the catalogue does
    not have starts the count again. A shorter listing is read to its end.

    Args:
        videos: The listing, newest first. Only as much as needed is taken from it.
        known_ids: The IDs of the videos the catalogue has.

    Returns:
        The videos that were read, in the order of the listing.
    """
    read: list[ListedVideo] = []
    known_in_a_row = 0
    for video in videos:
        read.append(video)
        known_in_a_row = known_in_a_row + 1 if video.id in known_ids else 0
        if known_in_a_row >= QUICK_CHECK_STOPS_AFTER:
            break
    return read


def listing_is_implausible(kind: CheckKind, known: int, read: int) -> bool:
    """Return whether a listing must be treated as a failed check (R-CH-13).

    A full listing without any video for a channel that had videos is never
    believed: an empty check marks nothing as removed.

    Args:
        kind: The kind of check.
        known: How many videos the catalogue has.
        read: How many videos the check read.
    """
    return kind is CheckKind.FULL and known > 0 and read == 0


def changes_of_check(
    kind: CheckKind,
    known: Sequence[Video],
    read: Sequence[ListedVideo],
    *,
    channel_id: str,
    now: int,
    first_listing: bool,
) -> CheckChanges:
    """Return what a successful check changes in the catalogue.

    Implements R-CH-12 to R-CH-15. A value the listing did not give never
    replaces a known one. The first approximate date of a video is kept.

    Args:
        kind: The kind of check.
        known: The videos of the channel as the catalogue has them.
        read: The videos the check read, in the order of the listing.
        channel_id: The channel.
        now: The time of the check, as seconds since the epoch.
        first_listing: Whether this is the first listing of the channel. Its
            videos are not "new".

    Returns:
        The videos to insert and to update, and the counts for the log.
    """
    known_by_id = {video.id: video for video in known}
    listed = _without_repeats(read)
    after: dict[str, Video] = {}
    for entry in listed:
        before = known_by_id.get(entry.id)
        after[entry.id] = (
            _first_seen(entry, channel_id, now, first_listing)
            if before is None
            else _seen_again(before, entry, now)
        )
    if kind is CheckKind.FULL:
        for video in known:
            if video.id not in after:
                after[video.id] = _missed(video)
    order = _merged_order([entry.id for entry in listed], [video.id for video in known])
    placed = {
        video_id: replace(after.get(video_id) or known_by_id[video_id], channel_position=position)
        for position, video_id in enumerate(order)
    }
    inserted = tuple(video for video_id, video in placed.items() if video_id not in known_by_id)
    updated = tuple(placed[video.id] for video in known if placed[video.id] != video)
    return CheckChanges(
        inserted=inserted,
        updated=updated,
        new=0 if first_listing else len(inserted),
        changed=sum(1 for video in updated if _facts(video) != _facts(known_by_id[video.id])),
        removed=sum(1 for video in updated if video.gone and not known_by_id[video.id].gone),
        returned=sum(1 for video in updated if not video.gone and known_by_id[video.id].gone),
        read=len(listed),
    )


def _without_repeats(read: Sequence[ListedVideo]) -> list[ListedVideo]:
    seen: set[str] = set()
    listed: list[ListedVideo] = []
    for entry in read:
        if entry.id not in seen:
            seen.add(entry.id)
            listed.append(entry)
    return listed


def _first_seen(entry: ListedVideo, channel_id: str, now: int, first_listing: bool) -> Video:
    return Video(
        id=entry.id,
        channel_id=channel_id,
        title=entry.title,
        duration_s=entry.duration_s,
        view_count=entry.view_count,
        published_at=entry.published_at,
        published_exact=False,
        published_precision=_precision(entry),
        thumbnail_url=entry.thumbnail_url,
        channel_position=0,
        first_seen_at=now,
        last_seen_at=now,
        seen_in_first_listing=first_listing,
    )


def _seen_again(before: Video, entry: ListedVideo, now: int) -> Video:
    has_no_date = before.published_at is None and entry.published_at is not None
    return replace(
        before,
        title=entry.title or before.title,
        duration_s=before.duration_s if entry.duration_s is None else entry.duration_s,
        view_count=before.view_count if entry.view_count is None else entry.view_count,
        published_at=entry.published_at if has_no_date else before.published_at,
        published_precision=_precision(entry) if has_no_date else before.published_precision,
        thumbnail_url=before.thumbnail_url or entry.thumbnail_url,
        last_seen_at=now,
        missing_checks=0,
        gone=False,
    )


def _missed(video: Video) -> Video:
    misses = video.missing_checks + 1
    return replace(video, missing_checks=misses, gone=video.gone or misses >= MISSES_UNTIL_GONE)


def _precision(entry: ListedVideo) -> DatePrecision | None:
    if entry.published_at is None:
        return None
    return precision_of(entry.published_at, entry.listed_at)


def _facts(video: Video) -> tuple[str, int | None, int | None]:
    return video.title, video.duration_s, video.view_count


def _merged_order(listed: Sequence[str], known: Sequence[str]) -> list[str]:
    """Return the order of all videos: the listed ones as listed, the others kept in place.

    A known video that was not listed stays in front of the known video that
    followed it before. Known videos behind the last listed one keep their
    order at the end. So a quick check, which reads only the top, leaves the
    rest of the channel as it was.
    """
    listed_ids = set(listed)
    in_front_of: dict[str, list[str]] = {}
    waiting: list[str] = []
    for video_id in known:
        if video_id in listed_ids:
            in_front_of[video_id] = waiting
            waiting = []
        else:
            waiting.append(video_id)
    order: list[str] = []
    for video_id in listed:
        order.extend(in_front_of.get(video_id, ()))
        order.append(video_id)
    order.extend(waiting)
    return order
