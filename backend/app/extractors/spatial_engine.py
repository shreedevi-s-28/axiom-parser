import pymupdf as fitz
import sys
import re
from collections import defaultdict


def extract_raw_spans(pdf_path: str) -> list[dict]:
    """Extract text lines from a PDF and normalize coordinates to a 0-1000 scale."""

    extracted_blocks = []

    with fitz.open(pdf_path) as doc:

        for page_num, page in enumerate(doc):
            rect = page.rect

            if rect.width <= 0 or rect.height <= 0:
                continue

            scale_x = 1000.0 / rect.width
            scale_y = 1000.0 / rect.height

            text_page = page.get_text("dict")

            for block_num, block in enumerate(text_page.get("blocks", [])):

                if "lines" not in block:
                    continue

                for line_num, line in enumerate(block["lines"]):

                    spans = line.get("spans", [])

                    if not spans:
                        continue

                    line_text = "".join(
                        span.get("text", "") for span in spans
                    ).strip()

                    if not line_text:
                        continue

                    raw_bbox = line.get("bbox")

                    if not raw_bbox or len(raw_bbox) != 4:
                        continue

                    x0, y0, x1, y1 = raw_bbox

                    normalized_bbox = [
                        round(x0 * scale_x, 1),
                        round(y0 * scale_y, 1),
                        round(x1 * scale_x, 1),
                        round(y1 * scale_y, 1),
                    ]

                    extracted_blocks.append({
                        "id": f"p{page_num + 1}_b{block_num}_l{line_num}",
                        "page": page_num + 1,
                        "text": line_text,
                        "bbox": normalized_bbox,
                        "font_size": round(
                            max(span.get("size", 0.0) for span in spans),
                            1
                        ),
                        "page_width": round(rect.width, 1),
                        "page_height": round(rect.height, 1),
                        "region": "body",        # Default region
                        "column_index": 0,       # Default column
                        "reading_order": 0,      # Computed in Phase 4
                        "semantic_type": "paragraph" # Computed in Phase 5
                    })

    return extracted_blocks


def validate_geometry(blocks: list[dict]) -> tuple[list[str], list[str]]:
    """Phase 1: Validate normalized bounding boxes within 0-1000 scale."""
    errors = []
    warnings = []

    for block in blocks:
        block_id = block.get("id", "unknown")
        bbox = block.get("bbox", [])
        page_w = block.get("page_width", 0)
        page_h = block.get("page_height", 0)
        text = block.get("text", "")

        if page_w <= 0 or page_h <= 0:
            errors.append(f"[{block_id}] Invalid page dimensions: width={page_w}, height={page_h}")

        if len(bbox) != 4:
            errors.append(f"[{block_id}] Bbox does not have 4 coordinates: {bbox}")
            continue

        x0, y0, x1, y1 = bbox

        if not (-0.1 <= x0 <= 1000.1 and -0.1 <= y0 <= 1000.1 and -0.1 <= x1 <= 1000.1 and -0.1 <= y1 <= 1000.1):
            errors.append(f"[{block_id}] Coordinates out of 0-1000 bounds: {bbox}")

        if x0 >= x1:
            warnings.append(f"[{block_id}] Inverted/Zero horizontal box: x0 ({x0}) >= x1 ({x1})")
        if y0 >= y1:
            warnings.append(f"[{block_id}] Inverted/Zero vertical box: y0 ({y0}) >= y1 ({y1})")

        if not text:
            warnings.append(f"[{block_id}] Empty text block detected")

    return errors, warnings


def detect_headers_footers(blocks: list[dict], header_threshold: float = 120.0, footer_threshold: float = 880.0) -> list[dict]:
    """Phase 2: Identifies repeated top/bottom elements across pages."""
    if not blocks:
        return blocks

    header_candidates = defaultdict(set)
    footer_candidates = defaultdict(set)

    total_pages = max(b["page"] for b in blocks)

    for b in blocks:
        y0 = b["bbox"][1]
        y1 = b["bbox"][3]
        text_clean = b["text"].strip().lower()

        if y0 <= header_threshold:
            header_candidates[text_clean].add(b["page"])

        if y1 >= footer_threshold:
            footer_candidates[text_clean].add(b["page"])

    min_page_occurrence = 2 if total_pages > 1 else 1

    repeated_headers = {
        txt for txt, pages in header_candidates.items() if len(pages) >= min_page_occurrence
    }
    repeated_footers = {
        txt for txt, pages in footer_candidates.items() if len(pages) >= min_page_occurrence
    }

    for b in blocks:
        y0 = b["bbox"][1]
        y1 = b["bbox"][3]
        text_clean = b["text"].strip().lower()

        if y0 <= header_threshold and (text_clean in repeated_headers or total_pages == 1):
            b["region"] = "header"
        elif y1 >= footer_threshold and (text_clean in repeated_footers or total_pages == 1):
            b["region"] = "footer"

    return blocks


def detect_columns(blocks: list[dict]) -> list[dict]:
    """Phase 3: Analyzes horizontal positions per page to detect multi-column layouts."""
    if not blocks:
        return blocks

    pages = defaultdict(list)
    for b in blocks:
        pages[b["page"]].append(b)

    for page_num, page_blocks in pages.items():
        body_blocks = [b for b in page_blocks if b["region"] == "body"]

        if not body_blocks:
            continue

        left_side_blocks = [b for b in body_blocks if b["bbox"][0] < 450 and b["bbox"][2] < 550]
        right_side_blocks = [b for b in body_blocks if b["bbox"][0] > 450]

        is_two_column = len(left_side_blocks) >= 3 and len(right_side_blocks) >= 3

        if is_two_column:
            for b in page_blocks:
                mid_x = (b["bbox"][0] + b["bbox"][2]) / 2.0
                if mid_x < 500:
                    b["column_index"] = 0
                else:
                    b["column_index"] = 1
        else:
            for b in page_blocks:
                b["column_index"] = 0

    return blocks


def determine_reading_order(blocks: list[dict]) -> list[dict]:
    """Phase 4: Assigns a logical reading order per page."""
    if not blocks:
        return blocks

    pages = defaultdict(list)
    for b in blocks:
        pages[b["page"]].append(b)

    ordered_blocks = []

    for page_num in sorted(pages.keys()):
        page_blocks = pages[page_num]

        headers = [b for b in page_blocks if b["region"] == "header"]
        footers = [b for b in page_blocks if b["region"] == "footer"]
        body_blocks = [b for b in page_blocks if b["region"] == "body"]

        headers_sorted = sorted(headers, key=lambda b: (b["bbox"][1], b["bbox"][0]))
        footers_sorted = sorted(footers, key=lambda b: (b["bbox"][1], b["bbox"][0]))
        body_sorted = sorted(
            body_blocks,
            key=lambda b: (b["column_index"], b["bbox"][1], b["bbox"][0])
        )

        page_ordered = headers_sorted + body_sorted + footers_sorted

        for order_idx, b in enumerate(page_ordered, start=1):
            b["reading_order"] = order_idx
            ordered_blocks.append(b)

    return ordered_blocks


def classify_semantic_types(blocks: list[dict]) -> list[dict]:
    """
    Phase 5: Classifies text blocks into semantic types based on font size,
    bullet patterns, header/footer regions, and text length.
    """
    if not blocks:
        return blocks

    # Compute median font size for body text baseline
    font_sizes = [b["font_size"] for b in blocks if b["font_size"] > 0]
    font_sizes.sort()
    median_size = font_sizes[len(font_sizes) // 2] if font_sizes else 12.0

    bullet_pattern = re.compile(r"^([\bullet\-\*\u2022\u2023\u25b6]|\d+[\.\)])\s+")

    for b in blocks:
        text = b["text"].strip()
        size = b["font_size"]

        if b["region"] == "header":
            b["semantic_type"] = "header"
            continue
        elif b["region"] == "footer":
            b["semantic_type"] = "footer"
            continue

        # Check for list items
        if bullet_pattern.match(text):
            b["semantic_type"] = "list_item"
            continue

        # Check for titles & headings based on font size ratio to median
        if size >= median_size * 1.8:
            b["semantic_type"] = "title"
        elif size >= median_size * 1.3:
            b["semantic_type"] = "heading"
        elif size >= median_size * 1.15 and len(text) < 80:
            b["semantic_type"] = "subheading"
        else:
            b["semantic_type"] = "paragraph"

    return blocks


if __name__ == "__main__":
    sample_pdf = sys.argv[1] if len(sys.argv) > 1 else "sample.pdf"

    try:
        blocks = extract_raw_spans(sample_pdf)
        print(f"Successfully extracted {len(blocks)} blocks from {sample_pdf}!")

        # Phase 1: Geometry Validation
        errors, warnings = validate_geometry(blocks)
        print("\n--- PHASE 1: GEOMETRY VALIDATION ---")
        print(f"Errors: {len(errors)}, Warnings: {len(warnings)}")

        # Phase 2: Header/Footer Detection
        blocks = detect_headers_footers(blocks)

        # Phase 3: Column Detection
        blocks = detect_columns(blocks)

        # Phase 4: Reading Order
        blocks = determine_reading_order(blocks)

        # Phase 5: Semantic Classification
        blocks = classify_semantic_types(blocks)

        print("\n--- PHASE 5: SEMANTIC CLASSIFICATION REPORT ---")
        type_counts = defaultdict(int)
        for b in blocks:
            type_counts[b["semantic_type"]] += 1

        for sem_type, count in sorted(type_counts.items()):
            print(f"  - {sem_type.title()}: {count} blocks")

        print("\n--- SAMPLE CLASSIFIED BLOCKS (PAGE 2) ---")
        page2_blocks = [b for b in blocks if b["page"] == 2]
        for b in sorted(page2_blocks, key=lambda x: x["reading_order"])[:8]:
            print(f"  [{b['semantic_type'].upper():10s} | Order {b['reading_order']:02d}] {b['text'][:65]}...")

    except Exception as e:
        print(f"Error: {e}")