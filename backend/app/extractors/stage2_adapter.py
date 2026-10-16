"""Stage 2 enrichment for the ingestion pipeline (Person 3).

enrich_blocks() takes the SemanticBlocks produced by Stage 1 (Person 2's
spatial engine) plus the original PDF bytes and returns a new list where:
  * ruled tables become TABLE blocks with table_data,
  * vector charts become FIGURE blocks with chart_data and a Markdown table,
  * equation-only lines become EQUATION blocks with bare LaTeX in `latex`.

It never invents data: a chart whose values cannot be recovered exactly (and no
vision model is available) becomes a low-confidence FIGURE flagged for review.
The canned golden chart in chart2data is NOT used here.
"""
import logging
import re
from typing import List, Optional, Tuple

import pymupdf as fitz

from app.schemas.document import (
    BlockType,
    BoundingBox,
    ChartData,
    SemanticBlock,
    TableData,
)
from app.extractors.chart2data import chart_to_markdown_table, extract_chart, validate_chart_data
from app.extractors.math_parser import has_unconverted_symbols, is_equation_line, to_bare_latex
from app.extractors.region_detector import detect_chart_regions, detect_tables, render_crop_png
from app.extractors.vector_chart import extract_vector_bar_chart

logger = logging.getLogger(__name__)

# Block ids produced by spatial_engine.extract_raw_spans. Anything else (the
# demo fixture, spreadsheet/pptx/image adapters) is passed through untouched.
_SPATIAL_ID = re.compile(r"^p\d+_b\d+_l\d+$")

_CHART_TYPE_MAP = {"bar": "bar_chart", "line": "line_chart", "pie": "pie_chart"}


def _norm_bbox(rect: "fitz.Rect", page_rect: "fitz.Rect") -> BoundingBox:
    """PDF points -> the schema's 0..1000 scale, clamped to the valid range."""
    sx, sy = 1000.0 / page_rect.width, 1000.0 / page_rect.height

    def clamp(v: float) -> float:
        return round(min(max(v, 0.0), 1000.0), 1)

    return BoundingBox(
        x0=clamp((rect.x0 - page_rect.x0) * sx), y0=clamp((rect.y0 - page_rect.y0) * sy),
        x1=clamp((rect.x1 - page_rect.x0) * sx), y1=clamp((rect.y1 - page_rect.y0) * sy),
    )


def _center_inside(block: SemanticBlock, box: BoundingBox) -> bool:
    cx = (block.bbox.x0 + block.bbox.x1) / 2
    cy = (block.bbox.y0 + block.bbox.y1) / 2
    return box.x0 <= cx <= box.x1 and box.y0 <= cy <= box.y1


def _make_table_block(page_no: int, n: int, rows: List[List[str]], box: BoundingBox) -> SemanticBlock:
    headers, body = (rows[0], rows[1:]) if len(rows) > 1 else ([], rows)
    return SemanticBlock(
        id=f"p{page_no}_tbl{n}", page=page_no, type=BlockType.TABLE,
        text=f"Table ({len(rows)} rows)", bbox=box, confidence=0.9, reading_order=0,
        table_data=TableData(headers=headers, rows=body),
    )


def _make_chart_block(page_no: int, n: int, page: "fitz.Page", region: "fitz.Rect",
                      box: BoundingBox) -> SemanticBlock:
    # 1) Exact values straight from the PDF's vector layer.
    data = extract_vector_bar_chart(page, region)
    confidence, reason = 0.95, None

    # 2) Vision model, only when a key is configured and the vector pass failed.
    if data is None:
        image = render_crop_png(page, region)
        vision, source = extract_chart(image)
        if source == "vision":
            data, confidence = vision, 0.75
            reason = "Chart values read by a vision model; verify against the source."

    # 3) Honest failure: no numbers rather than invented ones.
    if data is None or not validate_chart_data(data):
        return SemanticBlock(
            id=f"p{page_no}_fig{n}", page=page_no, type=BlockType.FIGURE,
            text="*(Chart detected - values could not be extracted exactly)*",
            bbox=box, confidence=0.45, reading_order=0, flagged_for_review=True,
            review_reason="Chart values not recoverable from the vector layer and no "
                          "vision model result available. Manual transcription needed.",
        )

    data = {**data, "chart_type": _CHART_TYPE_MAP.get(data.get("chart_type"), data.get("chart_type"))}
    return SemanticBlock(
        id=f"p{page_no}_fig{n}", page=page_no, type=BlockType.FIGURE,
        text=chart_to_markdown_table(data), bbox=box, confidence=confidence, reading_order=0,
        chart_data=ChartData(**data),
        flagged_for_review=reason is not None, review_reason=reason,
    )


def _to_equation(block: SemanticBlock) -> SemanticBlock:
    latex = to_bare_latex(block.text)
    if has_unconverted_symbols(latex):
        return block.model_copy(update={
            "type": BlockType.EQUATION, "latex": latex, "confidence": 0.6,
            "flagged_for_review": True,
            "review_reason": "Equation contains symbols that could not be converted to LaTeX.",
        })
    return block.model_copy(update={"type": BlockType.EQUATION, "latex": latex, "confidence": 0.92})


def _insert_position(page_blocks: List[SemanticBlock], new: SemanticBlock) -> int:
    for i, b in enumerate(page_blocks):
        if b.type in (BlockType.HEADER, BlockType.FOOTER):
            continue
        if b.bbox.y0 > new.bbox.y0:
            return i
    for i, b in enumerate(page_blocks):
        if b.type == BlockType.FOOTER:
            return i
    return len(page_blocks)


def _enrich_page(page: "fitz.Page", page_no: int, page_blocks: List[SemanticBlock]) -> List[SemanticBlock]:
    tables = detect_tables(page)
    charts = detect_chart_regions(page, [r for r, _ in tables])
    new_blocks: List[SemanticBlock] = []
    claimed: List[BoundingBox] = []

    for n, (rect, rows) in enumerate(tables, start=1):
        box = _norm_bbox(rect, page.rect)
        new_blocks.append(_make_table_block(page_no, n, rows, box))
        claimed.append(box)
    for n, region in enumerate(charts, start=1):
        box = _norm_bbox(region, page.rect)
        new_blocks.append(_make_chart_block(page_no, n, page, region, box))
        claimed.append(box)

    remaining = [b for b in page_blocks if not any(_center_inside(b, c) for c in claimed)]
    remaining = [_to_equation(b) if b.type == BlockType.PARAGRAPH and is_equation_line(b.text) else b
                 for b in remaining]

    for nb in sorted(new_blocks, key=lambda b: (b.bbox.y0, b.bbox.x0)):
        remaining.insert(_insert_position(remaining, nb), nb)

    for order, b in enumerate(remaining, start=1):   # per-page numbering, as Person 2 does
        b.reading_order = order
    return remaining


def enrich_blocks(blocks: List[SemanticBlock], pdf_bytes: bytes) -> List[SemanticBlock]:
    """Main entry point. Safe by construction: any failure on a page keeps that
    page's original blocks, so Stage 2 can never make the result worse."""
    if not blocks or not all(_SPATIAL_ID.match(b.id) for b in blocks):
        return blocks

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        by_page = {}
        for b in blocks:
            by_page.setdefault(b.page, []).append(b)

        result: List[SemanticBlock] = []
        for page_no in sorted(by_page):
            originals = by_page[page_no]
            try:
                result.extend(_enrich_page(doc[page_no - 1], page_no, [b.model_copy() for b in originals]))
            except Exception as exc:  # noqa: BLE001 - deliberate per-page isolation
                logger.warning("Stage 2 skipped page %s: %s", page_no, exc)
                result.extend(originals)
        return result
