"""The YouTubeGateway port: everything the app asks of YouTube.

From milestone M2: looking a channel up, listing its regular videos, the
optional video count of a channel preview, and fetching a picture. From
milestone M3: downloading one video into the temp folder of its job
(docs/ARCHITECTURE.md sections 7.2 and 7.3). From milestone M4: the exact
published time of one video (ARCHITECTURE section 7.4).

Every method raises ``AppError`` with a code of docs/LOGGING.md section 4
when YouTube cannot be asked: ``NETWORK_UNREACHABLE``, ``RATE_LIMITED``,
``BOT_CHECK``, ``YOUTUBE_CHANGED``, and ``CHANNEL_NOT_FOUND`` where a
channel is named.

Tests: backend/tests/integration/test_youtube_gateway_contract.py
"""

from collections.abc import Callable
from typing import Protocol

from ytmirror.core.channels import ChannelFacts, ChannelListing, ChannelReference
from ytmirror.core.jobs import DownloadProgress, DownloadRequest, DownloadResult


class YouTubeGateway(Protocol):
    """Asks YouTube about channels and their videos."""

    def lookup_channel(self, reference: ChannelReference) -> ChannelFacts:
        """Return what YouTube says about a channel, without reading its videos (R-CH-03).

        Args:
            reference: The channel as the user named it.

        Raises:
            AppError: ``CHANNEL_NOT_FOUND`` when YouTube has no such channel, or
                one of the codes for a request that could not be made.
        """
        ...

    def list_channel(self, channel_id: str) -> ChannelListing:
        """Start a listing of the regular videos of a channel, newest first (R-CH-12).

        Only regular videos are listed: no Shorts and no live streams (R-CH-07).
        The listing is read video by video, and YouTube is asked for more only
        when more is read. A channel without regular videos has an empty
        listing. A listing that YouTube cuts off raises an error instead of
        ending early.

        Args:
            channel_id: The channel ID.

        Raises:
            AppError: Here or while the videos are read.
        """
        ...

    def preview_video_count(self, channel_id: str) -> int:
        """Return how many regular videos YouTube says a channel has (R-CH-03).

        The number is a preview only and rests on a convention of YouTube
        that is documented nowhere (docs/DECISIONS.md D-061). Callers must
        treat every failure as "no count".

        Args:
            channel_id: The channel ID.

        Raises:
            AppError: When YouTube gives no usable number.
        """
        ...

    def fetch_image(self, url: str) -> bytes:
        """Return the bytes of a thumbnail or an avatar (R-CH-16).

        Args:
            url: The address a lookup or a listing gave.

        Raises:
            AppError: When the picture cannot be fetched.
        """
        ...

    def exact_date(self, video_id: str) -> int | None:
        """Return the exact published time of one video, with the lightest lookup (R-DT-05).

        The release time of a premiere or a scheduled video comes before the
        time of its upload (R-DT-03).

        Args:
            video_id: The video ID.

        Returns:
            Seconds since the Unix epoch, UTC, or None for a video that has not
            been released yet.

        Raises:
            AppError: With the code of what went wrong, for example ``VIDEO_PRIVATE``.
        """
        ...

    def download(
        self,
        request: DownloadRequest,
        on_progress: Callable[[DownloadProgress], None],
        is_cancelled: Callable[[], bool],
        *,
        start_writing: Callable[[], None] = lambda: None,
    ) -> DownloadResult:
        """Download one video as an MKV with its metadata, into the temp folder of its job.

        Args:
            request: What to download, and where to.
            on_progress: Told how far the download is (R-QU-04).
            is_cancelled: Asked while the download runs. When it says yes, the
                download ends at its next step.
            start_writing: Called once, right before the first file of the job is
                written, after what only reads from YouTube. It raises
                ``DownloadCancelledError`` when the job was cancelled meanwhile:
                then nothing is written (R-QU-02).

        Raises:
            AppError: With the code of what went wrong, for example ``MEMBERS_ONLY``.
            DownloadCancelledError: When it was cancelled.
            SubtitlesFailedError: When only the subtitles failed (R-MD-04).
        """
        ...
