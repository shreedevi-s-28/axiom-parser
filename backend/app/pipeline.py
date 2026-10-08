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
            # Spreadsheets: XLSX / CSV / XLS
            if fname_lower.endswith((".xlsx", ".xls", ".csv")):
                from app.ingest.adapters import parse_spreadsheet
                return self._require_blocks(parse_spreadsheet(filename, content), filename), [], {}

            # Presentations: PPTX / PPT (PPT via conversion not implemented yet)
            if fname_lower.endswith((".pptx", ".ppt")):
                from app.ingest.adapters import parse_presentation
                return self._require_blocks(parse_presentation(filename, content), filename), [], {}

            # DOCX
            if fname_lower.endswith((".docx",)):
                from app.ingest.adapters import parse_docx
                return self._require_blocks(parse_docx(filename, content), filename), [], {}

            # Images: PNG / JPG / TIFF / HEIC (HEIC may need pillow-heif)
            if fname_lower.endswith((".png", ".jpg", ".jpeg", ".tiff", ".tif", ".heic", ".heif")):
                from app.ingest.adapters import parse_image
                return self._require_blocks(parse_image(filename, content), filename), [], {}

            # Plain text
            if fname_lower.endswith((".txt", ".text")):
                from app.ingest.adapters import parse_txt
                return self._require_blocks(parse_txt(filename, content), filename), [], {}

            # Markdown
            if fname_lower.endswith((".md", ".markdown")):
                from app.ingest.adapters import parse_markdown
                return self._require_blocks(parse_markdown(filename, content), filename), [], {}

            # HTML
            if fname_lower.endswith((".html", ".htm")):
                from app.ingest.adapters import parse_html
                return self._require_blocks(parse_html(filename, content), filename), [], {}

            # RTF
            if fname_lower.endswith(".rtf"):
                from app.ingest.adapters import parse_rtf
                return self._require_blocks(parse_rtf(filename, content), filename), [], {}

            # Email EML
            if fname_lower.endswith(".eml"):
                from app.ingest.adapters import parse_eml
                blocks, attachments = parse_eml(filename, content, depth=0)
                # recursively parse attachments (depth protected inside)
                for att_name, att_bytes in attachments:
                    try:
                        sub_blocks, _ = self._parse_attachment(att_name, att_bytes, depth=1)
                        for sb in sub_blocks:
                            sb.page = 1  # keep under parent
                            sb.metadata = {**(sb.metadata or {}), "from_attachment": att_name}
                            blocks.append(sb)
                    except Exception as sub_exc:
                        blocks.append(
                            SemanticBlock(
                                id=f"blk_att_err_{len(blocks)}",
                                page=1,
                                type=BlockType.ERROR,
                                text=f"Failed to parse attachment {att_name}: {sub_exc}",
                                bbox=BoundingBox(x0=0, y0=0, x1=100, y1=20),
                                confidence=0.0,
                                reading_order=len(blocks) + 1,
                                flagged_for_review=True,
                                review_reason=str(sub_exc),
                            )
                        )
                return self._require_blocks(blocks, filename), [], {}

            # MSG
            if fname_lower.endswith(".msg"):
                from app.ingest.adapters import parse_msg
                blocks, attachments = parse_msg(filename, content)
                for att_name, att_bytes in attachments:
                    try:
                        sub_blocks, _ = self._parse_attachment(att_name, att_bytes, depth=1)
                        for sb in sub_blocks:
                            sb.metadata = {**(sb.metadata or {}), "from_attachment": att_name}
                            blocks.append(sb)
                    except Exception as sub_exc:
                        blocks.append(
                            SemanticBlock(
                                id=f"blk_att_err_{len(blocks)}",
                                page=1,
                                type=BlockType.ERROR,
                                text=f"Failed to parse attachment {att_name}: {sub_exc}",
                                bbox=BoundingBox(x0=0, y0=0, x1=100, y1=20),
                                confidence=0.0,
                                reading_order=len(blocks) + 1,
                                flagged_for_review=True,
                                review_reason=str(sub_exc),
                            )
                        )
                return self._require_blocks(blocks, filename), [], {}

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
            detail=(
                f"The file '{filename}' has an unsupported type. "
                "Supported: PDF, DOCX, PPTX, XLSX, CSV, PNG/JPG/TIFF, HTML, MD, TXT, RTF, EML, MSG."
            ),
            diagnostics={"filename": filename},
        )

    def _parse_attachment(
        self, filename: str, content: bytes, depth: int = 1
    ) -> Tuple[List[SemanticBlock], List]:
        """Lightweight recursive attachment parser with depth guard."""
        if depth > 3:
            return [], []
        # Re-use stage1 logic by calling adapters directly for safety
        fname_lower = filename.lower()
        try:
            if fname_lower.endswith((".pdf",)):
                # save temp and extract
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp.write(content)
                    path = tmp.name
                try:
                    blocks, pages, issues = self._extract_pdf(filename, path)
                    return blocks, []
                finally:
                    os.unlink(path)
            if fname_lower.endswith((".docx",)):
                from app.ingest.adapters import parse_docx
                return parse_docx(filename, content), []
            if fname_lower.endswith((".xlsx", ".csv")):
                from app.ingest.adapters import parse_spreadsheet
                return parse_spreadsheet(filename, content), []
            if fname_lower.endswith((".png", ".jpg", ".jpeg", ".tiff")):
                from app.ingest.adapters import parse_image
                return parse_image(filename, content), []
            if fname_lower.endswith(".eml"):
                from app.ingest.adapters import parse_eml
                return parse_eml(filename, content, depth=depth)
            if fname_lower.endswith((".txt", ".md")):
                from app.ingest.adapters import parse_txt
                return parse_txt(filename, content), []
        except Exception:
            pass
        return [], []


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

        # If no text layer, attempt per-page OCR
        ocr_used = False
        if not spans:
            spans, ocr_used = self._ocr_pdf_pages(pdf_path, info["page_count"])
            if not spans:
                raise PipelineError(
                    status_code=422,
                    error_code="ERR_NO_TEXT_LAYER",
                    title="No Extractable Text",
                    detail=(
                        "The PDF has pages but no machine-readable text and OCR produced no results. "
                        "It may be blank, encrypted image, or OCR failed."
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
            conf = s.get("confidence")
            if conf is not None and conf > 1.0:
                conf = conf / 100.0
            blocks.append(
                SemanticBlock(
                    id=s.get("id") or f"blk_{uuid.uuid4().hex[:6]}",
                    page=s["page"],
                    type=b_type,
                    level=lvl,
                    text=s.get("text", ""),
                    bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1),
                    confidence=conf,
                    font_size=s.get("font_size"),
                    reading_order=len(blocks) + 1,
                    flagged_for_review=bool(conf is not None and conf < 0.6),
                    review_reason="Low OCR confidence" if (conf is not None and conf < 0.6) else None,
                    metadata={"ocr": ocr_used} if ocr_used else {},
                )
            )

        pages = []
        for p in info["pages"]:
            pages.append(
                PageInfo(
                    page=p["page"],
                    width=p["width"],
                    height=p["height"],
                    is_scanned=ocr_used,
                )
            )
        return blocks, pages, issues

    def _ocr_pdf_pages(self, pdf_path: str, page_count: int) -> Tuple[List[dict], bool]:
        """Render each page and OCR with Tesseract. Returns (spans, ocr_used)."""
        import pymupdf as fitz
        from PIL import Image
        import io as _io

        spans: List[dict] = []
        try:
            import pytesseract
            from pytesseract import Output
        except ImportError:
            return [], False

        with fitz.open(pdf_path) as doc:
            for page_num, page in enumerate(doc):
                # Render at 2x for better OCR
                mat = fitz.Matrix(2.0, 2.0)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img_bytes = pix.tobytes("png")
                img = Image.open(_io.BytesIO(img_bytes))
                w, h = img.size
                try:
                    data = pytesseract.image_to_data(img, output_type=Output.DICT)
                except Exception:
                    continue
                n = len(data["text"])
                # group by line
                lines: Dict[int, list] = {}
                for i in range(n):
                    conf = int(data["conf"][i]) if str(data["conf"][i]).lstrip("-").isdigit() else -1
                    txt = (data["text"][i] or "").strip()
                    if conf < 0 or not txt:
                        continue
                    key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
                    if key not in lines:
                        lines[key] = {"texts": [], "confs": [], "bbox": [data["left"][i], data["top"][i], data["left"][i] + data["width"][i], data["top"][i] + data["height"][i]]}
                    lines[key]["texts"].append(txt)
                    lines[key]["confs"].append(conf)
                    b = lines[key]["bbox"]
                    b[0] = min(b[0], data["left"][i])
                    b[1] = min(b[1], data["top"][i])
                    b[2] = max(b[2], data["left"][i] + data["width"][i])
                    b[3] = max(b[3], data["top"][i] + data["height"][i])

                scale_x = 1000.0 / w
                scale_y = 1000.0 / h
                for li, (key, info) in enumerate(sorted(lines.items())):
                    text = " ".join(info["texts"]).strip()
                    if not text:
                        continue
                    avg_conf = sum(info["confs"]) / len(info["confs"])
                    x0, y0, x1, y1 = info["bbox"]
                    spans.append({
                        "id": f"ocr_p{page_num+1}_l{li}",
                        "page": page_num + 1,
                        "text": text,
                        "bbox": [
                            round(x0 * scale_x, 1),
                            round(y0 * scale_y, 1),
                            round(x1 * scale_x, 1),
                            round(y1 * scale_y, 1),
                        ],
                        "font_size": 10.0,
                        "page_width": round(page.rect.width, 1),
                        "page_height": round(page.rect.height, 1),
                        "region": "body",
                        "column_index": 0,
                        "reading_order": 0,
                        "semantic_type": "paragraph",
                        "confidence": round(avg_conf, 1),
                    })
        return spans, True


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
        for b in blocks:
            if b.type in (BlockType.HEADER, BlockType.FOOTER):
                # Omit running headers/footers from core markdown reading stream
                continue
            elif b.type in (BlockType.HEADING, BlockType.TITLE):
                level = "#" * (b.level or 2)
                md_lines.append(f"{level} {b.text}\n")
            elif b.type == BlockType.LIST_ITEM:
                # avoid double bullets if text already starts with marker
                t = b.text.lstrip("-*+ ").lstrip()
                if re.match(r"^\d+\.\s", b.text):
                    md_lines.append(b.text)
                else:
                    md_lines.append(f"- {t}")

            elif b.type == BlockType.PARAGRAPH:
                md_lines.append(f"{b.text}\n")
            elif b.type == BlockType.TABLE and b.table_data:
                if b.table_data.headers:
                    md_lines.append("| " + " | ".join(b.table_data.headers) + " |")
                    md_lines.append("| " + " | ".join(["---"] * len(b.table_data.headers)) + " |")
                for r in b.table_data.rows:
                    md_lines.append("| " + " | ".join(str(c) for c in r) + " |")
                md_lines.append("\n")
            elif b.type == BlockType.FIGURE:
                caption = b.text or "Figure"
                if b.asset_path:
                    md_lines.append(f"![{caption}]({b.asset_path})\n")
                else:
                    md_lines.append(f"*[{caption}]*\n")
            elif b.type == BlockType.CAPTION:
                md_lines.append(f"*{b.text}*\n")
            elif b.type == BlockType.EQUATION:
                md_lines.append(f"$$\n{b.latex or b.text}\n$$\n")
            elif b.type == BlockType.FOOTNOTE:
                md_lines.append(f"[^fn]: {b.text}\n")
            elif b.type == BlockType.ERROR:
                md_lines.append(f"> **Extraction warning:** {b.text}\n")
            elif b.type == BlockType.IMAGE:
                md_lines.append(f"![image]({b.asset_path or ''})\n")
        return "\n".join(md_lines)

