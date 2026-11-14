"""The CatalogueRepository port: the stored channels and their videos.

Channels and videos are behind one port, so that everything a check changes
is stored in one transaction (docs/ARCHITECTURE.md section 7.1). A
repository stores and loads. It does not decide what a check changes: that
is ``core/catalogue.py``.

Tests: backend/tests/integration/db/test_catalogue_repository.py
"""

from collections.abc import Mapping
from typing import Protocol

from ytmirror.core.catalogue import CheckChanges
from ytmirror.core.channels import Channel, ChannelTotals, Video


class CatalogueRepository(Protocol):
    """Stores the channels the user added and the catalogue of each."""

    def channels(self) -> tuple[Channel, ...]:
        """Return every channel, in the order of the sidebar."""
        ...

    def channel(self, channel_id: str) -> Channel | None:
        """Return one channel, or None when it was not added.

        Args:
            channel_id: The channel ID.
        """
        ...

    def add_channel(self, channel: Channel) -> None:
        """Store a new channel.

        Args:
            channel: The channel. Its ID must not be stored yet.
        """
        ...

    def save_channel(self, channel: Channel) -> None:
        """Store the current values of a channel that was added before.

        A channel that is not stored (any more) is left alone: nothing is created.

        Args:
            channel: The channel as it is now.
        """
        ...

    def remove_channel(self, channel_id: str) -> None:
        """Remove a channel and its whole catalogue (R-CH-32).

        Args:
            channel_id: The channel ID. An unknown one changes nothing.
        """
        ...

    def videos(self, channel_id: str) -> tuple[Video, ...]:
        """Return the catalogue of a channel, in the order of the channel (R-CH-10).

        Args:
            channel_id: The channel ID.
        """
        ...

    def video_ids(self, channel_id: str) -> frozenset[str]:
        """Return the IDs of the videos of a channel.

        Args:
            channel_id: The channel ID.
        """
        ...

    def video(self, video_id: str) -> Video | None:
        """Return one video, or None when no catalogue has it.

        Args:
            video_id: The video ID.
        """
        ...

    def apply_check(self, channel: Channel, changes: CheckChanges) -> bool:
        """Store the result of a successful check in one transaction.

        The channel takes its new values and the videos are inserted and
        updated together, or nothing is stored. A video whose ID another
        channel already has is left out.

        Args:
            channel: The channel as it is after the check.
            changes: The videos to insert and to update.

        Returns:
            False when the channel is not stored (any more): then nothing was stored.
        """
        ...

    def totals(self, new_since: int) -> Mapping[str, ChannelTotals]:
        """Return the numbers of every channel that has videos, by channel ID.

        Args:
            new_since: A video first seen after this moment can still be new (R-CH-15).
        """
        ...
