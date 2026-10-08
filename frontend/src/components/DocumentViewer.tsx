import React, { useEffect, useState } from 'react';
import type { Block } from '../types/document';
import { BoundingBox } from './BoundingBox';
import { DocumentPageLayer } from './DocumentPageLayer';

interface DocumentViewerProps {
  /** null until a document has been analysed */
  filename: string | null;
  pageNumber: number;
  pageCount: number;
  /** Real page size in PDF points; null when unknown (used only for the aspect ratio). */
  pageSize: { width: number; height: number } | null;
  imageUrl: string | null;
  emptyTitle: string;
  emptyBody: string;
  /** Blocks on the current page only. */
  blocks: Block[];
  selectedBlockId: string | null;
  hoveredBlockId: string | null;
  onSelectBlock: (id: string) => void;
  onHoverBlock: (id: string | null) => void;
  onPageChange: (page: number) => void;
}

const PAGE_WIDTH = 954;
const PAGE_HEIGHT = 1000;

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
  filename,
  pageNumber,
  pageCount,
  pageSize,
  imageUrl,
  emptyTitle,
  emptyBody,
  blocks,
  selectedBlockId,
  hoveredBlockId,
  onSelectBlock,
  onHoverBlock,
  onPageChange,
}) => {
  const [zoom, setZoom] = useState(100);
  const [showBoundingBoxes, setShowBoundingBoxes] = useState(true);
  const [fitScale, setFitScale] = useState(1);

  useEffect(() => {
    const updateScale = () => {
      const availableWidth = window.innerWidth - 230 - 280 - 80;
      const scale = Math.min(1, Math.max(0.65, availableWidth / PAGE_WIDTH));
      setFitScale(scale);
    };

    updateScale();

    window.addEventListener('resize', updateScale);

    return () => {
      window.removeEventListener('resize', updateScale);
    };
  }, []);

  const handleZoomIn = () => {
    setZoom((prev) => Math.min(prev + 10, 180));
  };

  const handleZoomOut = () => {
    setZoom((prev) => Math.max(prev - 10, 60));
  };

  const handleResetZoom = () => {
    setZoom(100);
  };

  const scale = fitScale * (zoom / 100);

  const pageHeight = pageSize
    ? Math.round(PAGE_WIDTH * (pageSize.height / pageSize.width))
    : PAGE_HEIGHT;

  const pageLabel = String(pageNumber).padStart(2, '0');
  const totalLabel = String(pageCount).padStart(2, '0');

  return (
    <div className="h-full w-full bg-[#e9e5dd] flex flex-col">

      {/* TOOLBAR */}
      <div className="h-14 shrink-0 bg-[#f7f5f0] border-b border-stone-300 px-6 flex items-center justify-between">

        <div className="flex items-center gap-5 min-w-0">

          <div className="min-w-0">
            <p className="text-[9px] uppercase tracking-[0.2em] text-stone-400 mb-1">
              Source Document
            </p>

            <p className="text-sm font-medium text-stone-800 truncate max-w-[360px]">
              {filename ?? 'No document loaded'}
            </p>
          </div>

          <div className="h-6 w-px bg-stone-300 shrink-0" />

          {/* PAGE NAVIGATION */}
          <div className="flex items-center border border-stone-300 bg-white h-7 text-[9px] font-mono tracking-wider text-stone-500">

            <button
              type="button"
              onClick={() => onPageChange(pageNumber - 1)}
              disabled={!filename || pageNumber <= 1}
              className="w-7 h-full hover:bg-stone-100 transition-colors disabled:opacity-30 disabled:hover:bg-white"
              title="Previous page"
            >
              ‹
            </button>

            <span className="px-3 border-x border-stone-300 h-full flex items-center">
              {filename ? `PAGE ${pageLabel} / ${totalLabel}` : 'PAGE —'}
            </span>

            <button
              type="button"
              onClick={() => onPageChange(pageNumber + 1)}
              disabled={!filename || pageNumber >= pageCount}
              className="w-7 h-full hover:bg-stone-100 transition-colors disabled:opacity-30 disabled:hover:bg-white"
              title="Next page"
            >
              ›
            </button>

          </div>

        </div>


        <div className="flex items-center gap-5 shrink-0">

          {/* GROUNDING */}
          <label className="flex items-center gap-2 cursor-pointer text-[9px] uppercase tracking-[0.14em] text-stone-500">

            <input
              type="checkbox"
              checked={showBoundingBoxes}
              onChange={(e) => setShowBoundingBoxes(e.target.checked)}
              className="accent-slate-700"
            />

            <span>Grounding</span>

          </label>


          {/* ZOOM */}
          <div className="flex items-center border border-stone-300 bg-white h-7">

            <button
              type="button"
              onClick={handleZoomOut}
              className="w-8 h-full text-stone-500 hover:bg-stone-100 transition-colors"
              title="Zoom out"
            >
              −
            </button>

            <button
              type="button"
              onClick={handleResetZoom}
              className="h-full px-3 border-x border-stone-300 text-[9px] font-mono text-stone-600 hover:bg-stone-100 transition-colors"
            >
              {zoom}%
            </button>

            <button
              type="button"
              onClick={handleZoomIn}
              className="w-8 h-full text-stone-500 hover:bg-stone-100 transition-colors"
              title="Zoom in"
            >
              +
            </button>

          </div>

        </div>

      </div>


      {/* DOCUMENT WORKSPACE */}
      <div className="flex-1 min-h-0 overflow-auto">

        {filename ? (
          <div className="min-h-full w-full flex justify-center items-start px-10 py-10">

            {/* SCALED PAGE FRAME */}
            <div
              className="relative shrink-0"
              style={{
                width: `${PAGE_WIDTH * scale}px`,
                height: `${pageHeight * scale}px`,
              }}
            >

              {/* ACTUAL PAGE */}
              <div
                className="absolute left-0 top-0 bg-white border border-stone-300 shadow-[0_12px_35px_rgba(55,48,40,0.14)]"
                style={{
                  width: `${PAGE_WIDTH}px`,
                  height: `${pageHeight}px`,
                  transform: `scale(${scale})`,
                  transformOrigin: 'top left',
                }}
                onClick={() => onSelectBlock('')}
              >

                <DocumentPageLayer
                  key={imageUrl ?? `page-${pageNumber}`}
                  imageUrl={imageUrl}
                  pageNumber={pageNumber}
                />

                {/* GROUNDING OVERLAY */}
                {showBoundingBoxes &&
                  blocks.map((block) => (
                    <BoundingBox
                      key={block.id}
                      block={block}
                      isSelected={block.id === selectedBlockId}
                      isHovered={block.id === hoveredBlockId}
                      onSelectBlock={onSelectBlock}
                      onHoverBlock={onHoverBlock}
                    />
                  ))}

              </div>

            </div>

          </div>
        ) : (
          /* EMPTY / LOADING STATE */
          <div className="h-full w-full flex items-center justify-center px-10">
            <div className="max-w-sm text-center">
              <p className="font-serif text-lg text-stone-700">
                {emptyTitle}
              </p>

              <p className="mt-2 text-xs leading-relaxed text-stone-500">
                {emptyBody}
              </p>
            </div>
          </div>
        )}

      </div>


      {/* STATUS BAR */}
      <div className="h-8 shrink-0 bg-[#f7f5f0] border-t border-stone-300 px-6 flex items-center justify-between text-[9px] font-mono text-stone-500">

        <div className="flex items-center gap-6">

          <span>
            {String(blocks.length).padStart(2, '0')} BLOCKS ON PAGE
          </span>

          <span>
            COORDINATES: TOP-LEFT
          </span>

        </div>

        <div className="flex items-center gap-5">

          <span>
            {filename ? `PAGE ${pageLabel}` : 'NO DOCUMENT'}
          </span>

          <span className="text-stone-700">
            ZOOM {zoom}%
          </span>

        </div>

      </div>

    </div>
  );
};