"""The AppMetaRepository port: facts the app keeps about itself.

Not settings: the user never sees or changes them. The first one is the
moment the first-run setup completed (R-IN-03).

Tests: backend/tests/integration/test_app_meta_repository_contract.py
"""

from typing import Protocol


class AppMetaRepository(Protocol):
    """Stores small facts under a key."""

    def get(self, key: str) -> str | None:
        """Return the value stored under a key, or None when nothing was stored.

        Args:
            key: The name of the fact.
        """
        ...

    def put(self, key: str, value: str) -> None:
        """Store a value under a key, replacing an earlier one.

        Args:
            key: The name of the fact.
            value: Its value as text.
        """
        ...
