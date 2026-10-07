# backend/app/ingest/adapters.py
import io
import csv
import os
import sys

# Ensure Python can resolve 'app' from the backend directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from typing import List
from openpyxl import load_workbook
from pptx import Presentation
from PIL import Image

from app.schemas.document import (
    SemanticBlock,
    BlockType,
    BoundingBox,
    TableData,
)

def parse_spreadsheet(filename: str, content: bytes) -> List[SemanticBlock]:
    """Converts XLSX / CSV sheets into structured SemanticBlocks."""
    blocks: List[SemanticBlock] = []
    
    if filename.lower().endswith(".csv"):
        text_stream = io.StringIO(content.decode("utf-8", errors="ignore"))
        reader = list(csv.reader(text_stream))
        if not reader:
            return blocks
        
        headers = [str(c).strip() for c in reader[0]]
        rows = [[str(cell).strip() for cell in r] for r in reader[1:]]
        
        t_data = TableData(headers=headers, rows=rows, is_multi_page=False)
        blocks.append(SemanticBlock(
            id="blk_sheet_01",
            page=1,
            type=BlockType.TABLE,
            text=f"Spreadsheet Table: {filename}",
            bbox=BoundingBox(x0=50.0, y0=50.0, x1=950.0, y1=900.0),
            confidence=0.99,
            reading_order=1,
            table_data=t_data
        ))
        return blocks

    wb = load_workbook(filename=io.BytesIO(content), data_only=True)
    page_idx = 1

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        all_rows = list(sheet.iter_rows(values_only=True))
        if not all_rows:
            continue

        non_empty_rows = [
            [str(cell).strip() if cell is not None else "" for cell in r]
            for r in all_rows if any(c is not None for c in r)
        ]

        if not non_empty_rows:
            continue

        headers = non_empty_rows[0]
        data_rows = non_empty_rows[1:]

        blocks.append(SemanticBlock(
            id=f"blk_sheet_title_{page_idx}",
            page=page_idx,
            type=BlockType.HEADING,
            level=2,
            text=f"Sheet: {sheet_name}",
            bbox=BoundingBox(x0=50.0, y0=40.0, x1=900.0, y1=80.0),
            confidence=1.0,
            reading_order=len(blocks) + 1
        ))

        t_data = TableData(headers=headers, rows=data_rows, is_multi_page=False)
        blocks.append(SemanticBlock(
            id=f"blk_sheet_data_{page_idx}",
            page=page_idx,
            type=BlockType.TABLE,
            text=f"Table: {sheet_name}",
            bbox=BoundingBox(x0=50.0, y0=90.0, x1=950.0, y1=900.0),
            confidence=0.99,
            reading_order=len(blocks) + 1,
            table_data=t_data
        ))
        page_idx += 1

    return blocks

def parse_presentation(filename: str, content: bytes) -> List[SemanticBlock]:
    """Converts PPTX slides into structured SemanticBlocks."""
    prs = Presentation(io.BytesIO(content))
    blocks: List[SemanticBlock] = []

    for slide_idx, slide in enumerate(prs.slides, start=1):
        order = 1
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue

            text = shape.text_frame.text.strip()
            if not text:
                continue

            is_title = (shape == slide.shapes.title) or (order == 1)
            block_type = BlockType.HEADING if is_title else BlockType.PARAGRAPH

            blocks.append(SemanticBlock(
                id=f"blk_slide_{slide_idx}_{order}",
                page=slide_idx,
                type=block_type,
                level=1 if is_title else None,
                text=text,
                bbox=BoundingBox(x0=50.0, y0=100.0 * order, x1=900.0, y1=(100.0 * order) + 60.0),
                confidence=0.98,
                reading_order=len(blocks) + 1
            ))
            order += 1

    return blocks

def parse_image_metadata(filename: str, content: bytes) -> List[SemanticBlock]:
    """Reads basic image geometry and initializes bounding canvas."""
    img = Image.open(io.BytesIO(content))
    w, h = img.size

    return [
        SemanticBlock(
            id="blk_img_01",
            page=1,
            type=BlockType.FIGURE,
            text=f"Image Scan: {filename} ({w}x{h} px)",
            bbox=BoundingBox(x0=20.0, y0=20.0, x1=980.0, y1=980.0),
            confidence=0.95,
            reading_order=1
        )
    ]