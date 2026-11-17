"""Stores what the exact-date fetch finds and keeps, in ``videos`` and ``date_fetch_queue``.

Implements the DateRepository port. This module must not decide when a
video is tried again: it is told.

Tests: backend/tests/integration/db/test_date_repository.py
"""

from collections.abc import Callable, Mapping, Sequence

from sqlalchemy import Engine, Select, and_, delete, or_, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from ytmirror.adapters.db.engine import for_reading
from ytmirror.adapters.db.tables import ChannelRow, DateFetchRow, VideoRow
from ytmirror.core.errors import ErrorCode
from ytmirror.core.exact_dates import FetchState, PendingDate
from ytmirror.ports.clock import Clock

_CHUNK = 500
"""How many IDs go into one "IN" list: SQLite limits the number of values of a statement."""


class SqlDateRepository:
    """Reads the videos that wait for an exact date, and stores what the fetch finds."""

    def __init__(self, engine: Engine, clock: Clock) -> None:
        """Create the repository.

        Args:
            engine: The database engine.
            clock: The source of the ``created_at`` and ``updated_at`` times.
        """
        self._engine = engine
        self._reader = for_reading(engine)
        self._clock = clock

    def pending(self, now: int, *, limit: int, by_api: bool) -> tuple[PendingDate, ...]:
        """Return the next videos the fetch may look up now, in the order of the fetch."""
        query = _waiting(now, by_api=by_api).add_columns(VideoRow.id).limit(limit)
        with Session(self._reader) as session:
            return tuple(
                PendingDate(video_id=video_id, channel_id=channel_id)
                for channel_id, video_id in session.execute(query)
            )

    def waiting_channels(self, now: int, *, by_api: bool) -> tuple[str, ...]:
        """Return the channel of every video the fetch may look up now, in fetch order."""
        with Session(self._reader) as session:
            return tuple(session.scalars(_waiting(now, by_api=by_api)))

    def set_exact(self, video_id: str, published_at: int) -> bool:
        """Store the exact time of a video that has none yet, and forget its fetch state."""
        with Session(self._engine) as session, session.begin():
            row = session.get(VideoRow, video_id)
            changed = row is not None and not row.published_exact and not row.gone
            if row is not None and changed:
                row.published_at = published_at
                row.published_exact = True
                row.published_precision = None
                row.updated_at = self._now()
            session.execute(delete(DateFetchRow).where(DateFetchRow.video_id == video_id))
        return changed

    def failed(
        self, video_id: str, code: ErrorCode, now: int, retry_after_s: Callable[[int], int]
    ) -> FetchState:
        """Count one more failed lookup of a video, and store when it may be tried again."""
        with Session(self._engine) as session, session.begin():
            row = session.get(DateFetchRow, video_id)
            if row is None:
                row = DateFetchRow(video_id=video_id, priority=0, attempts=0, created_at=now)
                session.add(row)
            row.attempts = (row.attempts or 0) + 1
            row.last_error = code.value
            row.next_try_at = now + retry_after_s(row.attempts)
            row.updated_at = now
            return FetchState(row.attempts, row.next_try_at, code)

    def left_out(self, video_ids: Sequence[str], now: int) -> None:
        """Note that the API gave no exact time for these videos (D-083)."""
        self._upsert(video_ids, {"api_left_out_at": now})

    def prioritize(self, video_ids: Sequence[str]) -> None:
        """Put videos at the front of the fetch (R-MI-03)."""
        self._upsert(video_ids, {"priority": 1})

    def fetch_states(self, channel_id: str) -> Mapping[str, FetchState]:
        """Return what the fetch keeps for the videos of a channel, by video."""
        with Session(self._reader) as session:
            rows = session.execute(
                select(DateFetchRow)
                .join(VideoRow, VideoRow.id == DateFetchRow.video_id)
                .where(VideoRow.channel_id == channel_id)
            ).scalars()
            return {
                row.video_id: FetchState(
                    attempts=row.attempts,
                    next_try_at=row.next_try_at,
                    last_error=None if row.last_error is None else ErrorCode(row.last_error),
                )
                for row in rows
            }

    def _upsert(self, video_ids: Sequence[str], values: dict[str, int]) -> None:
        now = self._now()
        with Session(self._engine) as session, session.begin():
            for start in range(0, len(video_ids), _CHUNK):
                known = list(
                    session.scalars(
                        select(VideoRow.id).where(
                            VideoRow.id.in_(video_ids[start : start + _CHUNK])
                        )
                    )
                )
                if not known:
                    continue
                statement = insert(DateFetchRow).values(
                    [
                        {"video_id": video_id, "created_at": now, "updated_at": now, **values}
                        for video_id in known
                    ]
                )
                session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[DateFetchRow.video_id],
                        set_={**values, "updated_at": now},
                    )
                )

    def _now(self) -> int:
        return int(self._clock.now().timestamp())


def _waiting(now: int, *, by_api: bool) -> Select[str]:
    """Return the query of the videos that wait, as their channel, in the order of the fetch."""
    conditions = [
        VideoRow.published_exact.is_(False),
        VideoRow.gone.is_(False),
        ChannelRow.paused.is_(False),
        or_(DateFetchRow.next_try_at.is_(None), DateFetchRow.next_try_at <= now),
    ]
    if by_api:
        conditions.append(
            or_(
                DateFetchRow.api_left_out_at.is_(None),
                ChannelRow.last_check_at.is_(None),
                DateFetchRow.api_left_out_at < ChannelRow.last_check_at,
            )
        )
    return (
        select(VideoRow.channel_id)
        .join(ChannelRow, ChannelRow.id == VideoRow.channel_id)
        .outerjoin(DateFetchRow, DateFetchRow.video_id == VideoRow.id)
        .where(and_(*conditions))
        .order_by(
            DateFetchRow.priority.desc().nulls_last(),
            VideoRow.published_at.desc().nulls_last(),
            VideoRow.channel_position,
            VideoRow.id,
        )
    )
