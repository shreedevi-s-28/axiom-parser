import { useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent } from 'react';
import { DocumentViewer } from './components/DocumentViewer';
import { ExtractedBlockList } from './components/ExtractedBlockList';
import { AuditQueue } from './components/AuditQueue';
import { EconomicsHUD } from './components/EconomicsHUD';
import { ApiError, analyzeDocument, pageImageUrl } from './api/client';
import { validatePdfFile } from './utils/file';
import { needsReview } from './utils/coordinates';
import type { DocumentResult } from './types/document';

type Phase = 'idle' | 'analyzing' | 'done' | 'error';

interface DisplayError {
  title: string;
  message: string;
  code: string | null;
}

const pad = (value: number) => String(value).padStart(2, '0');

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<DocumentResult | null>(null);
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState<DisplayError | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null);
  const [hoveredBlockId, setHoveredBlockId] = useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Cancel any in-flight request when the app unmounts.
  useEffect(() => () => abortRef.current?.abort(), []);

  const blocks = useMemo(() => result?.blocks ?? [], [result]);

  const pageBlocks = useMemo(
    () => blocks.filter((block) => block.page === currentPage),
    [blocks, currentPage],
  );

  const pageSize =
    result?.pages.find((page) => page.page === currentPage) ?? null;

  // Only PDFs have server-rendered page previews (they come with page geometry).
  const imageUrl =
    result && result.pages.length > 0
      ? pageImageUrl(result.document_id, currentPage)
      : null;

  const flaggedCount = blocks.filter(needsReview).length;

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const chosen = event.target.files?.[0];
    // Reset so choosing the same file again still fires a change event.
    event.target.value = '';

    if (!chosen) return;

    const problem = validatePdfFile(chosen);
    if (problem) {
      setError({ title: 'Invalid file', message: problem, code: null });
      return;
    }

    abortRef.current?.abort();
    setFile(chosen);
    setResult(null);
    setPhase('idle');
    setError(null);
    setSelectedBlockId(null);
    setHoveredBlockId(null);
    setCurrentPage(1);
  };

  const handleAnalyze = async () => {
    if (!file) {
      setError({
        title: 'No file selected',
        message: 'Select a PDF before running the analysis.',
        code: null,
      });
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setPhase('analyzing');
    setError(null);
    setResult(null);
    setSelectedBlockId(null);
    setHoveredBlockId(null);
    setCurrentPage(1);

    try {
      const analysis = await analyzeDocument(file, controller.signal);
      if (abortRef.current !== controller) return;
      setResult(analysis);
      setPhase('done');
    } catch (caught) {
      if (abortRef.current !== controller) return;
      if (caught instanceof DOMException && caught.name === 'AbortError') return;

      if (caught instanceof ApiError) {
        setError({ title: caught.title, message: caught.message, code: caught.code });
      } else {
        setError({
          title: 'Unexpected error',
          message: caught instanceof Error ? caught.message : 'Something went wrong.',
          code: null,
        });
      }
      setPhase('error');
    }
  };

  const handleSelectBlock = (id: string) => {
    if (!id) {
      setSelectedBlockId(null);
      return;
    }
    setSelectedBlockId(id);
    const block = blocks.find((candidate) => candidate.id === id);
    if (block) setCurrentPage(block.page);
  };

  const handlePageChange = (page: number) => {
    if (!result) return;
    setCurrentPage(Math.min(Math.max(1, page), result.page_count));
  };

  const statusLabel =
    phase === 'analyzing'
      ? 'ANALYZING'
      : phase === 'error'
        ? 'ANALYSIS FAILED'
        : phase === 'done'
          ? 'ANALYSIS COMPLETE'
          : 'SYSTEM READY';

  const statusColor =
    phase === 'analyzing'
      ? 'text-amber-600'
      : phase === 'error'
        ? 'text-red-700'
        : 'text-emerald-700';

  const statusDot =
    phase === 'analyzing'
      ? 'bg-amber-500 animate-pulse'
      : phase === 'error'
        ? 'bg-red-600'
        : 'bg-emerald-600';

  const emptyState =
    phase === 'analyzing'
      ? {
          title: 'Analyzing document…',
          body: `Uploading "${file?.name ?? ''}" and running extraction on the backend.`,
        }
      : phase === 'error'
        ? {
            title: 'Analysis failed',
            body: 'See the message above. Select another PDF, or try this one again.',
          }
        : file
          ? {
              title: 'Ready to analyze',
              body: `"${file.name}" is selected. Choose Analyze to upload it and run extraction.`,
            }
          : {
              title: 'No document loaded',
              body: 'Select a PDF with the button in the top bar, then choose Analyze to extract its structure.',
            };

  const buttonClass =
    'h-8 px-3 border text-[10px] font-mono uppercase tracking-wider transition-colors disabled:opacity-40 disabled:cursor-not-allowed';

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

        <div className="flex items-center gap-5 text-[10px] font-mono">

          {/* FILE SELECTION */}
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,application/pdf"
            onChange={handleFileChange}
            className="hidden"
          />

          <span
            className="max-w-[220px] truncate text-stone-500"
            title={file?.name}
          >
            {file ? file.name : 'NO FILE SELECTED'}
          </span>

          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={phase === 'analyzing'}
            className={`${buttonClass} border-stone-300 bg-white text-stone-700 hover:bg-stone-100`}
          >
            Select PDF
          </button>

          <button
            type="button"
            onClick={handleAnalyze}
            disabled={!file || phase === 'analyzing'}
            className={`${buttonClass} border-slate-900 bg-slate-900 text-white hover:bg-slate-700`}
          >
            {phase === 'analyzing' ? 'Analyzing…' : 'Analyze'}
          </button>

          <span className={`flex items-center gap-2 ${statusColor}`}>
            <span className={`h-2 w-2 rounded-full ${statusDot}`} />
            {statusLabel}
          </span>

        </div>

      </header>


      {/* ERROR BANNER */}
      {error && (
        <div
          role="alert"
          className="shrink-0 bg-orange-50 border-b border-orange-300 px-6 py-2.5 flex items-start justify-between gap-6"
        >
          <p className="text-[11px] leading-relaxed text-orange-900">
            <span className="font-semibold">{error.title}.</span>{' '}
            {error.message}
            {error.code && (
              <span className="ml-2 font-mono text-[9px] text-orange-700">
                {error.code}
              </span>
            )}
          </p>

          <button
            type="button"
            onClick={() => setError(null)}
            className="shrink-0 text-[10px] font-mono uppercase tracking-wider text-orange-800 hover:text-orange-950"
          >
            Dismiss
          </button>
        </div>
      )}


      {/* MAIN WORKSPACE */}
      <div className="flex-1 min-h-0 flex">

        {/* LEFT — DOCUMENT STRUCTURE */}
        <aside className="w-[230px] shrink-0 bg-[#242424] border-r border-stone-700 overflow-hidden">

          <ExtractedBlockList
            blocks={blocks}
            selectedBlockId={selectedBlockId}
            hoveredBlockId={hoveredBlockId}
            onSelectBlock={handleSelectBlock}
            onHoverBlock={setHoveredBlockId}
          />

        </aside>


        {/* CENTER — DOCUMENT */}
        <main className="flex-1 min-w-0 min-h-0 bg-[#e9e5dd] overflow-hidden">

          <DocumentViewer
            filename={result?.filename ?? null}
            pageNumber={currentPage}
            pageCount={result?.page_count ?? 0}
            pageSize={pageSize}
            imageUrl={imageUrl}
            emptyTitle={emptyState.title}
            emptyBody={emptyState.body}
            blocks={pageBlocks}
            selectedBlockId={selectedBlockId}
            hoveredBlockId={hoveredBlockId}
            onSelectBlock={handleSelectBlock}
            onHoverBlock={setHoveredBlockId}
            onPageChange={handlePageChange}
          />

        </main>


        {/* RIGHT — INSPECTION */}
        <aside className="w-[280px] shrink-0 bg-[#fbfaf7] border-l border-stone-300 overflow-y-auto">

          <div className="p-5">

            <EconomicsHUD
              pagesProcessed={result ? result.page_count : null}
              totalPages={result ? result.page_count : null}
              estimatedCost={result ? result.metrics.estimated_cost_usd : null}
              processingTime={result ? result.metrics.processing_time_ms / 1000 : null}
            />

            <div className="pt-5">

              <AuditQueue
                blocks={blocks}
                selectedBlockId={selectedBlockId}
                onSelectBlock={handleSelectBlock}
              />

            </div>

          </div>

        </aside>

      </div>


      {/* BOTTOM STATUS BAR */}
      <footer className="h-8 shrink-0 bg-slate-900 text-slate-300 px-6 flex items-center justify-between text-[9px] font-mono">

        <span>
          {result
            ? `AXIOMPARSE / ${result.document_id.toUpperCase()}`
            : 'AXIOMPARSE / NO ACTIVE SESSION'}
        </span>

        <div className="flex items-center gap-6">

          <span>
            {pad(blocks.length)} BLOCKS
          </span>

          <span>
            {pad(result?.page_count ?? 0)} {result?.page_count === 1 ? 'PAGE' : 'PAGES'}
          </span>

          <span className="text-emerald-400">
            {pad(blocks.length - flaggedCount)} UNFLAGGED
          </span>

          <span className="text-amber-400">
            {pad(flaggedCount)} REVIEW
          </span>

        </div>

      </footer>

    </div>
  );
}

export default App;
