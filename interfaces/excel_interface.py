from typing import BinaryIO, Protocol


class IExcelRepository(Protocol):
    def append(self, record: dict) -> int:
        """Append a record and return row number."""
        ...

    def get_stream(self) -> BinaryIO:
        """Return a file-like stream of the workbook."""
        ...
