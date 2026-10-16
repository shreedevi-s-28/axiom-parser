"""Deterministic chart extraction from a PDF's vector layer (Person 3).

When a chart is drawn as vector shapes with printed value labels, the exact
numbers are already in the file: read them instead of asking a vision model.
Returns None when values cannot be recovered exactly (e.g. a line chart with
no value labels), so the caller never receives guessed numbers."""
import re
from typing import Any, Dict, List, Optional, Tuple

import pymupdf as fitz

_NUMBER = re.compile(r'^\(?[-+]?[$€£]?\s*[\d,]*\.?\d+\s*[%MBKmbk]?\)?$')


def _parse_number(text: str) -> Optional[float]:
    t = text.strip()
    if not _NUMBER.match(t):
        return None
    neg = t.startswith('(') and t.endswith(')') or t.startswith('-')
    digits = re.sub(r'[^\d.]', '', t)
    if not digits or digits == '.':
        return None
    value = float(digits)
    return -value if neg else value


def _lines_in(page: "fitz.Page", region: "fitz.Rect") -> List[Tuple[str, "fitz.Rect"]]:
    """Whole text lines whose vertical extent lies in the region and whose
    centre is within the region's width (plus a margin for wide titles).
    Selecting whole lines avoids clip-truncated words like 'eve ue'."""
    wide = fitz.Rect(region.x0 - 120, region.y0, region.x1 + 120, region.y1)
    out = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            text = "".join(s.get("text", "") for s in line.get("spans", [])).strip()
            if not text:
                continue
            r = fitz.Rect(line["bbox"])
            centre_x = (r.x0 + r.x1) / 2
            if r.y0 >= region.y0 - 1 and r.y1 <= region.y1 + 1 and wide.x0 <= centre_x <= wide.x1:
                out.append((text, r))
    return out


def extract_vector_bar_chart(page: "fitz.Page", region: "fitz.Rect") -> Optional[Dict[str, Any]]:
    """Bar chart with a value label above each bar and a category label below."""
    bars = []
    for d in page.get_drawings():
        r = fitz.Rect(d["rect"])
        if d.get("fill") is not None and r.width >= 10 and r.height >= 1 and region.contains(r):
            bars.append(r)
    if len(bars) < 2:
        return None
    bars.sort(key=lambda r: r.x0)

    lines = _lines_in(page, region)
    top_of_shapes = min(b.y0 for b in bars)

    points = []
    for bar in bars:
        cx = (bar.x0 + bar.x1) / 2
        tol = bar.width

        above = [(t, r) for t, r in lines
                 if r.y1 <= bar.y0 + 2 and abs((r.x0 + r.x1) / 2 - cx) <= tol and _parse_number(t) is not None]
        below = [(t, r) for t, r in lines
                 if r.y0 >= bar.y1 - 1 and abs((r.x0 + r.x1) / 2 - cx) <= tol]
        if not above or not below:
            return None  # a bar without both labels is not exactly recoverable

        value_text, _ = min(above, key=lambda tr: bar.y0 - tr[1].y1)
        cat_text, _ = min(below, key=lambda tr: tr[1].y0 - bar.y1)
        points.append({"x": cat_text, "y": _parse_number(value_text)})

    title_candidates = [(t, r) for t, r in lines if r.y1 <= top_of_shapes and _parse_number(t) is None]
    title = min(title_candidates, key=lambda tr: tr[1].y0)[0] if title_candidates else None

    return {
        "chart_type": "bar",
        "title": title or "Untitled chart",
        "x_label": None,
        "y_label": None,
        "series": [{"name": title or "Series 1", "data": points}],
    }
