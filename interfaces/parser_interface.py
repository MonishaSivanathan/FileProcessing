from typing import Protocol


class IParser(Protocol):
    def parse(self, data: bytes) -> str:
        """Extract text from raw document bytes."""
        ...
