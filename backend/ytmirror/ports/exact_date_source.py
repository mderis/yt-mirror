"""The ExactDateSource port: the exact dates of videos from the YouTube API, with a key.

Implements the source of R-DT-05 that needs the optional key (docs/DECISIONS.md
D-082): ``videos.list`` by video ID, at most 50 per request. The key is
passed in with every call and never kept by the adapter.

Every method raises ``AppError``: ``API_KEY_INVALID`` when the key cannot be
used, ``API_QUOTA_EXCEEDED`` when its daily quota is used up, ``RATE_LIMITED``
when the API asks to slow down, and ``NETWORK_UNREACHABLE`` when it cannot be
reached. No error text ever contains the key.

Tests: backend/tests/integration/test_exact_date_source_contract.py
"""

from collections.abc import Mapping, Sequence
from typing import Protocol

MOST_IDS_PER_REQUEST = 50
"""The YouTube API answers at most 50 video IDs in one request, for one unit of quota."""


class ExactDateSource(Protocol):
    """Asks the YouTube API for the exact published times of videos."""

    def video_dates(self, key: str, video_ids: Sequence[str]) -> Mapping[str, int | None]:
        """Return the exact published times of up to 50 videos (R-DT-03, R-DT-05).

        Args:
            key: The API key.
            video_ids: At most ``MOST_IDS_PER_REQUEST`` video IDs.

        Returns:
            For every video the API returned: the release time of a premiere,
            else the time it became public, in seconds since the Unix epoch, or
            None when it has not been released yet. A video the API did not
            return is missing (D-083).

        Raises:
            AppError: With one of the codes of this port.
        """
        ...

    def test_key(self, key: str) -> None:
        """Ask the API once with a key, to see whether it works (R-DT-12).

        Args:
            key: The API key.

        Raises:
            AppError: With one of the codes of this port.
        """
        ...
