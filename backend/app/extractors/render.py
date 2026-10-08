# backend/app/extractors/render.py
import pymupdf as fitz

TARGET_WIDTH_PX = 1100


def render_page_png(pdf_path: str, page_number: int, target_width: int = TARGET_WIDTH_PX) -> bytes:
    """Render a 1-based PDF page to PNG bytes. Raises IndexError for an out-of-range page."""
    with fitz.open(pdf_path) as doc:
        if page_number < 1 or page_number > len(doc):
            raise IndexError(f"Page {page_number} out of range 1-{len(doc)}")
        page = doc[page_number - 1]
        zoom = target_width / page.rect.width if page.rect.width > 0 else 1.0
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return pixmap.tobytes("png")
