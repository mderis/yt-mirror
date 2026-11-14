"""The ImageCache port: the pictures of the catalogue, kept on this Mac.

Thumbnails of videos and avatars of channels are cached so that the list
works offline and for videos that were removed from YouTube (R-CH-16). A
picture is known by its kind and the ID of its video or channel, never by a
path that came from outside.

Tests: backend/tests/integration/test_image_cache_contract.py
"""

from collections.abc import Iterable
from enum import StrEnum
from typing import Protocol


class ImageKind(StrEnum):
    """The two kinds of cached pictures."""

    THUMBNAIL = "thumbnail"
    AVATAR = "avatar"


class ImageCache(Protocol):
    """Keeps pictures by kind and ID."""

    def has(self, kind: ImageKind, item_id: str) -> bool:
        """Return whether a picture is cached.

        Args:
            kind: A thumbnail or an avatar.
            item_id: The video ID or the channel ID.
        """
        ...

    def load(self, kind: ImageKind, item_id: str) -> bytes | None:
        """Return the bytes of a cached picture, or None when it is not cached.

        Args:
            kind: A thumbnail or an avatar.
            item_id: The video ID or the channel ID.
        """
        ...

    def store(self, kind: ImageKind, item_id: str, content: bytes) -> None:
        """Keep a picture, replacing an earlier one. It is complete or not there at all.

        Args:
            kind: A thumbnail or an avatar.
            item_id: The video ID or the channel ID.
            content: The bytes of the picture.
        """
        ...

    def remove(self, kind: ImageKind, item_ids: Iterable[str]) -> None:
        """Drop cached pictures. A picture that is not cached is skipped.

        Args:
            kind: A thumbnail or an avatar.
            item_ids: The video IDs or the channel IDs.
        """
        ...
