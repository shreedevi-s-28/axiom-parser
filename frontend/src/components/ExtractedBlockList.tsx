import React from 'react';
import type { Block } from '../types/document';
import { formatConfidence } from '../utils/coordinates';

interface ExtractedBlockListProps {
  blocks: Block[];
  selectedBlockId: string | null;
  hoveredBlockId: string | null;
  onSelectBlock: (id: string) => void;
  onHoverBlock: (id: string | null) => void;
}

export const ExtractedBlockList: React.FC<ExtractedBlockListProps> = ({
  blocks,
  selectedBlockId,
  hoveredBlockId,
  onSelectBlock,
  onHoverBlock,
}) => {
  return (
    <div className="h-full bg-[#242424] text-stone-200 flex flex-col">

      {/* PANEL HEADER */}
      <div className="px-5 py-5 border-b border-stone-700/70">

        <p className="text-[9px] uppercase tracking-[0.22em] text-stone-500">
          Document Structure
        </p>

        <div className="flex items-end justify-between mt-2">

          <h2 className="font-serif text-lg text-stone-100 leading-none">
            Extracted Blocks
          </h2>

          <span className="text-[10px] font-mono text-stone-500">
            {String(blocks.length).padStart(2, '0')}
          </span>

        </div>

      </div>


      {/* BLOCK LIST */}
      <div className="flex-1 overflow-y-auto">

        {blocks.map((block, index) => {

          const isSelected = block.id === selectedBlockId;
          const isHovered = block.id === hoveredBlockId;

          const isLowConfidence =
            block.confidence < 0.7 ||
            block.flagged_for_review;

          return (
            <button
              key={block.id}
              type="button"
              onClick={() => onSelectBlock(block.id)}
              onMouseEnter={() => onHoverBlock(block.id)}
              onMouseLeave={() => onHoverBlock(null)}
              className={`relative w-full text-left px-5 py-4 border-b border-stone-700/60 transition-colors ${
                isSelected
                  ? 'bg-stone-700/70'
                  : isHovered
                    ? 'bg-stone-800/70'
                    : 'hover:bg-stone-800/50'
              }`}
            >

              {/* ACTIVE MARKER */}
              {isSelected && (
                <span className="absolute left-0 top-0 bottom-0 w-0.5 bg-stone-200" />
              )}


              <div className="flex items-start gap-3">

                {/* NUMBER */}
                <span
                  className={`font-mono text-[10px] pt-0.5 w-5 shrink-0 ${
                    isSelected
                      ? 'text-stone-200'
                      : 'text-stone-600'
                  }`}
                >
                  {String(index + 1).padStart(2, '0')}
                </span>


                <div className="min-w-0 flex-1">

                  {/* TYPE + CONFIDENCE */}
                  <div className="flex items-center justify-between gap-3 mb-2">

                    <span
                      className={`text-[9px] uppercase tracking-[0.16em] ${
                        isSelected
                          ? 'text-stone-300'
                          : 'text-stone-500'
                      }`}
                    >
                      {block.type}
                    </span>

                    <span
                      className={`text-[10px] font-mono ${
                        isLowConfidence
                          ? 'text-orange-300'
                          : isSelected
                            ? 'text-stone-300'
                            : 'text-stone-500'
                      }`}
                    >
                      {formatConfidence(block.confidence)}
                    </span>

                  </div>


                  {/* TEXT */}
                  <p
                    className={`text-xs leading-[1.55] line-clamp-2 ${
                      isSelected
                        ? 'text-stone-100'
                        : 'text-stone-400'
                    }`}
                  >
                    {block.text}
                  </p>


                  {/* META */}
                  <div className="flex items-center justify-between mt-3">

                    <span className="text-[9px] font-mono text-stone-600">
                      PAGE {String(block.page).padStart(2, '0')}
                    </span>

                    {block.flagged_for_review && (
                      <span className="flex items-center gap-1.5 text-[9px] uppercase tracking-wider text-orange-300">

                        <span className="h-1.5 w-1.5 rounded-full bg-orange-400" />

                        Review

                      </span>
                    )}

                  </div>

                </div>

              </div>

            </button>
          );
        })}

      </div>


      {/* PANEL FOOTER */}
      <div className="px-5 py-3 border-t border-stone-700/70 text-[9px] font-mono text-stone-600 flex items-center justify-between">

        <span>
          READING ORDER
        </span>

        <span>
          01 → {String(blocks.length).padStart(2, '0')}
        </span>

      </div>

    </div>
  );
};