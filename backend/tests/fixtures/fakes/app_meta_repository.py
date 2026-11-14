"""Facts kept in memory. Fake of the AppMetaRepository port."""


class InMemoryAppMetaRepository:
    """Remembers what was put under each key."""

    def __init__(self) -> None:
        """Start with nothing stored."""
        self.facts: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        """Return the stored value, or None."""
        return self.facts.get(key)

    def put(self, key: str, value: str) -> None:
        """Remember the value."""
        self.facts[key] = value
