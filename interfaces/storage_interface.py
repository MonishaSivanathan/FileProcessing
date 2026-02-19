from typing import Protocol


class IStorage(Protocol):
    def save(self, name: str, data: bytes) -> str:
        """Save bytes under given name and return a URL."""
        ...

    def get(self, name: str) -> bytes:
        """Retrieve stored bytes."""
        ...
