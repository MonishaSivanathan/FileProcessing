import json
import re
from io import BytesIO

from PyPDF2 import PdfReader

from app.interfaces.parser_interface import IParser


class PdfParser(IParser):
    def parse(self, data: bytes) -> str:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt('')
        parsed_objects = []

        for page_num, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""

            # Try to parse table data from the page
            table_data = self._parse_table_from_text(page_text)

            if table_data:
                rows = table_data.get('rows', [])
                for row in rows:
                    parsed_objects.append(row)
                # continue to next page (don't return early)
                continue

            # fallback: split page into lines and try to parse each line
            for line in page_text.splitlines():
                line = line.strip()
                if not line:
                    continue
                # try full-line JSON
                try:
                    obj = json.loads(line)
                    parsed_objects.append(obj)
                    continue
                except Exception:
                    pass

                # try to parse key:value pairs separated by comma or semicolon
                # e.g. "k1: v1, k2: v2"
                parts = re.split(r'[;,]\s*', line)
                if len(parts) > 1 and all(':' in p for p in parts if p.strip()):
                    obj = {}
                    for p in parts:
                        if ':' in p:
                            k, v = p.split(':', 1)
                            obj[k.strip()] = v.strip()
                    if obj:
                        parsed_objects.append(obj)
                        continue

                # otherwise store as a raw line with page context
                parsed_objects.append({"page": page_num, "line": line})

        # If we collected any parsed objects, return NDJSON (one JSON object per line)
        if parsed_objects:
            return "\n".join(json.dumps(o, ensure_ascii=False) for o in parsed_objects)

        # nothing parsed: return minimal metadata
        pdf_json = {
            "total_pages": len(reader.pages),
            "pages": []
        }
        return json.dumps(pdf_json, indent=2)
    

    def _parse_table_from_text(self, text: str):
        # split into non-empty lines
        lines = [l for l in text.splitlines() if l.strip()]
        if len(lines) < 2:
            return None

        # first try a simple delimiter (tab or 2+ spaces)
        header_line = lines[0]
        # pick appropriate delimiter pattern
        if '\t' in header_line:
            delim = '\t'
        else:
            delim = r'\s{2,}'
        tentative = [h.strip() for h in re.split(delim, header_line) if h.strip()]
        if len(tentative) >= 2:
            # see if first data row matches same count
            first_vals = [v.strip() for v in re.split(delim, lines[1])]
            if len(first_vals) == len(tentative):
                headers = tentative
                rows = []
                for line in lines[1:]:
                    vals = [v.strip() for v in re.split(delim, line)]
                    if len(vals) < len(headers):
                        vals += [''] * (len(headers) - len(vals))
                    rows.append(dict(zip(headers, vals)))
                return {"headers": headers, "rows": rows, "row_count": len(rows)}

        # fallback: use token grouping based on data token count
        header_tokens = header_line.split()
        data_tokens = lines[1].split()
        # group numeric headers from right based on known suffixes
        numeric_count = len([t for t in data_tokens if re.fullmatch(r"\d+(\.\d+)?", t)])
        suffixes = {'Date', 'Required'}
        tokens = header_tokens[:]
        numeric_headers = []
        for _ in range(numeric_count):
            if not tokens:
                break
            tok = tokens.pop()
            if tok in suffixes and tokens:
                prefix = tokens.pop()
                numeric_headers.insert(0, f"{prefix} {tok}")
            else:
                numeric_headers.insert(0, tok)
        # remaining tokens are text headers, group them in pairs
        text_headers = []
        i = 0
        while i < len(tokens) - 1:
            text_headers.append(tokens[i] + " " + tokens[i + 1])
            i += 2
        if i < len(tokens):
            text_headers.append(tokens[i])
        headers = text_headers + numeric_headers
        ncols = len(headers)
        # construct rows by splitting tokens according to header count
        rows = []
        # numeric_count already computed earlier
        text_headers = headers[:len(headers) - numeric_count]
        num_text = len(text_headers)
        for line in lines[1:]:
            vals = line.split()
            # separate numeric part at end
            numeric_vals = vals[-numeric_count:] if numeric_count else []
            left_vals = vals[:-numeric_count] if numeric_count else vals[:]
            text_vals = []
            if num_text == 0:
                text_vals = []
            elif num_text == 1:
                text_vals = [" ".join(left_vals)]
            elif num_text == 2:
                text_vals = [left_vals[0] if left_vals else "", " ".join(left_vals[1:])]
            else:
                # first header gets first token
                first = left_vals[0] if left_vals else ""
                last = left_vals[-1] if len(left_vals) > 1 else ""
                middle = left_vals[1:-1]
                middle_headers = num_text - 2
                # distribute middle tokens evenly across middle headers
                if middle_headers > 0:
                    size = len(middle) // middle_headers
                    rem = len(middle) % middle_headers
                    ix = 0
                    mids = []
                    for i in range(middle_headers):
                        cnt = size + (1 if i < rem else 0)
                        mids.append(" ".join(middle[ix:ix+cnt]))
                        ix += cnt
                else:
                    mids = []
                text_vals = [first] + mids + [last]
            combined = text_vals + numeric_vals
            # pad/trim to length
            if len(combined) < ncols:
                combined += [''] * (ncols - len(combined))
            rows.append(dict(zip(headers, combined[:ncols])))
        if rows:
            return {"headers": headers, "rows": rows, "row_count": len(rows)}
        return None