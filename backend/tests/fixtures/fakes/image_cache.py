"""Pictures kept in memory. Fake of the ImageCache port."""

import re
from collections.abc import Iterable

from ytmirror.ports.image_cache import ImageKind

_SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


class InMemoryImageCache:
    """Remembers pictures in a dictionary."""

    def __init__(self) -> None:
        """Start empty."""
        self.pictures: dict[tuple[ImageKind, str], bytes] = {}

    def has(self, kind: ImageKind, item_id: str) -> bool:
        """Return whether the picture was stored."""
        return (kind, _checked(item_id)) in self.pictures

    def load(self, kind: ImageKind, item_id: str) -> bytes | None:
        """Return the stored picture, or None."""
        return self.pictures.get((kind, _checked(item_id)))

    def store(self, kind: ImageKind, item_id: str, content: bytes) -> None:
        """Remember the picture."""
        self.pictures[(kind, _checked(item_id))] = content

    def remove(self, kind: ImageKind, item_ids: Iterable[str]) -> None:
        """Forget the pictures."""
        for item_id in item_ids:
            self.pictures.pop((kind, _checked(item_id)), None)


def _checked(item_id: str) -> str:
    if not _SAFE_ID.fullmatch(item_id):
        raise ValueError(f"Not an ID of a video or a channel: {item_id!r}")
    return item_id
