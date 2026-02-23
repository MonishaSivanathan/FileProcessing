import json
import uuid
from dataclasses import dataclass

from app.implementations.azure_blob_storage import AzureBlobStorage
from app.implementations.docx_parser import DocxParser
from app.implementations.excel_repository import ExcelRepository
from app.implementations.pdf_parser import PdfParser
from app.interfaces.excel_interface import IExcelRepository
from app.interfaces.storage_interface import IStorage
from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class UploadResult:
    id: str
    blob_url: str
    excel_row: int


class DocumentService:
    def __init__(self, storage: IStorage = None, excel_repo: IExcelRepository = None):
        self.storage = storage or AzureBlobStorage()
        self.excel_repo = excel_repo or ExcelRepository()
        self.parsers = {
            "doc": DocxParser(),
            "docx": DocxParser(),
            "pdf": PdfParser(),
        }
        logger.info("DocumentService initialized: available_parsers=%s", list(self.parsers))

    def _consolidate_fragments(self, ndjson_str: str) -> str:
        """Consolidate fragmented JSON lines into complete records."""
        if not ndjson_str or not ndjson_str.strip():
            return ndjson_str

        lines = [l.strip() for l in ndjson_str.splitlines() if l.strip()]
        if len(lines) < 2:
            return ndjson_str

        fragments = []
        for ln in lines:
            try:
                obj = json.loads(ln)
                fragments.append(obj)
            except Exception:
                pass

        if not fragments:
            return ndjson_str

        # Detect grouping: if fragments are single-valued, group by 6
        if len(fragments) >= 6 and all(
            len(f) == 1 or (len(f) == 2 and "Progress" in f) for f in fragments
        ):
            consolidated = []
            i = 0
            while i < len(fragments):
                if i + 5 < len(fragments):
                    group = fragments[i : i + 6]
                    record = self._merge_six_fragments(group)
                    if record:
                        consolidated.append(record)
                        i += 6
                        continue
                if len(fragments[i]) > 1:
                    consolidated.append(fragments[i])
                i += 1

            if consolidated:
                return "\n".join(
                    json.dumps(r, ensure_ascii=False) for r in consolidated
                )

        return ndjson_str

    def _merge_six_fragments(self, frags: list) -> dict:
        """Merge 6 JSON fragments into one complete record."""
        if len(frags) != 6:
            return None
        try:
            record = {}
            f0_vals = list(frags[0].values())
            if f0_vals:
                record["Project Name"] = f0_vals[0]
            f1 = frags[1]
            f1_vals = [v for k, v in f1.items() if k != "Progress"]
            assigned = f1.get("Progress")
            if f1_vals:
                record["Task Name"] = f1_vals[0]
            if assigned:
                record["Assigned to"] = assigned
            f2_vals = list(frags[2].values())
            f3_vals = list(frags[3].values())
            f4_vals = list(frags[4].values())
            f5_vals = list(frags[5].values())
            if f2_vals:
                record["Start Date"] = f2_vals[0]
            if f3_vals:
                record["Days Required"] = f3_vals[0]
            if f4_vals:
                record["End Date"] = f4_vals[0]
            if f5_vals:
                record["Progress"] = f5_vals[0]
            return record if len(record) >= 5 else None
        except Exception:
            return None

    def process_upload(self, file_stream, filename) -> UploadResult:
        # validation assumed done upstream
        ext = filename.rsplit(".", 1)[-1].lower()
        logger.info(
            "Upload processing started: filename='%s', extension='%s'",
            filename,
            ext,
        )
        content = file_stream.read()
        blob_name = f"{uuid.uuid4()}.{ext}"
        url = self.storage.save(blob_name, content)
        parser = self.parsers.get(ext)
        if not parser:
            logger.error(
                "Upload processing failed: unsupported file extension='%s'",
                ext,
            )
            raise ValueError(f"Unsupported file extension: {ext}")
        json_data = parser.parse(content)
        # consolidate fragmented lines if needed
        json_data = self._consolidate_fragments(json_data)
        row = self.excel_repo.append(
            {
                "id": blob_name,
                "filename": filename,
                "file_type": ext,
                "json_data": json_data,
            }
        )
        logger.info(
            "Upload processing completed: blob_id='%s', excel_row=%s",
            blob_name,
            row,
        )
        return UploadResult(id=blob_name, blob_url=url, excel_row=row)

    def get_excel_stream(self):
        logger.info("Excel stream retrieval started")
        return self.excel_repo.get_stream()
