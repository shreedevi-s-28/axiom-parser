# backend/app/ingest/adapters.py
"""Format-specific adapters that produce the canonical SemanticBlock list."""
from __future__ import annotations

import csv
import email
import email.policy
import html
import io
import os
import re
import sys
import tempfile
from email import message_from_bytes
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image
from openpyxl import load_workbook
from pptx import Presentation

# Ensure Python can resolve 'app' from the backend directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.schemas.document import (
    SemanticBlock,
    BlockType,
    BoundingBox,
    TableData,
    TableCell,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bbox(y0: float = 50.0, height: float = 40.0) -> BoundingBox:
    return BoundingBox(x0=50.0, y0=y0, x1=950.0, y1=y0 + height)


def _block(
    id_: str,
    page: int,
    type_: BlockType,
    text: str,
    order: int,
    *,
    level: Optional[int] = None,
    confidence: float = 0.95,
    table_data: Optional[TableData] = None,
    latex: Optional[str] = None,
    flagged: bool = False,
    reason: Optional[str] = None,
    asset_path: Optional[str] = None,
    metadata: Optional[dict] = None,
    y0: float = 50.0,
) -> SemanticBlock:
    return SemanticBlock(
        id=id_,
        page=page,
        type=type_,
        text=text,
        bbox=_bbox(y0=y0),
        confidence=confidence,
        reading_order=order,
        level=level,
        table_data=table_data,
        latex=latex,
        flagged_for_review=flagged,
        review_reason=reason,
        asset_path=asset_path,
        metadata=metadata or {},
    )


# ---------------------------------------------------------------------------
# Spreadsheet (XLSX / CSV / basic XLS via openpyxl fallback)
# ---------------------------------------------------------------------------

def parse_spreadsheet(filename: str, content: bytes) -> List[SemanticBlock]:
    """Converts XLSX / CSV sheets into structured SemanticBlocks."""
    blocks: List[SemanticBlock] = []

    if filename.lower().endswith(".csv"):
        text_stream = io.StringIO(content.decode("utf-8", errors="replace"))
        reader = list(csv.reader(text_stream))
        if not reader:
            return blocks

        headers = [str(c).strip() for c in reader[0]]
        rows = [[str(cell).strip() for cell in r] for r in reader[1:]]
        cells = [
            TableCell(row=ri, col=ci, text=cell)
            for ri, row in enumerate([headers] + rows)
            for ci, cell in enumerate(row)
        ]
        t_data = TableData(headers=headers, rows=rows, cells=cells, is_multi_page=False)
        blocks.append(
            _block(
                "blk_csv_01",
                1,
                BlockType.TABLE,
                f"CSV Table: {filename}",
                1,
                confidence=0.99,
                table_data=t_data,
            )
        )
        return blocks

    # XLSX (and openpyxl can open many .xls via compatibility)
    try:
        wb = load_workbook(filename=io.BytesIO(content), data_only=True)
    except Exception as exc:
        raise ValueError(f"Cannot open spreadsheet: {exc}") from exc

    page_idx = 1
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        all_rows = list(sheet.iter_rows(values_only=True))
        if not all_rows:
            continue

        non_empty_rows = [
            [str(cell).strip() if cell is not None else "" for cell in r]
            for r in all_rows
            if any(c is not None for c in r)
        ]
        if not non_empty_rows:
            continue

        headers = non_empty_rows[0]
        data_rows = non_empty_rows[1:]
        cells = [
            TableCell(row=ri, col=ci, text=cell)
            for ri, row in enumerate(non_empty_rows)
            for ci, cell in enumerate(row)
        ]

        blocks.append(
            _block(
                f"blk_sheet_title_{page_idx}",
                page_idx,
                BlockType.HEADING,
                f"Sheet: {sheet_name}",
                len(blocks) + 1,
                level=2,
                confidence=1.0,
                y0=40.0,
            )
        )
        t_data = TableData(
            headers=headers, rows=data_rows, cells=cells, is_multi_page=False
        )
        blocks.append(
            _block(
                f"blk_sheet_data_{page_idx}",
                page_idx,
                BlockType.TABLE,
                f"Table: {sheet_name}",
                len(blocks) + 1,
                confidence=0.99,
                table_data=t_data,
                y0=90.0,
            )
        )
        page_idx += 1

    return blocks


# ---------------------------------------------------------------------------
# Presentation (PPTX)
# ---------------------------------------------------------------------------

def parse_presentation(filename: str, content: bytes) -> List[SemanticBlock]:
    """Converts PPTX slides into structured SemanticBlocks."""
    prs = Presentation(io.BytesIO(content))
    blocks: List[SemanticBlock] = []

    for slide_idx, slide in enumerate(prs.slides, start=1):
        order = 1
        # speaker notes
        notes_text = ""
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes_text = slide.notes_slide.notes_text_frame.text.strip()

        for shape in slide.shapes:
            if shape.has_table:
                table = shape.table
                headers = []
                rows = []
                cells = []
                for ri, row in enumerate(table.rows):
                    row_vals = []
                    for ci, cell in enumerate(row.cells):
                        txt = cell.text.strip()
                        row_vals.append(txt)
                        cells.append(TableCell(row=ri, col=ci, text=txt))
                    if ri == 0:
                        headers = row_vals
                    else:
                        rows.append(row_vals)
                t_data = TableData(headers=headers, rows=rows, cells=cells)
                blocks.append(
                    _block(
                        f"blk_slide_{slide_idx}_tbl_{order}",
                        slide_idx,
                        BlockType.TABLE,
                        f"Table on slide {slide_idx}",
                        len(blocks) + 1,
                        confidence=0.97,
                        table_data=t_data,
                        y0=50.0 + order * 30,
                    )
                )
                order += 1
                continue

            if not shape.has_text_frame:
                continue
            text = shape.text_frame.text.strip()
            if not text:
                continue

            is_title = (shape == slide.shapes.title) or (order == 1)
            block_type = BlockType.HEADING if is_title else BlockType.PARAGRAPH
            blocks.append(
                _block(
                    f"blk_slide_{slide_idx}_{order}",
                    slide_idx,
                    block_type,
                    text,
                    len(blocks) + 1,
                    level=1 if is_title else None,
                    confidence=0.98,
                    y0=50.0 + order * 40,
                )
            )
            order += 1

        if notes_text:
            blocks.append(
                _block(
                    f"blk_slide_{slide_idx}_notes",
                    slide_idx,
                    BlockType.PARAGRAPH,
                    f"[Speaker notes] {notes_text}",
                    len(blocks) + 1,
                    confidence=0.9,
                    metadata={"is_speaker_notes": True},
                    y0=900.0,
                )
            )

    return blocks


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------

def parse_docx(filename: str, content: bytes) -> List[SemanticBlock]:
    """Parse modern Word documents."""
    from docx import Document
    from docx.oxml.ns import qn

    doc = Document(io.BytesIO(content))
    blocks: List[SemanticBlock] = []
    order = 1
    page = 1  # approximate; real page breaks need more work

    # paragraphs & headings
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style_name = (para.style.name or "").lower() if para.style else ""
        if "heading" in style_name or "title" in style_name:
            level = 1
            m = re.search(r"(\d+)", style_name)
            if m:
                level = int(m.group(1))
            btype = BlockType.TITLE if "title" in style_name else BlockType.HEADING
            blocks.append(
                _block(
                    f"blk_docx_h_{order}",
                    page,
                    btype,
                    text,
                    order,
                    level=level,
                    confidence=0.99,
                    y0=40.0 + order * 5,
                )
            )
        elif text.startswith(("- ", "* ", "• ")) or re.match(r"^\d+\.\s", text):
            blocks.append(
                _block(
                    f"blk_docx_li_{order}",
                    page,
                    BlockType.LIST_ITEM,
                    text,
                    order,
                    confidence=0.97,
                    y0=40.0 + order * 5,
                )
            )
        else:
            blocks.append(
                _block(
                    f"blk_docx_p_{order}",
                    page,
                    BlockType.PARAGRAPH,
                    text,
                    order,
                    confidence=0.98,
                    y0=40.0 + order * 5,
                )
            )
        order += 1

    # tables
    for ti, table in enumerate(doc.tables):
        headers = []
        rows = []
        cells = []
        for ri, row in enumerate(table.rows):
            row_vals = []
            for ci, cell in enumerate(row.cells):
                txt = cell.text.strip()
                row_vals.append(txt)
                # approximate rowspan/colspan from grid
                cells.append(TableCell(row=ri, col=ci, text=txt))
            if ri == 0:
                headers = row_vals
            else:
                rows.append(row_vals)
        t_data = TableData(headers=headers, rows=rows, cells=cells)
        blocks.append(
            _block(
                f"blk_docx_tbl_{ti}",
                page,
                BlockType.TABLE,
                f"Table {ti + 1}",
                order,
                confidence=0.97,
                table_data=t_data,
                y0=100.0 + ti * 50,
            )
        )
        order += 1

    # footnotes (basic)
    try:
        footnotes_part = doc.part.footnotes_part
        if footnotes_part is not None:
            for fi, fn in enumerate(footnotes_part.footnotes):
                text = "".join(p.text for p in fn.paragraphs).strip()
                if text:
                    blocks.append(
                        _block(
                            f"blk_docx_fn_{fi}",
                            page,
                            BlockType.FOOTNOTE,
                            text,
                            order,
                            confidence=0.9,
                            y0=950.0,
                        )
                    )
                    order += 1
    except Exception:
        pass

    return blocks


# ---------------------------------------------------------------------------
# Images (PNG/JPG/TIFF) – OCR via Tesseract when available
# ---------------------------------------------------------------------------

def parse_image(filename: str, content: bytes) -> List[SemanticBlock]:
    """OCR an image file and return text blocks + figure block."""
    img = Image.open(io.BytesIO(content))
    w, h = img.size
    blocks: List[SemanticBlock] = []

    # Always emit a figure block
    blocks.append(
        _block(
            "blk_img_figure",
            1,
            BlockType.FIGURE,
            f"Image: {filename} ({w}x{h} px)",
            1,
            confidence=0.99,
            metadata={"width_px": w, "height_px": h, "format": img.format},
            y0=20.0,
        )
    )

    # OCR
    try:
        import pytesseract
        from pytesseract import Output

        # convert to RGB if needed
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        data = pytesseract.image_to_data(img, output_type=Output.DICT)
        n = len(data["text"])
        order = 2
        current_line = []
        current_bbox = None
        confs = []

        def flush_line():
            nonlocal order, current_line, current_bbox, confs
            if not current_line:
                return
            text = " ".join(current_line).strip()
            if not text:
                current_line = []
                confs = []
                return
            avg_conf = sum(confs) / len(confs) if confs else 0.5
            # normalize bbox to 0-1000
            if current_bbox:
                x0 = max(0.0, min(1000.0, current_bbox[0] / w * 1000))
                y0 = max(0.0, min(1000.0, current_bbox[1] / h * 1000))
                x1 = max(0.0, min(1000.0, current_bbox[2] / w * 1000))
                y1 = max(0.0, min(1000.0, current_bbox[3] / h * 1000))
                bb = BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)
            else:
                bb = _bbox()
            blocks.append(
                SemanticBlock(
                    id=f"blk_ocr_{order}",
                    page=1,
                    type=BlockType.PARAGRAPH,
                    text=text,
                    bbox=bb,
                    confidence=round(avg_conf / 100.0, 3),
                    reading_order=order,
                    flagged_for_review=avg_conf < 60,
                    review_reason="Low OCR confidence" if avg_conf < 60 else None,
                )
            )
            order += 1
            current_line = []
            current_bbox = None
            confs = []

        for i in range(n):
            conf = int(data["conf"][i]) if data["conf"][i] != "-1" else -1
            txt = data["text"][i].strip()
            if conf == -1 or not txt:
                if data["level"][i] == 4:  # end of line
                    flush_line()
                continue
            x, y, bw, bh = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            if current_bbox is None:
                current_bbox = [x, y, x + bw, y + bh]
            else:
                current_bbox[0] = min(current_bbox[0], x)
                current_bbox[1] = min(current_bbox[1], y)
                current_bbox[2] = max(current_bbox[2], x + bw)
                current_bbox[3] = max(current_bbox[3], y + bh)
            current_line.append(txt)
            confs.append(conf)
            if data["level"][i] <= 4 and i + 1 < n and data["level"][i + 1] <= 4:
                # heuristic: flush on block/line boundaries
                pass
        flush_line()
    except Exception as exc:
        blocks.append(
            _block(
                "blk_ocr_fail",
                1,
                BlockType.ERROR,
                f"OCR unavailable or failed: {exc}",
                2,
                confidence=0.0,
                flagged=True,
                reason=str(exc),
            )
        )

    return blocks


# ---------------------------------------------------------------------------
# Plain text / Markdown / HTML / RTF
# ---------------------------------------------------------------------------

def parse_txt(filename: str, content: bytes) -> List[SemanticBlock]:
    text = content.decode("utf-8", errors="replace")
    blocks: List[SemanticBlock] = []
    order = 1
    for i, para in enumerate(re.split(r"\n\s*\n", text)):
        para = para.strip()
        if not para:
            continue
        # simple heading heuristic
        if len(para) < 80 and (para.isupper() or para.startswith("#")):
            btype = BlockType.HEADING
            level = para.count("#") or 1
            para = para.lstrip("# ").strip()
        else:
            btype = BlockType.PARAGRAPH
            level = None
        blocks.append(
            _block(f"blk_txt_{order}", 1, btype, para, order, level=level, confidence=1.0)
        )
        order += 1
    return blocks


def parse_markdown(filename: str, content: bytes) -> List[SemanticBlock]:
    text = content.decode("utf-8", errors="replace")
    blocks: List[SemanticBlock] = []
    order = 1
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        # headings
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            blocks.append(
                _block(
                    f"blk_md_h_{order}",
                    1,
                    BlockType.HEADING,
                    m.group(2).strip(),
                    order,
                    level=level,
                    confidence=1.0,
                )
            )
            order += 1
            i += 1
            continue
        # list items
        if re.match(r"^[-*+]\s+", stripped) or re.match(r"^\d+\.\s+", stripped):
            blocks.append(
                _block(
                    f"blk_md_li_{order}",
                    1,
                    BlockType.LIST_ITEM,
                    stripped,
                    order,
                    confidence=0.99,
                )
            )
            order += 1
            i += 1
            continue
        # tables (simple pipe tables)
        if "|" in stripped and i + 1 < len(lines) and re.match(r"^\s*\|?[-:| ]+\|?", lines[i + 1]):
            table_lines = []
            while i < len(lines) and "|" in lines[i]:
                table_lines.append(lines[i])
                i += 1
            # parse crude table
            rows_raw = []
            for tl in table_lines:
                if re.match(r"^\s*\|?[-:| ]+\|?", tl):
                    continue
                cells = [c.strip() for c in tl.strip().strip("|").split("|")]
                rows_raw.append(cells)
            if rows_raw:
                headers = rows_raw[0]
                data = rows_raw[1:]
                cells = [
                    TableCell(row=ri, col=ci, text=c)
                    for ri, row in enumerate(rows_raw)
                    for ci, c in enumerate(row)
                ]
                t_data = TableData(headers=headers, rows=data, cells=cells)
                blocks.append(
                    _block(
                        f"blk_md_tbl_{order}",
                        1,
                        BlockType.TABLE,
                        "Markdown table",
                        order,
                        confidence=0.95,
                        table_data=t_data,
                    )
                )
                order += 1
            continue
        # paragraph (collect until blank)
        para_lines = [stripped]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith("#") and "|" not in lines[i]:
            para_lines.append(lines[i].strip())
            i += 1
        text_para = " ".join(para_lines)
        blocks.append(
            _block(f"blk_md_p_{order}", 1, BlockType.PARAGRAPH, text_para, order, confidence=0.99)
        )
        order += 1
    return blocks


def parse_html(filename: str, content: bytes) -> List[SemanticBlock]:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        text = content.decode("utf-8", errors="replace")
        text = re.sub(r"<[^>]+>", " ", text)
        return parse_txt(filename, text.encode("utf-8"))

    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()

    blocks: List[SemanticBlock] = []
    order = 1

    # title
    if soup.title and soup.title.string:
        blocks.append(
            _block(
                "blk_html_title",
                1,
                BlockType.TITLE,
                soup.title.string.strip(),
                order,
                level=1,
                confidence=1.0,
            )
        )
        order += 1

    for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table"]):
        if el.name.startswith("h"):
            level = int(el.name[1])
            text = el.get_text(" ", strip=True)
            if text:
                blocks.append(
                    _block(
                        f"blk_html_h_{order}",
                        1,
                        BlockType.HEADING,
                        text,
                        order,
                        level=level,
                        confidence=0.98,
                    )
                )
                order += 1
        elif el.name == "p":
            text = el.get_text(" ", strip=True)
            if text:
                blocks.append(
                    _block(
                        f"blk_html_p_{order}",
                        1,
                        BlockType.PARAGRAPH,
                        text,
                        order,
                        confidence=0.97,
                    )
                )
                order += 1
        elif el.name == "li":
            text = el.get_text(" ", strip=True)
            if text:
                blocks.append(
                    _block(
                        f"blk_html_li_{order}",
                        1,
                        BlockType.LIST_ITEM,
                        text,
                        order,
                        confidence=0.97,
                    )
                )
                order += 1
        elif el.name == "table":
            headers = []
            rows = []
            cells = []
            for ri, tr in enumerate(el.find_all("tr")):
                row_cells = []
                for ci, cell in enumerate(tr.find_all(["th", "td"])):
                    txt = cell.get_text(" ", strip=True)
                    rowspan = int(cell.get("rowspan", 1))
                    colspan = int(cell.get("colspan", 1))
                    row_cells.append(txt)
                    cells.append(
                        TableCell(row=ri, col=ci, text=txt, rowspan=rowspan, colspan=colspan)
                    )
                if ri == 0 and tr.find("th"):
                    headers = row_cells
                else:
                    rows.append(row_cells)
            t_data = TableData(headers=headers, rows=rows, cells=cells, html=str(el)[:2000])
            blocks.append(
                _block(
                    f"blk_html_tbl_{order}",
                    1,
                    BlockType.TABLE,
                    "HTML table",
                    order,
                    confidence=0.96,
                    table_data=t_data,
                )
            )
            order += 1

    if not blocks:
        text = soup.get_text("\n", strip=True)
        return parse_txt(filename, text.encode("utf-8"))

    return blocks


def parse_rtf(filename: str, content: bytes) -> List[SemanticBlock]:
    try:
        from striprtf.striprtf import rtf_to_text
        text = rtf_to_text(content.decode("utf-8", errors="replace"))
    except Exception:
        try:
            from striprtf.striprtf import rtf_to_text
            text = rtf_to_text(content.decode("latin-1", errors="replace"))
        except Exception as exc:
            return [
                _block(
                    "blk_rtf_err",
                    1,
                    BlockType.ERROR,
                    f"RTF parse failed: {exc}",
                    1,
                    confidence=0.0,
                    flagged=True,
                    reason=str(exc),
                )
            ]
    return parse_txt(filename, text.encode("utf-8"))


# ---------------------------------------------------------------------------
# Email (EML / MSG)
# ---------------------------------------------------------------------------

MAX_EMAIL_DEPTH = 3


def parse_eml(
    filename: str, content: bytes, depth: int = 0
) -> Tuple[List[SemanticBlock], List[Tuple[str, bytes]]]:
    """Parse EML; returns blocks and list of (name, bytes) attachments for recursion."""
    if depth > MAX_EMAIL_DEPTH:
        return (
            [
                _block(
                    "blk_eml_depth",
                    1,
                    BlockType.ERROR,
                    "Email nesting depth exceeded; recursion stopped.",
                    1,
                    confidence=0.0,
                    flagged=True,
                    reason="MAX_EMAIL_DEPTH",
                )
            ],
            [],
        )

    msg = message_from_bytes(content, policy=email.policy.default)
    blocks: List[SemanticBlock] = []
    order = 1
    attachments: List[Tuple[str, bytes]] = []

    # headers
    subject = msg.get("Subject", "(no subject)")
    sender = msg.get("From", "")
    to = msg.get("To", "")
    date = msg.get("Date", "")

    blocks.append(
        _block(
            "blk_eml_subject",
            1,
            BlockType.HEADING,
            f"Subject: {subject}",
            order,
            level=1,
            confidence=1.0,
            metadata={"from": sender, "to": to, "date": date},
        )
    )
    order += 1
    if sender:
        blocks.append(
            _block("blk_eml_from", 1, BlockType.PARAGRAPH, f"From: {sender}", order, confidence=1.0)
        )
        order += 1

    # body
    body_text = ""
    body_html = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if "attachment" in disp.lower() or part.get_filename():
                fname = part.get_filename() or f"attachment_{len(attachments)}"
                payload = part.get_payload(decode=True) or b""
                attachments.append((fname, payload))
                blocks.append(
                    _block(
                        f"blk_eml_att_{len(attachments)}",
                        1,
                        BlockType.PARAGRAPH,
                        f"[Attachment] {fname} ({len(payload)} bytes)",
                        order,
                        confidence=1.0,
                        metadata={"attachment_name": fname, "size": len(payload)},
                    )
                )
                order += 1
            elif ctype == "text/plain" and not body_text:
                body_text = part.get_content()
            elif ctype == "text/html" and not body_html:
                body_html = part.get_content()
    else:
        ctype = msg.get_content_type()
        if ctype == "text/plain":
            body_text = msg.get_content()
        elif ctype == "text/html":
            body_html = msg.get_content()

    if body_html and not body_text:
        try:
            from bs4 import BeautifulSoup
            body_text = BeautifulSoup(body_html, "html.parser").get_text("\n", strip=True)
        except Exception:
            body_text = body_html

    if body_text:
        for para in re.split(r"\n\s*\n", body_text):
            para = para.strip()
            if para:
                blocks.append(
                    _block(
                        f"blk_eml_body_{order}",
                        1,
                        BlockType.PARAGRAPH,
                        para,
                        order,
                        confidence=0.95,
                    )
                )
                order += 1

    return blocks, attachments


def parse_msg(filename: str, content: bytes) -> Tuple[List[SemanticBlock], List[Tuple[str, bytes]]]:
    """Parse Outlook MSG files."""
    try:
        import extract_msg
        with tempfile.NamedTemporaryFile(suffix=".msg", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            msg = extract_msg.Message(tmp_path)
            blocks: List[SemanticBlock] = []
            order = 1
            subject = msg.subject or "(no subject)"
            blocks.append(
                _block(
                    "blk_msg_subject",
                    1,
                    BlockType.HEADING,
                    f"Subject: {subject}",
                    order,
                    level=1,
                    confidence=1.0,
                    metadata={"from": str(msg.sender), "date": str(msg.date)},
                )
            )
            order += 1
            body = msg.body or ""
            for para in re.split(r"\n\s*\n", body):
                para = para.strip()
                if para:
                    blocks.append(
                        _block(
                            f"blk_msg_body_{order}",
                            1,
                            BlockType.PARAGRAPH,
                            para,
                            order,
                            confidence=0.95,
                        )
                    )
                    order += 1
            attachments = []
            for att in msg.attachments:
                name = att.longFilename or att.shortFilename or f"att_{len(attachments)}"
                data = att.data or b""
                attachments.append((name, data))
                blocks.append(
                    _block(
                        f"blk_msg_att_{len(attachments)}",
                        1,
                        BlockType.PARAGRAPH,
                        f"[Attachment] {name} ({len(data)} bytes)",
                        order,
                        confidence=1.0,
                        metadata={"attachment_name": name},
                    )
                )
                order += 1
            msg.close()
            return blocks, attachments
        finally:
            os.unlink(tmp_path)
    except Exception as exc:
        return (
            [
                _block(
                    "blk_msg_err",
                    1,
                    BlockType.ERROR,
                    f"MSG parse failed: {exc}",
                    1,
                    confidence=0.0,
                    flagged=True,
                    reason=str(exc),
                )
            ],
            [],
        )


# ---------------------------------------------------------------------------
# Public image entry (kept for pipeline compatibility)
# ---------------------------------------------------------------------------

def parse_image_metadata(filename: str, content: bytes) -> List[SemanticBlock]:
    """Backward-compatible name used by pipeline; now performs OCR."""
    return parse_image(filename, content)
