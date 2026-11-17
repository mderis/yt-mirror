"""The fake of the YouTube API: the ExactDateSource port on the fake YouTube.

Part of the app for the same reason as ``fixture_youtube.py`` (docs/DECISIONS.md
D-062): an app started with ``YTM_FAKE_YOUTUBE`` must be able to take a key
and get exact dates without the network, for the end-to-end tests and the
screenshots. It answers from the videos of the fake YouTube.

The key decides how it fails: a key that starts with ``fixture-invalid`` is
refused as invalid, one that starts with ``fixture-quota`` has used up its
quota. Every other key works.

This module must not talk to the network.

Tests: backend/tests/integration/test_exact_date_source_contract.py
"""

from collections.abc import Callable, Mapping, Sequence

from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.ports.exact_date_source import MOST_IDS_PER_REQUEST

INVALID_KEY_PREFIX = "fixture-invalid"
QUOTA_KEY_PREFIX = "fixture-quota"


class FixtureYouTubeApi:
    """Answers exact dates from the fake YouTube, and fails by the key it is given.

    Attributes:
        requests: How many requests were made, as the quota counts them.
    """

    def __init__(self, api_date: Callable[[str], tuple[bool, int | None]]) -> None:
        """Answer from a fake YouTube.

        Args:
            api_date: Says of a video whether the API returns it, and its exact time:
                ``FixtureYouTube.api_date``. Passed in, as adapters never import each other.
        """
        self._api_date = api_date
        self.requests = 0

    def video_dates(self, key: str, video_ids: Sequence[str]) -> Mapping[str, int | None]:
        """Return the exact times of the fixture videos the fake API returns.

        Raises:
            AppError: ``API_KEY_INVALID`` or ``API_QUOTA_EXCEEDED`` by the key.
            ValueError: For more than 50 IDs.
        """
        if len(video_ids) > MOST_IDS_PER_REQUEST:
            raise ValueError(f"at most {MOST_IDS_PER_REQUEST} video IDs in one request")
        self._check(key)
        dates: dict[str, int | None] = {}
        for video_id in video_ids:
            returned, published = self._api_date(video_id)
            if returned:
                dates[video_id] = published
        return dates

    def test_key(self, key: str) -> None:
        """Fail as the key says, else answer.

        Raises:
            AppError: ``API_KEY_INVALID`` or ``API_QUOTA_EXCEEDED`` by the key.
        """
        self._check(key)

    def _check(self, key: str) -> None:
        self.requests += 1
        if not key or key.startswith(INVALID_KEY_PREFIX):
            raise AppError(ErrorCode.API_KEY_INVALID, {"reason": "keyInvalid"})
        if key.startswith(QUOTA_KEY_PREFIX):
            raise AppError(ErrorCode.API_QUOTA_EXCEEDED, {"reason": "quotaExceeded"})
