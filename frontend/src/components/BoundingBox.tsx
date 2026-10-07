import React from 'react';
import type { Block } from '../types/document';

interface BoundingBoxProps {
  block: Block;
  isSelected: boolean;
  isHovered: boolean;
  onSelectBlock: (id: string) => void;
  onHoverBlock: (id: string | null) => void;
}

export const BoundingBox: React.FC<BoundingBoxProps> = ({
  block,
  isSelected,
  isHovered,
  onSelectBlock,
  onHoverBlock,
}) => {
  const { x0, y0, x1, y1 } = block.bbox;

  const width = x1 - x0;
  const height = y1 - y0;

  const needsReview =
    block.confidence < 0.7 || block.flagged_for_review;

  return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onSelectBlock(block.id);
      }}
      onMouseEnter={() => onHoverBlock(block.id)}
      onMouseLeave={() => onHoverBlock(null)}
      className={`absolute text-left transition-all duration-150 ${
        isSelected
          ? needsReview
            ? 'border-2 border-orange-500 bg-orange-500/10'
            : 'border-2 border-slate-800 bg-slate-900/5'
          : isHovered
            ? 'border border-slate-700 bg-slate-900/5'
            : 'border border-slate-400/30 bg-transparent'
      }`}
      style={{
        left: `${x0}px`,
        top: `${y0}px`,
        width: `${width}px`,
        height: `${height}px`,
      }}
      title={`${block.id} — ${Math.round(block.confidence * 100)}% confidence`}
    >
      {/* BLOCK LABEL */}
      {(isSelected || isHovered || needsReview) && (
        <span
          className={`absolute -top-5 left-0 px-1.5 py-0.5 text-[8px] font-mono tracking-wide ${
            needsReview
              ? 'bg-orange-500 text-white'
              : 'bg-slate-800 text-white'
          }`}
        >
          {block.id}
        </span>
      )}

      {/* REVIEW MARKER */}
      {needsReview && (
        <span
          className="absolute -right-1.5 -top-1.5 h-3 w-3 rounded-full bg-orange-500 border-2 border-white"
          title="Needs review"
        />
      )}
    </button>
  );
};