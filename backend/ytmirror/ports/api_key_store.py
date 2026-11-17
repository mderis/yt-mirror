"""The ApiKeyStore port: where the optional YouTube API key is kept.

Implements the storage of R-DT-12 and R-SE-03 (docs/DECISIONS.md D-085):
the key is kept on this Mac only, apart from the database and the settings,
and is read only when it is needed.

Tests: backend/tests/integration/test_api_key_store_contract.py
"""

from typing import Protocol


class ApiKeyStore(Protocol):
    """Keeps the one API key of the app."""

    def read(self) -> str | None:
        """Return the saved key, or None when no key is saved.

        Raises:
            AppError: ``API_KEY_UNREADABLE`` when a key is saved but cannot be read.
        """
        ...

    def write(self, key: str) -> None:
        """Save a key in place of the one saved before, all at once.

        Raises:
            AppError: ``API_KEY_UNREADABLE`` when it cannot be written.
        """
        ...

    def remove(self) -> None:
        """Delete the saved key. Nothing happens when none is saved."""
        ...
