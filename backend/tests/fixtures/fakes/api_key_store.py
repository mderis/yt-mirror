"""An API key store in memory. Fake of the ApiKeyStore port.

Attributes of the fake let a test make a saved key unreadable and count the reads.
"""

from ytmirror.core.errors import AppError, ErrorCode


class InMemoryApiKeyStore:
    """Keeps the key in memory.

    Attributes:
        key: The saved key, or None.
        unreadable: Whether a saved key cannot be read.
        reads: How many times the key was read.
    """

    def __init__(self, key: str | None = None) -> None:
        """Start with a key, or with none."""
        self.key = key
        self.unreadable = False
        self.reads = 0

    def read(self) -> str | None:
        """Return the key, or fail as a file that cannot be read."""
        self.reads += 1
        if self.unreadable:
            raise AppError(ErrorCode.API_KEY_UNREADABLE, {"error": "PermissionError"})
        return self.key

    def is_saved(self) -> bool:
        """Return whether a key is saved, readable or not."""
        return self.key is not None

    def write(self, key: str) -> None:
        """Save a key; a saved key can be read again."""
        self.key = key
        self.unreadable = False

    def remove(self) -> None:
        """Forget the key."""
        self.key = None
        self.unreadable = False
