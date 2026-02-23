import json
import re

import docx2txt

from app.interfaces.parser_interface import IParser
from app.logging_config import get_logger

logger = get_logger(__name__)


class DocxParser(IParser):
    def parse(self, data: bytes) -> str:
        logger.info("DOCX parsing started: payload_bytes=%d", len(data) if data else 0)
        # docx2txt works with file path, so write to temp file
        import tempfile

        with tempfile.NamedTemporaryFile(delete=True, suffix=".docx") as tmp:
            tmp.write(data)
            tmp.flush()
            text = docx2txt.process(tmp.name)
        txt = text or ""

        # If the entire doc is JSON, return it prettified
        try:
            parsed = json.loads(txt)
            logger.info("DOCX parsing completed using full-document JSON detection")
            return json.dumps(parsed, indent=2)
        except Exception:
            pass

        # Split into non-empty lines
        lines = [l.rstrip() for l in txt.splitlines() if l.strip()]
        if not lines:
            logger.info("DOCX parsing completed: no non-empty lines extracted")
            return json.dumps({"content": txt}, indent=2)

        # Find a header line within the first 5 lines by detecting delimiters
        # or the line with the most alphabetic tokens. No hardcoded keywords.
        header_idx = None
        candidate_lines = lines[:5]
        for i, ln in enumerate(candidate_lines):
            # detect obvious delimiter patterns: tab, pipe, or multi-space
            if "\t" in ln or "|" in ln or re.search(r"\s{2,}", ln):
                # count resulting columns
                if "\t" in ln:
                    cols = [c.strip() for c in ln.split("\t") if c.strip()]
                elif "|" in ln:
                    cols = [c.strip() for c in re.split(r"\|", ln) if c.strip()]
                else:
                    cols = [c.strip() for c in re.split(r"\s{2,}", ln) if c.strip()]
                if len(cols) >= 3:
                    header_idx = i
                    break

        # fallback: pick the line among the first lines that has the most alphabetic tokens
        if header_idx is None:
            max_alpha = 0
            for i, ln in enumerate(candidate_lines):
                tokens = re.split(r"\s+", ln.strip())
                alpha_count = sum(
                    1
                    for t in tokens
                    if re.search(r"[A-Za-z]", t) and not re.fullmatch(r"\d+", t)
                )
                if alpha_count > max_alpha and alpha_count >= 2:
                    max_alpha = alpha_count
                    header_idx = i

        def map_line_to_headers(headers, line, delimiter_pattern=None):
            line = line.strip()
            if not line:
                return None
            # try splitting using delimiter pattern
            parts = None
            if delimiter_pattern:
                parts = [
                    p.strip() for p in re.split(delimiter_pattern, line) if p.strip()
                ]
            if not parts or len(parts) < 2:
                if "\t" in line:
                    parts = [p.strip() for p in line.split("\t") if p.strip()]
                else:
                    parts = [p.strip() for p in re.split(r"\s{2,}", line) if p.strip()]

            if len(parts) == len(headers):
                return dict(zip(headers, parts))

            # token-tail fallback: detect numeric tail values for date/days/end/progress
            tokens = line.split()
            numeric_headers = [
                h
                for h in headers
                if any(
                    k in h.lower()
                    for k in ("date", "day", "days", "progress", "start", "end")
                )
            ]
            nnum = len(numeric_headers)
            if nnum and len(tokens) >= nnum + 1:
                tail = tokens[-nnum:]
                left = tokens[:-nnum]
                nn = len(headers) - nnum
                # build left values heuristically
                if nn <= 0:
                    left_vals = []
                elif nn == 1:
                    left_vals = [" ".join(left)]
                else:
                    first = left[0] if left else ""
                    last = left[-1] if len(left) > 1 else ""
                    middle = left[1:-1]
                    mid_headers = nn - 2
                    mids = []
                    if mid_headers > 0:
                        size = len(middle) // mid_headers
                        rem = len(middle) % mid_headers
                        ix = 0
                        for i in range(mid_headers):
                            cnt = size + (1 if i < rem else 0)
                            mids.append(" ".join(middle[ix : ix + cnt]))
                            ix += cnt
                    left_vals = [first] + mids + [last]
                vals = left_vals + tail
                if len(vals) < len(headers):
                    vals += [""] * (len(headers) - len(vals))
                return dict(zip(headers, vals[: len(headers)]))

            # last resort: assign sequential tokens to headers, remainder to last header
            if len(tokens) >= len(headers):
                mapped = {}
                for i, h in enumerate(headers[:-1]):
                    mapped[h] = tokens[i]
                mapped[headers[-1]] = " ".join(tokens[len(headers) - 1 :])
                return mapped

            # cannot map
            return {headers[0]: line}

        records = []
        if header_idx is not None:
            hdr_line = lines[header_idx]
            # detect delimiter
            if "\t" in hdr_line:
                delim = "\t"
            elif "|" in hdr_line:
                delim = r"\|"
            elif re.search(r"\s{2,}", hdr_line):
                delim = r"\s{2,}"
            else:
                delim = None

            if delim:
                headers = [h.strip() for h in re.split(delim, hdr_line) if h.strip()]
            else:
                headers = [h.strip() for h in hdr_line.split() if h.strip()]

            # normalize common header names
            headers = [h if " " in h else h.replace("_", " ") for h in headers]

            for ln in lines[header_idx + 1 :]:
                mapped = map_line_to_headers(headers, ln, delimiter_pattern=delim)
                if mapped:
                    records.append(mapped)

        # fallback: parse key:value style lines into objects
        if not records:
            for line in lines:
                if ":" in line:
                    k, v = line.split(":", 1)
                    records.append({k.strip(): v.strip()})

        if records:
            logger.info("DOCX parsing completed: extracted_records=%d", len(records))
            return "\n".join(json.dumps(r, ensure_ascii=False) for r in records)

        logger.info("DOCX parsing completed with fallback: returning raw content payload")
        return json.dumps({"content": txt}, indent=2)
