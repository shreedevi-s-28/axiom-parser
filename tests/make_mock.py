import os
import sys

# Ensure Python can find the backend package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.schemas.document import (
    ParseResult,
    DocumentMetrics,
    SemanticBlock,
    BlockType,
    BoundingBox,
    TableData,
    TableCell,
)

def create_mock():
    # 1. Sample financial table cells with bounding boxes
    sample_cells = [
        TableCell(row=0, col=0, text="Term Loan B", bbox=BoundingBox(x0=54.0, y0=140.0, x1=300.0, y1=165.0)),
        TableCell(row=0, col=1, text="620.0", bbox=BoundingBox(x0=310.0, y0=140.0, x1=500.0, y1=165.0)),
        TableCell(row=0, col=2, text="SOFR + 2.50%", bbox=BoundingBox(x0=510.0, y0=140.0, x1=900.0, y1=165.0)),
        TableCell(row=1, col=0, text="Senior Notes", bbox=BoundingBox(x0=54.0, y0=170.0, x1=300.0, y1=195.0)),
        TableCell(row=1, col=1, text="400.0", bbox=BoundingBox(x0=310.0, y0=170.0, x1=500.0, y1=195.0)),
        TableCell(row=1, col=2, text="5.875%", bbox=BoundingBox(x0=510.0, y0=170.0, x1=900.0, y1=195.0)),
    ]

    sample_table = TableData(
        headers=["Tranche", "Principal ($M)", "Rate"],
        rows=[
            ["Term Loan B", "620.0", "SOFR + 2.50%"],
            ["Senior Notes", "400.0", "5.875%"],
        ],
        cells=sample_cells,
        is_multi_page=False,
        continued_pages=[1],
    )

    # 2. Block 1: Heading
    b1 = SemanticBlock(
        id="blk_001",
        page=1,
        type=BlockType.HEADING,
        level=1,
        text="Executive Financial Summary",
        bbox=BoundingBox(x0=54.0, y0=60.0, x1=900.0, y1=95.0),
        confidence=0.99,
        reading_order=1,
    )

    # 3. Block 2: Narrative paragraph
    b2 = SemanticBlock(
        id="blk_002",
        page=1,
        type=BlockType.PARAGRAPH,
        text="The following review reflects our consolidated debt obligations and capital structure maturities.",
        bbox=BoundingBox(x0=54.0, y0=100.0, x1=900.0, y1=130.0),
        confidence=0.98,
        reading_order=2,
    )

    # 4. Block 3: Debt structure table
    b3 = SemanticBlock(
        id="blk_003",
        page=1,
        type=BlockType.TABLE,
        text="Debt Structure Summary",
        bbox=BoundingBox(x0=54.0, y0=135.0, x1=900.0, y1=205.0),
        confidence=0.95,
        reading_order=3,
        table_data=sample_table,
    )

    # 5. Block 4: Flagged low-confidence block (for Diligence Audit Queue testing)
    b4 = SemanticBlock(
        id="blk_004",
        page=1,
        type=BlockType.PARAGRAPH,
        text="* Note 4: Excludes $12.5M deferred financing costs amortized over facility tenure.",
        bbox=BoundingBox(x0=54.0, y0=900.0, x1=900.0, y1=935.0),
        confidence=0.58,
        reading_order=4,
        flagged_for_review=True,
        review_reason="Degraded ink contrast: OCR confidence below 0.70 threshold"
    )

    # 6. Document metrics
    metrics = DocumentMetrics(
        processing_time_ms=840.0,
        estimated_cost_usd=0.00065,
        confidence_average=0.875,
        total_pages=1,
        total_blocks=4,
    )

    result = ParseResult(
        document_id="doc_mock_123",
        filename="sample_filing.pdf",
        file_type="application/pdf",
        page_count=1,
        metrics=metrics,
        blocks=[b1, b2, b3, b4],
        markdown="# Executive Financial Summary\n\nThe following review reflects our consolidated debt obligations and capital structure maturities.\n\n| Tranche | Principal ($M) | Rate |\n| --- | --- | --- |\n| Term Loan B | 620.0 | SOFR + 2.50% |\n| Senior Notes | 400.0 | 5.875% |\n\n* Note 4: Excludes $12.5M deferred financing costs amortized over facility tenure.",
    )

    os.makedirs("contracts", exist_ok=True)
    target_path = os.path.join("contracts", "mock_result.json")
    with open(target_path, "w") as f:
        f.write(result.model_dump_json(indent=2))

    print(f"SUCCESS: {target_path} re-generated!")

if __name__ == "__main__":
    create_mock()