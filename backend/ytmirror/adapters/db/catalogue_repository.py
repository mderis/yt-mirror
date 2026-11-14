"""Stores channels and videos in the ``channels`` and ``videos`` tables.

Implements the CatalogueRepository port. This module must not decide what a
check changes: it stores what it is given, in one transaction.

Tests: backend/tests/integration/db/test_catalogue_repository.py
"""

import dataclasses
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Engine, case, delete, func, insert, select, update
from sqlalchemy.orm import Session

from ytmirror.adapters.db.tables import ChannelRow, VideoRow
from ytmirror.core.catalogue import CheckChanges
from ytmirror.core.channels import (
    Channel,
    ChannelTotals,
    DatePrecision,
    Quality,
    Video,
    VideoStatus,
)
from ytmirror.core.errors import ErrorCode
from ytmirror.ports.clock import Clock

_CHUNK = 500
"""How many IDs go into one "IN" list: SQLite limits the number of values of a statement."""


class SqlCatalogueRepository:
    """Reads and writes rows of ``channels`` and ``videos``."""

    def __init__(self, engine: Engine, clock: Clock) -> None:
        """Create the repository.

        Args:
            engine: The database engine.
            clock: The source of the ``created_at`` and ``updated_at`` times.
        """
        self._engine = engine
        self._clock = clock

    def channels(self) -> tuple[Channel, ...]:
        """Return every channel, in the order of the sidebar."""
        with Session(self._engine) as session:
            rows = session.scalars(select(ChannelRow).order_by(ChannelRow.position, ChannelRow.id))
            return tuple(_channel_of(row) for row in rows)

    def channel(self, channel_id: str) -> Channel | None:
        """Return one channel, or None when it was not added.

        Args:
            channel_id: The channel ID.
        """
        with Session(self._engine) as session:
            row = session.get(ChannelRow, channel_id)
            return None if row is None else _channel_of(row)

    def add_channel(self, channel: Channel) -> None:
        """Store a new channel.

        Args:
            channel: The channel. Its ID must not be stored yet.
        """
        now = self._now()
        with Session(self._engine) as session, session.begin():
            session.add(ChannelRow(**_values_of(channel), created_at=now, updated_at=now))

    def save_channel(self, channel: Channel) -> None:
        """Store the current values of a channel that was added before.

        Args:
            channel: The channel as it is now.
        """
        with Session(self._engine) as session, session.begin():
            self._save_channel(session, channel)

    def remove_channel(self, channel_id: str) -> None:
        """Remove a channel and its whole catalogue (R-CH-32).

        Args:
            channel_id: The channel ID. An unknown one changes nothing.
        """
        with Session(self._engine) as session, session.begin():
            # The foreign key removes the videos with the channel.
            session.execute(delete(ChannelRow).where(ChannelRow.id == channel_id))

    def videos(self, channel_id: str) -> tuple[Video, ...]:
        """Return the catalogue of a channel, in the order of the channel (R-CH-10).

        Args:
            channel_id: The channel ID.
        """
        with Session(self._engine) as session:
            rows = session.scalars(
                select(VideoRow)
                .where(VideoRow.channel_id == channel_id)
                .order_by(VideoRow.channel_position, VideoRow.id)
            )
            return tuple(_video_of(row) for row in rows)

    def video_ids(self, channel_id: str) -> frozenset[str]:
        """Return the IDs of the videos of a channel.

        Args:
            channel_id: The channel ID.
        """
        with Session(self._engine) as session:
            ids = session.scalars(select(VideoRow.id).where(VideoRow.channel_id == channel_id))
            return frozenset(ids)

    def video(self, video_id: str) -> Video | None:
        """Return one video, or None when no catalogue has it.

        Args:
            video_id: The video ID.
        """
        with Session(self._engine) as session:
            row = session.get(VideoRow, video_id)
            return None if row is None else _video_of(row)

    def apply_check(self, channel: Channel, changes: CheckChanges) -> bool:
        """Store the result of a successful check in one transaction.

        Args:
            channel: The channel as it is after the check.
            changes: The videos to insert and to update.

        Returns:
            False when the channel is not stored (any more): then nothing was stored.
        """
        now = self._now()
        with Session(self._engine) as session, session.begin():
            if not self._save_channel(session, channel):
                return False
            taken = _ids_of_other_channels(session, channel.id, changes.inserted)
            fresh = [
                {**_values_of(video), "created_at": now, "updated_at": now}
                for video in changes.inserted
                if video.id not in taken
            ]
            if fresh:
                session.execute(insert(VideoRow), fresh)
            if changes.updated:
                session.execute(
                    update(VideoRow),
                    [{**_values_of(video), "updated_at": now} for video in changes.updated],
                )
        return True

    def totals(self, new_since: int) -> Mapping[str, ChannelTotals]:
        """Return the numbers of every channel that has videos, by channel ID.

        Args:
            new_since: A video first seen after this moment can still be new (R-CH-15).
        """
        synced = VideoRow.status == VideoStatus.SYNCED.value
        new = (
            VideoRow.seen_in_first_listing.is_(False)
            & VideoRow.excluded.is_(False)
            & ~synced
            & (VideoRow.first_seen_at > new_since)
        )
        query = select(
            VideoRow.channel_id,
            func.count(),
            func.sum(case((synced, 1), else_=0)),
            func.sum(case((VideoRow.excluded.is_(True), 1), else_=0)),
            func.sum(case((synced, func.coalesce(VideoRow.file_size, 0)), else_=0)),
            func.sum(case((new, 1), else_=0)),
        ).group_by(VideoRow.channel_id)
        with Session(self._engine) as session:
            return {
                channel_id: ChannelTotals(
                    videos=videos,
                    synced=synced_count,
                    excluded=excluded,
                    size_bytes=size,
                    new=new_count,
                )
                for channel_id, videos, synced_count, excluded, size, new_count in session.execute(
                    query
                )
            }

    def _save_channel(self, session: Session, channel: Channel) -> bool:
        row = session.get(ChannelRow, channel.id)
        if row is None:
            return False
        changed = False
        for name, value in _values_of(channel).items():
            if getattr(row, name) != value:
                setattr(row, name, value)
                changed = True
        if changed:
            row.updated_at = self._now()
        return True

    def _now(self) -> int:
        return int(self._clock.now().timestamp())


def _ids_of_other_channels(session: Session, channel_id: str, videos: Sequence[Video]) -> set[str]:
    """Return which of the videos another channel already has. A video has one channel."""
    ids = [video.id for video in videos]
    taken: set[str] = set()
    for start in range(0, len(ids), _CHUNK):
        taken.update(
            session.scalars(
                select(VideoRow.id).where(
                    VideoRow.id.in_(ids[start : start + _CHUNK]), VideoRow.channel_id != channel_id
                )
            )
        )
    return taken


def _values_of(item: Channel | Video) -> dict[str, Any]:
    """Return the columns of a channel or a video. An enum is stored by its value."""
    return {
        field.name: getattr(value, "value", value)
        for field in dataclasses.fields(item)
        for value in (getattr(item, field.name),)
    }


def _channel_of(row: ChannelRow) -> Channel:
    return Channel(
        id=row.id,
        url=row.url,
        title=row.title,
        handle=row.handle,
        avatar_url=row.avatar_url,
        folder=row.folder,
        folder_is_custom=row.folder_is_custom,
        quality=None if row.quality is None else Quality(row.quality),
        auto_mirror=row.auto_mirror,
        mirror_after=row.mirror_after,
        paused=row.paused,
        first_listed_at=row.first_listed_at,
        last_check_at=row.last_check_at,
        last_full_check_at=row.last_full_check_at,
        last_check_error=None if row.last_check_error is None else ErrorCode(row.last_check_error),
        position=row.position,
    )


def _video_of(row: VideoRow) -> Video:
    precision = row.published_precision
    error = row.last_error_code
    return Video(
        id=row.id,
        channel_id=row.channel_id,
        title=row.title,
        duration_s=row.duration_s,
        view_count=row.view_count,
        published_at=row.published_at,
        published_exact=row.published_exact,
        published_precision=None if precision is None else DatePrecision(precision),
        thumbnail_url=row.thumbnail_url,
        channel_position=row.channel_position,
        first_seen_at=row.first_seen_at,
        last_seen_at=row.last_seen_at,
        seen_in_first_listing=row.seen_in_first_listing,
        status=VideoStatus(row.status),
        excluded=row.excluded,
        excluded_by=row.excluded_by,
        exclude_exception=row.exclude_exception,
        missing_checks=row.missing_checks,
        gone=row.gone,
        file_name=row.file_name,
        file_size=row.file_size,
        height=row.height,
        vcodec=row.vcodec,
        acodec=row.acodec,
        has_subtitles=row.has_subtitles,
        downloaded_at=row.downloaded_at,
        last_error_code=None if error is None else ErrorCode(error),
        last_error_at=row.last_error_at,
        attempts=row.attempts,
    )
