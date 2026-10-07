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
)

def create_mock():
    # 1. Sample financial table
    sample_table = TableData(
        headers=["Tranche", "Principal ($M)", "Rate"],
        rows=[
            ["Term Loan B", "620.0", "SOFR + 2.50%"],
            ["Senior Notes", "400.0", "5.875%"],
        ],
        is_multi_page=False,
        continued_pages=[1],
    )

    # 2. Block 1: Document heading
    b1 = SemanticBlock(
        id="blk_001",
        page=1,
        type=BlockType.HEADING,
        level=1,
        text="Executive Financial Summary",
        bbox=BoundingBox(x0=50.0, y0=50.0, x1=900.0, y1=90.0),
        confidence=0.99,
        reading_order=1,
    )

    # 3. Block 2: Financial table block
    b2 = SemanticBlock(
        id="blk_002",
        page=1,
        type=BlockType.TABLE,
        text="Debt Structure Summary",
        bbox=BoundingBox(x0=50.0, y0=110.0, x1=900.0, y1=300.0),
        confidence=0.95,
        reading_order=2,
        table_data=sample_table,
    )

    # 4. Processing metrics
    metrics = DocumentMetrics(
        processing_time_ms=840.0,
        estimated_cost_usd=0.00065,
        confidence_average=0.97,
        total_pages=1,
        total_blocks=2,
    )

    # 5. Full ParseResult object
    result = ParseResult(
        document_id="doc_mock_123",
        filename="sample_filing.pdf",
        file_type="application/pdf",
        page_count=1,
        metrics=metrics,
        blocks=[b1, b2],
        markdown="# Executive Financial Summary\n\n| Tranche | Principal ($M) | Rate |\n| --- | --- | --- |\n| Term Loan B | 620.0 | SOFR + 2.50% |\n| Senior Notes | 400.0 | 5.875% |",
    )

    # 6. Ensure contracts/ directory exists and write JSON
    os.makedirs("contracts", exist_ok=True)
    target_path = os.path.join("contracts", "mock_result.json")
    with open(target_path, "w") as f:
        f.write(result.model_dump_json(indent=2))

    print(f"SUCCESS: {target_path} created and validated!")

if __name__ == "__main__":
    create_mock()