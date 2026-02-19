import json
from openpyxl import load_workbook
from flask import Blueprint, jsonify, request

from app.services.document_service import DocumentService
from app.utils.file_validator import validate_file

document_bp = Blueprint("documents", __name__, url_prefix="/api/documents")

service = DocumentService()


@document_bp.route("", methods=["POST"])
def upload_document():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file provided"}), 400

    try:
        validate_file(file)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    result = service.process_upload(file.stream, file.filename)
    return jsonify(result.__dict__), 201


@document_bp.route("/excel", methods=["GET"])
def get_excel():
    try:
        stream = service.get_excel_stream()
        # parse workbook in-memory and return structured JSON for all entries

        stream.seek(0)
        wb = load_workbook(stream)
        ws = wb.active

        rows = list(ws.iter_rows(values_only=True))
        if not rows or len(rows) < 2:
            return jsonify({"data": []}), 200

        headers = [h for h in rows[0]]
        # common column names that may contain transformed JSON
        json_cols = [
            name for name in ("json_data", "transformed_data") if name in headers
        ]
        json_col_idx = headers.index(json_cols[0]) if json_cols else None

        # locate id/filename/file_type indices if present
        id_idx = headers.index("id") if "id" in headers else None
        filename_idx = headers.index("filename") if "filename" in headers else None
        filetype_idx = headers.index("file_type") if "file_type" in headers else None

        entries = []
        for r in rows[1:]:
            entry = {
                "id": r[id_idx] if id_idx is not None else None,
                "filename": r[filename_idx] if filename_idx is not None else None,
                "file_type": r[filetype_idx] if filetype_idx is not None else None,
                "transformed_data": [],
            }

            if json_col_idx is not None:
                cell = r[json_col_idx]
                if not cell:
                    entry["transformed_data"] = []
                elif isinstance(cell, str):
                    lines = [l for l in cell.splitlines() if l.strip()]
                    parsed = []
                    for ln in lines:
                        try:
                            val = json.loads(ln)
                        except Exception:
                            # if the cell is a JSON array
                            try:
                                val = json.loads(cell)
                                if isinstance(val, list):
                                    parsed.extend(val)
                                    break
                            except Exception:
                                val = ln
                        if isinstance(val, list):
                            parsed.extend(val)
                        else:
                            parsed.append(val)
                    entry["transformed_data"] = parsed
                else:
                    # non-string (unlikely) - include raw
                    entry["transformed_data"] = [cell]
            else:
                # reconstruct object from all columns except id/filename/file_type
                obj = {}
                for k, val in zip(headers, r):
                    if k in ("id", "filename", "file_type"):
                        continue
                    obj[k] = val
                entry["transformed_data"] = [obj]

            entries.append(entry)

        return jsonify({"data": entries}), 200
    except FileNotFoundError:
        return jsonify({"error": "Excel file not found"}), 404
