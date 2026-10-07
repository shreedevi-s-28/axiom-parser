export interface BoundingBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface TableCell {
  row: number;
  col: number;
  text: string;
  rowspan: number;
  colspan: number;
  bbox: BoundingBox;
}

export interface TableData {
  headers: string[];
  rows: string[][];
  cells: TableCell[];
  is_multi_page: boolean;
  continued_pages: number[];
}

export interface Block {
  id: string;
  page: number;
  type: string;
  text: string;
  bbox: BoundingBox;
  confidence: number;
  reading_order: number;
  level: number | null;
  table_data: TableData | null;
  chart_data: unknown | null;
  latex: string | null;
  flagged_for_review: boolean;
  review_reason: string | null;
}

export interface DocumentMetrics {
  processing_time_ms: number;
  estimated_cost_usd: number;
  confidence_average: number;
  total_pages: number;
  total_blocks: number;
}

export interface DocumentResult {
  document_id: string;
  filename: string;
  file_type: string;
  page_count: number;
  metrics: DocumentMetrics;
  blocks: Block[];
  markdown: string;
}

export interface RFC7807Error {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance: string;
}