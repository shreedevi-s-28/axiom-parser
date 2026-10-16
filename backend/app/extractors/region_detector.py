"""Finds table and chart regions on a PDF page (Person 3). Geometry only:
no schema types and no LLM calls live here."""
from typing import List, Tuple

import pymupdf as fitz

# A drawing cluster must have at least this many shapes to count as a chart.
MIN_CHART_SHAPES = 3
# Shapes closer than this (points) are merged into one cluster.
CLUSTER_GAP = 60.0
# Chart titles/labels sit just outside the drawn shapes.
PAD_TOP, PAD_BOTTOM, PAD_SIDE = 45.0, 25.0, 12.0


def detect_tables(page: "fitz.Page") -> List[Tuple["fitz.Rect", List[List[str]]]]:
    """Ruled tables detected by PyMuPDF as (bounding rect, rows of cell text)."""
    found = []
    try:
        for t in page.find_tables().tables:
            rows = [[(c or "").strip() for c in row] for row in t.extract()]
            if rows:
                found.append((fitz.Rect(t.bbox), rows))
    except Exception:
        return []
    return found


def _inside(inner: "fitz.Rect", outer: "fitz.Rect", tol: float = 3.0) -> bool:
    grown = fitz.Rect(outer.x0 - tol, outer.y0 - tol, outer.x1 + tol, outer.y1 + tol)
    return grown.contains(inner)


def _cluster(rects: List["fitz.Rect"]) -> List[List["fitz.Rect"]]:
    clusters: List[List["fitz.Rect"]] = []
    for r in rects:
        grown = fitz.Rect(r.x0 - CLUSTER_GAP, r.y0 - CLUSTER_GAP, r.x1 + CLUSTER_GAP, r.y1 + CLUSTER_GAP)
        hits = [c for c in clusters if any(grown.intersects(m) for m in c)]
        merged = [r]
        for c in hits:
            merged.extend(c)
            clusters.remove(c)
        clusters.append(merged)
    return clusters


# Axis labels (Q1, 2024, ...) can sit well below the drawn shapes.
LABEL_REACH = 100.0
LABEL_MAX_CHARS = 8


def _absorb_axis_labels(page: "fitz.Page", region: "fitz.Rect") -> "fitz.Rect":
    """Grow the region's bottom edge to cover short axis labels directly beneath it."""
    bottom = region.y1
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            text = "".join(s.get("text", "") for s in line.get("spans", [])).strip()
            r = fitz.Rect(line["bbox"])
            centre_x = (r.x0 + r.x1) / 2
            if (text and len(text) <= LABEL_MAX_CHARS
                    and region.x0 <= centre_x <= region.x1
                    and region.y1 - 1 <= r.y0 <= region.y1 + LABEL_REACH):
                bottom = max(bottom, r.y1 + 2)
    return fitz.Rect(region.x0, region.y0, region.x1, min(bottom, page.rect.y1))


def detect_chart_regions(page: "fitz.Page", table_rects: List["fitz.Rect"]) -> List["fitz.Rect"]:
    """Padded bounding rects of vector-drawing clusters that are not tables."""
    shapes = []
    for d in page.get_drawings():
        r = fitz.Rect(d["rect"])
        if r.is_empty and r.width == 0 and r.height == 0:
            continue
        if any(_inside(r, t) for t in table_rects):
            continue
        shapes.append(r)

    regions = []
    for cluster in _cluster(shapes):
        if len(cluster) < MIN_CHART_SHAPES:
            continue
        union = fitz.Rect(cluster[0])
        for r in cluster[1:]:
            union |= r
        padded = fitz.Rect(
            union.x0 - PAD_SIDE, union.y0 - PAD_TOP,
            union.x1 + PAD_SIDE, union.y1 + PAD_BOTTOM,
        )
        regions.append(_absorb_axis_labels(page, padded & page.rect))
    return sorted(regions, key=lambda r: (r.y0, r.x0))


def render_crop_png(page: "fitz.Page", region: "fitz.Rect", zoom: float = 2.0) -> bytes:
    """Rasterize a region for the vision model."""
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=region)
    return pix.tobytes("png")
