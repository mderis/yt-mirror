"""The ImageCache port as files in the cache folder of the app.

Layout: ``data/cache/thumbnails/<video id>`` and ``data/cache/avatars/<channel id>``.
The files have no ending: what kind of picture it is, is read from its first
bytes when it is served. A picture is written next to its place and moved
there, so a file in place is always complete (R-QA-06).

An ID that could leave the cache folder is refused: it is a programming error.

Tests: backend/tests/integration/test_image_cache_contract.py
"""

import os
import re
import tempfile
from collections.abc import Iterable
from pathlib import Path

from ytmirror.ports.image_cache import ImageKind

_FOLDERS = {ImageKind.THUMBNAIL: "thumbnails", ImageKind.AVATAR: "avatars"}
_SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


class FileImageCache:
    """Keeps every picture as one file."""

    def __init__(self, cache_dir: Path) -> None:
        """Create the cache. No folder is created before the first picture is stored.

        Args:
            cache_dir: The cache folder of the app.
        """
        self._cache_dir = cache_dir

    def has(self, kind: ImageKind, item_id: str) -> bool:
        """Return whether a picture is cached.

        Args:
            kind: A thumbnail or an avatar.
            item_id: The video ID or the channel ID.
        """
        return self._place(kind, item_id).is_file()

    def load(self, kind: ImageKind, item_id: str) -> bytes | None:
        """Return the bytes of a cached picture, or None when it is not cached.

        Args:
            kind: A thumbnail or an avatar.
            item_id: The video ID or the channel ID.
        """
        try:
            return self._place(kind, item_id).read_bytes()
        except FileNotFoundError:
            return None

    def store(self, kind: ImageKind, item_id: str, content: bytes) -> None:
        """Keep a picture, replacing an earlier one.

        Args:
            kind: A thumbnail or an avatar.
            item_id: The video ID or the channel ID.
            content: The bytes of the picture.
        """
        place = self._place(kind, item_id)
        place.parent.mkdir(parents=True, exist_ok=True)
        handle, name = tempfile.mkstemp(dir=place.parent, prefix=".arriving-")
        with os.fdopen(handle, "wb") as file:
            file.write(content)
        Path(name).replace(place)

    def remove(self, kind: ImageKind, item_ids: Iterable[str]) -> None:
        """Drop cached pictures. A picture that is not cached is skipped.

        Args:
            kind: A thumbnail or an avatar.
            item_ids: The video IDs or the channel IDs.
        """
        for item_id in item_ids:
            self._place(kind, item_id).unlink(missing_ok=True)

    def _place(self, kind: ImageKind, item_id: str) -> Path:
        if not _SAFE_ID.fullmatch(item_id):
            raise ValueError(f"Not an ID of a video or a channel: {item_id!r}")
        return self._cache_dir / _FOLDERS[kind] / item_id
