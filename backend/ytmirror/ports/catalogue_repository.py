"""The CatalogueRepository port: the stored channels and their videos.

Channels and videos are behind one port, so that everything a check changes
is stored in one transaction (docs/ARCHITECTURE.md section 7.1). A
repository stores and loads. It does not decide what a check changes: that
is ``core/catalogue.py``.

Tests: backend/tests/integration/db/test_catalogue_repository.py
"""

from collections.abc import Mapping, Sequence
from typing import Protocol

from ytmirror.core.catalogue import CheckChanges
from ytmirror.core.channels import Channel, ChannelTotals, Video, VideoStatus
from ytmirror.core.status import StatusChange


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

    def videos_by_id(self, video_ids: Sequence[str]) -> Mapping[str, Video]:
        """Return the videos with these IDs, by ID. An unknown ID is left out.

        Args:
            video_ids: The video IDs.
        """
        ...

    def videos_with_status(self, status: VideoStatus) -> tuple[Video, ...]:
        """Return the videos of every channel that have a status, newest failure first.

        Args:
            status: The status.
        """
        ...

    def count_with_status(self, status: VideoStatus) -> int:
        """Return how many videos of every channel have a status.

        Args:
            status: The status.
        """
        ...

    def owners_of(self, video_ids: Sequence[str], *, other_than: str) -> Mapping[str, str]:
        """Return which of the videos belong to another channel, with that channel (R-CH-17).

        Args:
            video_ids: The video IDs to look up.
            other_than: The channel that asks. Its own videos are left out.

        Returns:
            The channel ID by video ID, for the videos another channel has.
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

    def count_check_retry(self, channel_id: str) -> int | None:
        """Count one more automatic retry of a failed check, and nothing else (R-CH-25).

        Only a channel whose last check failed and that is not paused is counted:
        a pause or a successful check that came meanwhile is never undone.

        Returns:
            The new count, or None when the channel is not to be retried any more.
        """
        ...

    def mark_rename(self, video_id: str, old: str, new: str) -> bool:
        """Store the marker of a rename before the file is moved (R-FN-06).

        Args:
            video_id: The video.
            old: The name its file has.
            new: The name it is going to have.

        Returns:
            Whether it was stored: False when the file has another name by now, or a
            rename of it is marked already.
        """
        ...

    def finish_rename(self, video_id: str, old: str, new: str) -> bool:
        """Store the new name of a file that was moved, and clear the marker.

        Returns:
            Whether it was stored: False when the name or the marker changed meanwhile.
        """
        ...

    def clear_rename(self, video_id: str) -> None:
        """Forget the marker of a rename that did not happen or was undone."""
        ...

    def change_status(self, change: StatusChange) -> bool:
        """Change the status of a video whose file went or came back, with its event (R-LG-03).

        Args:
            change: The change, from the status the video must still have.

        Returns:
            Whether it was stored: False when the video has another status by now.
        """
        ...

    def totals(self, new_since: int) -> Mapping[str, ChannelTotals]:
        """Return the numbers of every channel that has videos, by channel ID.

        Args:
            new_since: A video first seen after this moment can still be new (R-CH-15).
        """
        ...
