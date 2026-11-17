"""The DateRepository port: the videos that wait for an exact date, and what the fetch keeps.

Implements the storage of R-DT-05, R-DT-06 and R-DT-13. A video waits for
its exact date while it has none, is not removed from YouTube and its
channel is not paused. The order is the order of the fetch: videos a
decision waits for first (R-MI-03), then the newest. What the fetch keeps
for a video (failures, when it may be tried again, when the API left it
out) survives restarts.

Tests: backend/tests/integration/db/test_date_repository.py
"""

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol

from ytmirror.core.errors import ErrorCode
from ytmirror.core.exact_dates import FetchState, PendingDate


class DateRepository(Protocol):
    """Reads the videos that wait for an exact date, and stores what the fetch finds."""

    def pending(self, now: int, *, limit: int, by_api: bool) -> tuple[PendingDate, ...]:
        """Return the next videos the fetch may look up now, in the order of the fetch.

        Args:
            now: The time now. A video that failed waits until its next try.
            limit: How many at most.
            by_api: Whether they are for the YouTube API: then a video the API left
                out since the last check of its channel is skipped (D-083).
        """
        ...

    def waiting_channels(self, now: int, *, by_api: bool) -> tuple[str, ...]:
        """Return the channel of every video the fetch may look up now, in the order of the fetch.

        Args:
            now: The time now.
            by_api: Whether for the YouTube API, as for ``pending``.
        """
        ...

    def set_exact(self, video_id: str, published_at: int) -> bool:
        """Store the exact published time of a video that has none yet.

        Args:
            video_id: The video.
            published_at: Its exact time, in seconds since the Unix epoch.

        Returns:
            Whether it was stored: False when the video has an exact time already,
            was removed from YouTube, or is gone from the catalogue.
        """
        ...

    def failed(
        self, video_id: str, code: ErrorCode, now: int, retry_after_s: Callable[[int], int]
    ) -> FetchState:
        """Note that the lookup of a video failed, and when it may be tried again.

        Args:
            video_id: The video.
            code: Why.
            now: The time now.
            retry_after_s: Says how long to wait after so many failures in a row.

        Returns:
            What the fetch now keeps for the video.
        """
        ...

    def left_out(self, video_ids: Sequence[str], now: int) -> None:
        """Note that the YouTube API gave no exact time for these videos (D-083).

        They are not asked of the API again before the next check of their channel.

        Args:
            video_ids: The videos.
            now: The time now.
        """
        ...

    def prioritize(self, video_ids: Sequence[str]) -> None:
        """Put videos at the front of the fetch: a decision waits for their date (R-MI-03).

        Args:
            video_ids: The videos.
        """
        ...

    def fetch_states(self, channel_id: str) -> Mapping[str, FetchState]:
        """Return what the fetch keeps for the videos of a channel, by video.

        Args:
            channel_id: The channel.
        """
        ...
