from __future__ import annotations
from enum import Enum
from typing import List, Optional, Union
from pydantic import BaseModel, Field

# 1. Allowed block types in the document
class BlockType(str, Enum):
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    FIGURE = "figure"
    EQUATION = "equation"
    HEADER = "header"
    FOOTER = "footer"

# 2. Normalized bounding box coordinates (scaled 0.0 to 1000.0)
class BoundingBox(BaseModel):
    x0: float = Field(..., ge=0.0, le=1000.0)
    y0: float = Field(..., ge=0.0, le=1000.0)
    x1: float = Field(..., ge=0.0, le=1000.0)
    y1: float = Field(..., ge=0.0, le=1000.0)

# 3. Table representation
class TableCell(BaseModel):
    row: int
    col: int
    text: str
    rowspan: int = 1
    colspan: int = 1
    bbox: Optional[BoundingBox] = None

class TableData(BaseModel):
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)
    cells: List[TableCell] = Field(default_factory=list)
    is_multi_page: bool = False
    continued_pages: List[int] = Field(default_factory=list)

# 4. Chart data representation
class ChartDataPoint(BaseModel):
    x: Union[str, float]
    y: float

class ChartSeries(BaseModel):
    name: str
    data: List[ChartDataPoint]

class ChartData(BaseModel):
    chart_type: str = "bar_chart"
    title: Optional[str] = None
    x_label: Optional[str] = None
    y_label: Optional[str] = None
    series: List[ChartSeries] = Field(default_factory=list)

# 5. Core semantic block for every extracted unit
class SemanticBlock(BaseModel):
    id: str
    page: int
    type: BlockType
    text: str
    bbox: BoundingBox
    confidence: float = Field(..., ge=0.0, le=1.0)
    reading_order: int
    level: Optional[int] = None
    table_data: Optional[TableData] = None
    chart_data: Optional[ChartData] = None
    latex: Optional[str] = None
    flagged_for_review: bool = False
    review_reason: Optional[str] = None

# 6. Metadata and metrics
class DocumentMetrics(BaseModel):
    processing_time_ms: float
    estimated_cost_usd: float
    confidence_average: float
    total_pages: int
    total_blocks: int

# 7. Final unified JSON output schema
class ParseResult(BaseModel):
    document_id: str
    filename: str
    file_type: str
    page_count: int
    metrics: DocumentMetrics
    blocks: List[SemanticBlock]
    markdown: str