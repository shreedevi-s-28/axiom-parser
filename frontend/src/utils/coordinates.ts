import type { BoundingBox } from '../types/document';

export interface PageDimensions {
  width: number;
  height: number;
}

export const DEFAULT_PAGE_DIMENSIONS: PageDimensions = {
  width: 954,
  height: 1000,
};

/** The backend normalises every bounding box to a 0-1000 square, regardless of page size. */
export const NORMALIZED_SPACE: PageDimensions = {
  width: 1000,
  height: 1000,
};

export interface CalculatedRect {
  leftPercent: number;
  topPercent: number;
  widthPercent: number;
  heightPercent: number;
  width: number;
  height: number;
}

export function transformBboxToPercentage(
  bbox: BoundingBox,
  pageDim: PageDimensions = DEFAULT_PAGE_DIMENSIONS
): CalculatedRect {
  const width = Math.max(0, bbox.x1 - bbox.x0);
  const height = Math.max(0, bbox.y1 - bbox.y0);

  return {
    leftPercent: (bbox.x0 / pageDim.width) * 100,
    topPercent: (bbox.y0 / pageDim.height) * 100,
    widthPercent: (width / pageDim.width) * 100,
    heightPercent: (height / pageDim.height) * 100,
    width,
    height,
  };
}

export function formatConfidence(confidence: number | null): string {
  return confidence === null ? 'N/A' : `${Math.round(confidence * 100)}%`;
}

export const REVIEW_CONFIDENCE_THRESHOLD = 0.7;

export function needsReview(block: {
  confidence: number | null;
  flagged_for_review: boolean;
}): boolean {
  return (
    block.flagged_for_review ||
    (block.confidence !== null && block.confidence < REVIEW_CONFIDENCE_THRESHOLD)
  );
}