import React from 'react';
import type { Block } from '../types/document';
import { NORMALIZED_SPACE, needsReview, transformBboxToPercentage } from '../utils/coordinates';

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
  // Backend boxes live in a normalised 0-1000 space; place them as percentages of the page.
  const rect = transformBboxToPercentage(block.bbox, NORMALIZED_SPACE);

  const flagged = needsReview(block);

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
          ? flagged
            ? 'border-2 border-orange-500 bg-orange-500/10'
            : 'border-2 border-slate-800 bg-slate-900/5'
          : isHovered
            ? 'border border-slate-700 bg-slate-900/5'
            : 'border border-slate-400/30 bg-transparent'
      }`}
      style={{
        left: `${rect.leftPercent}%`,
        top: `${rect.topPercent}%`,
        width: `${rect.widthPercent}%`,
        height: `${rect.heightPercent}%`,
      }}
      title={
        block.confidence === null
          ? `${block.id} — ${block.type}`
          : `${block.id} — ${Math.round(block.confidence * 100)}% confidence`
      }
    >
      {/* BLOCK LABEL */}
      {(isSelected || isHovered || flagged) && (
        <span
          className={`absolute -top-5 left-0 px-1.5 py-0.5 text-[8px] font-mono tracking-wide ${
            flagged
              ? 'bg-orange-500 text-white'
              : 'bg-slate-800 text-white'
          }`}
        >
          {block.id}
        </span>
      )}

      {/* REVIEW MARKER */}
      {flagged && (
        <span
          className="absolute -right-1.5 -top-1.5 h-3 w-3 rounded-full bg-orange-500 border-2 border-white"
          title="Needs review"
        />
      )}
    </button>
  );
};