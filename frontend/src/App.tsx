import { useState } from 'react';
import { DocumentViewer } from './components/DocumentViewer';
import { ExtractedBlockList } from './components/ExtractedBlockList';
import { AuditQueue } from './components/AuditQueue';
import { EconomicsHUD } from './components/EconomicsHUD';
import type { Block } from './types/document';

const mockBlocks: Block[] = [
  {
    id: 'blk_001',
    page: 1,
    type: 'heading',
    text: 'Annual Financial Report 2025',
    bbox: { x0: 100, y0: 80, x1: 850, y1: 150 },
    confidence: 0.98,
    reading_order: 1,
    level: 1,
    table_data: null,
    chart_data: null,
    latex: null,
    flagged_for_review: false,
    review_reason: null,
  },
  {
    id: 'blk_002',
    page: 1,
    type: 'paragraph',
    text: 'This document contains the annual financial results and operational summary.',
    bbox: { x0: 100, y0: 190, x1: 850, y1: 280 },
    confidence: 0.94,
    reading_order: 2,
    level: null,
    table_data: null,
    chart_data: null,
    latex: null,
    flagged_for_review: false,
    review_reason: null,
  },
  {
    id: 'blk_003',
    page: 1,
    type: 'table',
    text: 'Revenue increased by 18% compared with the previous year.',
    bbox: { x0: 100, y0: 330, x1: 850, y1: 500 },
    confidence: 0.91,
    reading_order: 3,
    level: null,
    table_data: null,
    chart_data: null,
    latex: null,
    flagged_for_review: false,
    review_reason: null,
  },
  {
    id: 'blk_004',
    page: 1,
    type: 'paragraph',
    text: 'Operating expenses increased significantly during the reporting period.',
    bbox: { x0: 100, y0: 540, x1: 850, y1: 650 },
    confidence: 0.58,
    reading_order: 4,
    level: null,
    table_data: null,
    chart_data: null,
    latex: null,
    flagged_for_review: true,
    review_reason: 'Low OCR confidence. Manual verification recommended.',
  },
];

function App() {
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null);
  const [hoveredBlockId, setHoveredBlockId] = useState<string | null>(null);

  const totalPages = 1;
  const pagesProcessed = 1;
  const estimatedCost = 0.0048;
  const processingTime = 2.7;

  return (
    <div className="h-screen bg-stone-100 text-slate-900 flex flex-col overflow-hidden">

      {/* TOP BAR */}
      <header className="h-16 shrink-0 bg-white border-b border-stone-300 px-6 flex items-center justify-between">

        <div className="flex items-center gap-4">

          <div className="h-9 w-9 border-2 border-slate-900 flex items-center justify-center font-serif text-lg font-bold">
            A
          </div>

          <div className="leading-tight">
            <h1 className="text-base font-semibold tracking-tight text-slate-900">
              AxiomParse
            </h1>

            <p className="text-[9px] uppercase tracking-[0.2em] text-stone-500 mt-1">
              Document Examination Workbench
            </p>
          </div>

        </div>

        <div className="flex items-center gap-7 text-[10px] font-mono">

          <span className="text-stone-500">
            REPORT / 2025
          </span>

          <span className="flex items-center gap-2 text-emerald-700">
            <span className="h-2 w-2 rounded-full bg-emerald-600" />
            SYSTEM READY
          </span>

        </div>

      </header>


      {/* MAIN WORKSPACE */}
      <div className="flex-1 min-h-0 flex">

        {/* LEFT — DOCUMENT STRUCTURE */}
        <aside className="w-[230px] shrink-0 bg-[#242424] border-r border-stone-700 overflow-hidden">

          <ExtractedBlockList
            blocks={mockBlocks}
            selectedBlockId={selectedBlockId}
            hoveredBlockId={hoveredBlockId}
            onSelectBlock={setSelectedBlockId}
            onHoverBlock={setHoveredBlockId}
          />

        </aside>


        {/* CENTER — DOCUMENT */}
        <main className="flex-1 min-w-0 min-h-0 bg-[#e9e5dd] overflow-hidden">

          <DocumentViewer
            filename="annual_report_2025.pdf"
            pageNumber={1}
            blocks={mockBlocks}
            selectedBlockId={selectedBlockId}
            hoveredBlockId={hoveredBlockId}
            onSelectBlock={setSelectedBlockId}
            onHoverBlock={setHoveredBlockId}
          />

        </main>


        {/* RIGHT — INSPECTION */}
        <aside className="w-[280px] shrink-0 bg-[#fbfaf7] border-l border-stone-300 overflow-y-auto">

          <div className="p-5">

            <EconomicsHUD
              pagesProcessed={pagesProcessed}
              totalPages={totalPages}
              estimatedCost={estimatedCost}
              processingTime={processingTime}
            />

            <div className="pt-5">

              <AuditQueue
                blocks={mockBlocks}
                selectedBlockId={selectedBlockId}
                onSelectBlock={setSelectedBlockId}
              />

            </div>

          </div>

        </aside>

      </div>


      {/* BOTTOM STATUS BAR */}
      <footer className="h-8 shrink-0 bg-slate-900 text-slate-300 px-6 flex items-center justify-between text-[9px] font-mono">

        <span>
          AXIOMPARSE / EXTRACTION SESSION 001
        </span>

        <div className="flex items-center gap-6">

          <span>
            04 BLOCKS
          </span>

          <span>
            01 PAGE
          </span>

          <span className="text-emerald-400">
            03 VERIFIED
          </span>

          <span className="text-amber-400">
            01 REVIEW
          </span>

        </div>

      </footer>

    </div>
  );
}

export default App;