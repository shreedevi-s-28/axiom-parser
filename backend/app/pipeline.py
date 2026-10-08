# backend/app/pipeline.py
import asyncio
import os
import re
import time
import uuid
from typing import Dict, List, Optional, Tuple

from app.schemas.document import (
    ParseResult,
    DocumentMetrics,
    PageInfo,
    SemanticBlock,
    BlockType,
    BoundingBox,
)
from app.core.cache import cache_engine
from app.core.errors import PipelineError
from app.core.store import document_store

# Opt-in demo cache. Off by default so every upload is analysed for real.
DEMO_CACHE_ENABLED = os.getenv("AXIOMPARSE_DEMO_CACHE", "").lower() in ("1", "true", "yes")

# Cost model: on-premise benchmark (~$0.65 per 1,000 pages). This is an ESTIMATE
# derived from the real page count, not a measured bill.
COST_PER_PAGE_USD = 0.00065

_GEOMETRY_ID_PATTERN = re.compile(r"^\[(.+?)\]\s*(.*)$")


class UniversalIngestionPipeline:
    """
    Standardized 3-Stage Pipeline Orchestrator:
    Stage 1: Detect & Route (sniff format, inspect vector vs scanned, segment)
    Stage 2: Extract & Assemble (sort reading order, stitch tables, transcribe charts/math)
    Stage 3: Flag & Deliver (compute confidence scores, flag ambiguous blocks, output Markdown/JSON)
    """

    def __init__(self):
        self.cost_per_page_usd = COST_PER_PAGE_USD

    async def execute(self, filename: str, content: bytes, mime_type: str) -> ParseResult:
        # Extraction is CPU-bound and synchronous; run it off the event loop so the
        # server stays responsive and the watchdog timeout can actually fire.
        return await asyncio.to_thread(self._execute_sync, filename, content, mime_type)

    def _execute_sync(self, filename: str, content: bytes, mime_type: str) -> ParseResult:
        start_time = time.perf_counter()
        doc_id = f"doc_{uuid.uuid4().hex[:8]}"
        is_pdf = filename.lower().endswith(".pdf")

        stored_path: Optional[str] = None
        if is_pdf:
            stored_path = document_store.save(doc_id, content)

        try:
            if DEMO_CACHE_ENABLED:
                cached_payload = cache_engine.get(content, filename)
                if cached_payload:
                    cached_payload["document_id"] = doc_id
                    cached_payload["filename"] = filename
                    cached_payload["metrics"]["processing_time_ms"] = round(
                        (time.perf_counter() - start_time) * 1000.0, 2
                    )
                    return ParseResult.model_validate(cached_payload)

            # STAGE 1: DETECT & ROUTE
            raw_blocks, pages, geometry_issues = self._stage1_detect_and_route(filename, content, mime_type, stored_path)

            # STAGE 2: EXTRACT & ASSEMBLE
            assembled_blocks = self._stage2_extract_and_assemble(raw_blocks)

            # STAGE 3: FLAG & DELIVER
            final_blocks, avg_confidence = self._stage3_flag_and_deliver(assembled_blocks, geometry_issues)
        except Exception:
            if stored_path:
                document_store.delete(doc_id)
            raise

        # Only a successful analysis may evict older stored documents.
        if stored_path:
            document_store.prune()

        markdown_content = self._generate_markdown(final_blocks)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        if pages:
            page_count = len(pages)
        else:
            page_count = max([b.page for b in final_blocks], default=1)
        total_cost = page_count * self.cost_per_page_usd

        metrics = DocumentMetrics(
            processing_time_ms=round(elapsed_ms, 2),
            estimated_cost_usd=round(total_cost, 6),
            confidence_average=round(avg_confidence, 3) if avg_confidence is not None else None,
            total_pages=page_count,
            total_blocks=len(final_blocks),
        )

        result = ParseResult(
            document_id=doc_id,
            filename=filename,
            file_type=mime_type,
            page_count=page_count,
            pages=pages,
            metrics=metrics,
            blocks=final_blocks,
            markdown=markdown_content,
        )

        if DEMO_CACHE_ENABLED:
            cache_engine.set(content, filename, result.model_dump())
        return result

    def _stage1_detect_and_route(
        self, filename: str, content: bytes, mime: str, stored_path: Optional[str]
    ) -> Tuple[List[SemanticBlock], List[PageInfo], Dict[str, List[str]]]:
        """Identifies file properties and routes to specialized format adapters."""
        fname_lower = filename.lower()

        try:
            # Spreadsheets: XLSX / CSV
            if fname_lower.endswith((".xlsx", ".xls", ".csv")):
                from app.ingest.adapters import parse_spreadsheet
                return self._require_blocks(parse_spreadsheet(filename, content), filename), [], {}

            # Presentations: PPTX
            if fname_lower.endswith((".pptx", ".ppt")):
                from app.ingest.adapters import parse_presentation
                return self._require_blocks(parse_presentation(filename, content), filename), [], {}

            # Raw Images: PNG / JPG / TIFF
            if fname_lower.endswith((".png", ".jpg", ".jpeg", ".tiff")):
                from app.ingest.adapters import parse_image_metadata
                return self._require_blocks(parse_image_metadata(filename, content), filename), [], {}
        except PipelineError:
            raise
        except Exception as exc:
            raise PipelineError(
                status_code=422,
                error_code="ERR_EXTRACTION_FAILED",
                title="Extraction Failed",
                detail=f"The file '{filename}' could not be read: {exc}",
                diagnostics={"filename": filename, "exception": type(exc).__name__},
            )

        if fname_lower.endswith(".pdf") and stored_path:
            return self._extract_pdf(filename, stored_path)

        raise PipelineError(
            status_code=415,
            error_code="ERR_UNSUPPORTED_FORMAT",
            title="Unsupported File Format",
            detail=f"The file '{filename}' has an unsupported type. Upload a PDF, XLSX, PPTX, or image file.",
            diagnostics={"filename": filename},
        )

    @staticmethod
    def _require_blocks(blocks: List[SemanticBlock], filename: str) -> List[SemanticBlock]:
        if not blocks:
            raise PipelineError(
                status_code=422,
                error_code="ERR_EMPTY_DOCUMENT",
                title="No Content Extracted",
                detail=f"No extractable content was found in '{filename}'.",
                diagnostics={"filename": filename},
            )
        return blocks

    def _extract_pdf(
        self, filename: str, pdf_path: str
    ) -> Tuple[List[SemanticBlock], List[PageInfo], Dict[str, List[str]]]:
        """Runs the spatial engine over a real PDF. Never substitutes placeholder content."""
        from app.extractors.spatial_engine import (
            get_document_info,
            extract_raw_spans,
            validate_geometry,
            detect_headers_footers,
            detect_columns,
            determine_reading_order,
            classify_semantic_types,
        )

        try:
            info = get_document_info(pdf_path)
        except Exception as exc:
            raise PipelineError(
                status_code=422,
                error_code="ERR_CORRUPT_PDF",
                title="PDF Could Not Be Opened",
                detail="The file starts like a PDF but its structure could not be read. It may be corrupt or truncated.",
                diagnostics={"filename": filename, "exception": type(exc).__name__},
            )

        if info["needs_password"]:
            raise PipelineError(
                status_code=422,
                error_code="ERR_ENCRYPTED_PDF",
                title="Encrypted PDF",
                detail="This PDF is password-protected. Remove the password and upload it again.",
                diagnostics={"filename": filename},
            )

        if info["page_count"] == 0:
            raise PipelineError(
                status_code=422,
                error_code="ERR_EMPTY_DOCUMENT",
                title="PDF Has No Pages",
                detail="The PDF opened successfully but contains no pages.",
                diagnostics={"filename": filename},
            )

        try:
            spans = extract_raw_spans(pdf_path)
        except Exception as exc:
            raise PipelineError(
                status_code=500,
                error_code="ERR_EXTRACTION_FAILED",
                title="Extraction Failed",
                detail=f"Text extraction failed: {exc}",
                diagnostics={"filename": filename, "exception": type(exc).__name__},
            )

        if not spans:
            raise PipelineError(
                status_code=422,
                error_code="ERR_NO_TEXT_LAYER",
                title="No Extractable Text",
                detail=(
                    "The PDF has pages but no machine-readable text. It is probably a scanned or "
                    "image-only document, which requires OCR (not available in this engine)."
                ),
                diagnostics={"filename": filename, "page_count": info["page_count"]},
            )

        _, warnings = validate_geometry(spans)
        issues: Dict[str, List[str]] = {}
        for warning in warnings:
            match = _GEOMETRY_ID_PATTERN.match(warning)
            if match:
                issues.setdefault(match.group(1), []).append(match.group(2))
        spans = detect_headers_footers(spans)
        spans = detect_columns(spans)
        spans = determine_reading_order(spans)
        spans = classify_semantic_types(spans)

        blocks: List[SemanticBlock] = []
        for s in spans:
            sem = s.get("semantic_type", "paragraph").lower()
            lvl: Optional[int] = None
            if sem == "title":
                b_type, lvl = BlockType.HEADING, 1
            elif sem == "heading":
                b_type, lvl = BlockType.HEADING, 2
            elif sem == "subheading":
                b_type, lvl = BlockType.HEADING, 3
            elif sem == "list_item":
                b_type = BlockType.LIST_ITEM
            elif sem == "header":
                b_type = BlockType.HEADER
            elif sem == "footer":
                b_type = BlockType.FOOTER
            else:
                b_type = BlockType.PARAGRAPH

            x0, y0, x1, y1 = [min(1000.0, max(0.0, float(v))) for v in s["bbox"]]
            blocks.append(
                SemanticBlock(
                    id=s.get("id") or f"blk_{uuid.uuid4().hex[:6]}",
                    page=s["page"],
                    type=b_type,
                    level=lvl,
                    text=s.get("text", ""),
                    bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1),
                    # The spatial engine reads the PDF text layer; it computes no confidence.
                    confidence=None,
                    font_size=s.get("font_size"),
                    # Engine order is per page; renumber to one continuous document order.
                    reading_order=len(blocks) + 1,
                )
            )

        pages = [PageInfo(**p) for p in info["pages"]]
        return blocks, pages, issues

    def _stage2_extract_and_assemble(self, blocks: List[SemanticBlock]) -> List[SemanticBlock]:
        """Integration hook for Person 2 (Spatial/Layout) & Person 3 (Chart/Math)."""
        return blocks

    def _stage3_flag_and_deliver(
        self, blocks: List[SemanticBlock], geometry_issues: Optional[Dict[str, List[str]]] = None
    ) -> Tuple[List[SemanticBlock], Optional[float]]:
        """Flags blocks using real signals: low confidence (when computed), geometry problems, unmapped glyphs."""
        geometry_issues = geometry_issues or {}
        confidences: List[float] = []
        for b in blocks:
            reasons: List[str] = []

            if b.confidence is not None:
                confidences.append(b.confidence)
                if b.confidence < 0.70:
                    reasons.append(f"Confidence score ({b.confidence:.2f}) below threshold")

            if b.id in geometry_issues:
                reasons.append("Geometry check: " + "; ".join(geometry_issues[b.id]))

            if "\ufffd" in b.text:
                reasons.append("Text contains unmapped glyphs (U+FFFD); the font encoding may be broken")

            if reasons:
                b.flagged_for_review = True
                if not b.review_reason:
                    b.review_reason = ". ".join(reasons)

        avg_confidence = sum(confidences) / len(confidences) if confidences else None
        return blocks, avg_confidence

    def _generate_markdown(self, blocks: List[SemanticBlock]) -> str:
        """Assembles blocks into clean GitHub Flavored Markdown (GFM)."""
        md_lines = []

        def cell(value: str) -> str:
            return str(value).replace("|", "\\|").replace("\n", " ")

        for b in blocks:
            if b.type == BlockType.HEADER or b.type == BlockType.FOOTER:
                # Omit running headers/footers from core markdown reading stream
                continue
            elif b.type == BlockType.HEADING:
                level = "#" * (b.level or 2)
                md_lines.append(f"{level} {b.text}\n")
            elif b.type == BlockType.LIST_ITEM:
                md_lines.append(f"- {b.text}")
            elif b.type == BlockType.PARAGRAPH:
                md_lines.append(f"{b.text}\n")
            elif b.type == BlockType.TABLE and b.table_data:
                if b.table_data.headers:
                    md_lines.append("| " + " | ".join(cell(h) for h in b.table_data.headers) + " |")
                    md_lines.append("| " + " | ".join(["---"] * len(b.table_data.headers)) + " |")
                for r in b.table_data.rows:
                    md_lines.append("| " + " | ".join(cell(c) for c in r) + " |")
                md_lines.append("\n")
            elif b.type == BlockType.FIGURE:
                md_lines.append(f"{b.text}\n")
            elif b.type == BlockType.EQUATION:
                md_lines.append(f"$$\n{b.latex or b.text}\n$$\n")
        return "\n".join(md_lines)
