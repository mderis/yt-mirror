"""The YouTubeGateway port: everything the app asks of YouTube.

From milestone M2: looking a channel up, listing its regular videos, the
optional video count of a channel preview, and fetching a picture. Metadata
of one video and downloads arrive in milestone M3.

Every method raises ``AppError`` with a code of docs/LOGGING.md section 4
when YouTube cannot be asked: ``NETWORK_UNREACHABLE``, ``RATE_LIMITED``,
``BOT_CHECK``, ``YOUTUBE_CHANGED``, and ``CHANNEL_NOT_FOUND`` where a
channel is named.

Tests: backend/tests/integration/test_youtube_gateway_contract.py
"""

from typing import Protocol

from ytmirror.core.channels import ChannelFacts, ChannelListing, ChannelReference


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
