import React from 'react';
import type { Block } from '../types/document';
import { formatConfidence, needsReview } from '../utils/coordinates';

interface AuditQueueProps {
  blocks: Block[];
  selectedBlockId: string | null;
  onSelectBlock: (id: string) => void;
}

export const AuditQueue: React.FC<AuditQueueProps> = ({
  blocks,
  selectedBlockId,
  onSelectBlock,
}) => {
  const selectedBlock =
    blocks.find((block) => block.id === selectedBlockId) ?? null;

  const auditBlocks = blocks.filter(needsReview);

  const confidencePercent =
    selectedBlock && selectedBlock.confidence !== null
      ? Math.round(selectedBlock.confidence * 100)
      : null;

  return (
    <section>

      {/* INSPECTOR HEADER */}
      <div className="pb-4 border-b border-stone-300">
        <p className="text-[9px] uppercase tracking-[0.2em] text-stone-500">
          Block Inspection
        </p>

        <h3 className="font-serif text-lg text-stone-800 mt-1">
          {selectedBlock
            ? selectedBlock.id
            : 'Select a block'}
        </h3>
      </div>

      {/* SELECTED BLOCK */}
      {selectedBlock ? (
        <div className="py-5 space-y-5">

          {/* TYPE */}
          <div>
            <p className="text-[9px] uppercase tracking-wider text-stone-400 mb-1">
              Block type
            </p>

            <p className="text-xs uppercase tracking-wider text-stone-700">
              {selectedBlock.type}
            </p>
          </div>

          {/* EXTRACTED TEXT */}
          <div>
            <p className="text-[9px] uppercase tracking-wider text-stone-400 mb-2">
              Extracted text
            </p>

            <div className="border-l-2 border-stone-300 pl-3">
              <p className="text-xs leading-relaxed text-stone-700">
                {selectedBlock.text}
              </p>
            </div>
          </div>

          {/* CONFIDENCE */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-[9px] uppercase tracking-wider text-stone-400">
                Confidence
              </p>

              <span
                className={`text-xs font-mono ${
                  confidencePercent !== null && confidencePercent < 70
                    ? 'text-orange-700'
                    : 'text-slate-700'
                }`}
              >
                {formatConfidence(selectedBlock.confidence)}
              </span>
            </div>

            {confidencePercent !== null ? (
              <div className="h-1 bg-stone-200">
                <div
                  className={`h-full ${
                    confidencePercent < 70
                      ? 'bg-orange-500'
                      : 'bg-slate-700'
                  }`}
                  style={{
                    width: `${confidencePercent}%`,
                  }}
                />
              </div>
            ) : (
              <p className="text-[10px] leading-relaxed text-stone-400">
                Not computed: this block was read from the PDF text layer, so no
                OCR confidence exists.
              </p>
            )}
          </div>

          {/* COORDINATES */}
          <div>
            <p className="text-[9px] uppercase tracking-wider text-stone-400 mb-2">
              Bounding coordinates
            </p>

            <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-[10px] font-mono">

              <div className="flex justify-between border-b border-stone-200 pb-1">
                <span className="text-stone-400">X0</span>
                <span className="text-stone-700">
                  {selectedBlock.bbox.x0}
                </span>
              </div>

              <div className="flex justify-between border-b border-stone-200 pb-1">
                <span className="text-stone-400">Y0</span>
                <span className="text-stone-700">
                  {selectedBlock.bbox.y0}
                </span>
              </div>

              <div className="flex justify-between border-b border-stone-200 pb-1">
                <span className="text-stone-400">X1</span>
                <span className="text-stone-700">
                  {selectedBlock.bbox.x1}
                </span>
              </div>

              <div className="flex justify-between border-b border-stone-200 pb-1">
                <span className="text-stone-400">Y1</span>
                <span className="text-stone-700">
                  {selectedBlock.bbox.y1}
                </span>
              </div>

            </div>
          </div>

          {/* READING ORDER */}
          <div className="space-y-2 border-t border-stone-200 pt-3">
            <div className="flex items-center justify-between">
              <span className="text-[9px] uppercase tracking-wider text-stone-400">
                Reading order
              </span>

              <span className="text-[10px] font-mono text-stone-700">
                {String(selectedBlock.reading_order).padStart(2, '0')}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-[9px] uppercase tracking-wider text-stone-400">
                Page
              </span>

              <span className="text-[10px] font-mono text-stone-700">
                {String(selectedBlock.page).padStart(2, '0')}
              </span>
            </div>

            {selectedBlock.font_size !== null && (
              <div className="flex items-center justify-between">
                <span className="text-[9px] uppercase tracking-wider text-stone-400">
                  Font size
                </span>

                <span className="text-[10px] font-mono text-stone-700">
                  {selectedBlock.font_size} pt
                </span>
              </div>
            )}
          </div>

          {/* REVIEW WARNING */}
          {needsReview(selectedBlock) && (
            <div className="border-l-2 border-orange-500 bg-orange-50 px-3 py-3">

              <p className="text-[9px] uppercase tracking-wider text-orange-700 mb-1">
                Manual review required
              </p>

              <p className="text-[10px] leading-relaxed text-orange-800">
                {selectedBlock.review_reason ||
                  'Confidence score is below the review threshold.'}
              </p>

            </div>
          )}

        </div>
      ) : (
        /* EMPTY INSPECTOR */
        <div className="py-8">
          <p className="text-xs leading-relaxed text-stone-500">
            Select an extracted block from the document structure
            or click a grounded region on the page to inspect its
            extracted content and coordinates.
          </p>
        </div>
      )}

      {/* REVIEW QUEUE */}
      <div className="border-t border-stone-300 pt-5">

        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-[9px] uppercase tracking-[0.16em] text-stone-400">
              Verification
            </p>

            <h4 className="font-serif text-base text-stone-800 mt-1">
              Review Queue
            </h4>
          </div>

          <span className="text-[10px] font-mono text-orange-700">
            {String(auditBlocks.length).padStart(2, '0')}
          </span>
        </div>

        <div className="space-y-1">

          {auditBlocks.length === 0 && (
            <p className="text-[10px] leading-relaxed text-stone-400">
              {blocks.length === 0
                ? 'Nothing to review yet.'
                : 'No blocks were flagged for review.'}
            </p>
          )}

          {auditBlocks.map((block) => (
            <button
              key={block.id}
              type="button"
              onClick={() => onSelectBlock(block.id)}
              className={`w-full flex items-center justify-between py-2 text-left border-b border-stone-200 ${
                block.id === selectedBlockId
                  ? 'text-orange-700'
                  : 'text-stone-600 hover:text-slate-900'
              }`}
            >
              <span className="text-[10px] font-mono">
                {block.id}
              </span>

              <span className="text-[10px] font-mono">
                {formatConfidence(block.confidence)}
              </span>
            </button>
          ))}

        </div>
      </div>

    </section>
  );
};