from abc import ABC, abstractmethod


class Provider(ABC):
    """A pluggable AI answer surface. Add a new one by subclassing this."""

    key: str  # short id stored on TrackedQuery.surfaces, e.g. "chatgpt"

    @abstractmethod
    async def query(self, text: str) -> str:
        """Run `text` against this surface and return the raw answer text."""
        raise NotImplementedError
