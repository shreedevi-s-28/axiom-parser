import React from 'react';

interface EconomicsHUDProps {
  pagesProcessed: number;
  totalPages: number;
  estimatedCost: number;
  processingTime: number;
}

export const EconomicsHUD: React.FC<EconomicsHUDProps> = ({
  pagesProcessed,
  totalPages,
  estimatedCost,
  processingTime,
}) => {
  const progress =
    totalPages > 0
      ? Math.round((pagesProcessed / totalPages) * 100)
      : 0;

  return (
    <section className="border-b border-stone-300 pb-5">
      
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-[9px] uppercase tracking-[0.2em] text-stone-500">
            Processing Record
          </p>

          <h3 className="font-serif text-lg text-stone-800 mt-1">
            Extraction
          </h3>
        </div>

        <span className="text-xs font-mono text-stone-600">
          {progress}%
        </span>
      </div>

      {/* PROGRESS */}
      <div className="h-1 bg-stone-200 mb-5">
        <div
          className="h-full bg-slate-700 transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* METRICS */}
      <div className="space-y-3">

        <div className="flex items-center justify-between">
          <span className="text-[10px] uppercase tracking-wider text-stone-500">
            Pages processed
          </span>

          <span className="text-[11px] font-mono text-stone-800">
            {pagesProcessed} / {totalPages}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-[10px] uppercase tracking-wider text-stone-500">
            Processing time
          </span>

          <span className="text-[11px] font-mono text-stone-800">
            {processingTime.toFixed(1)}s
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-[10px] uppercase tracking-wider text-stone-500">
            Estimated cost
          </span>

          <span className="text-[11px] font-mono text-stone-800">
            ${estimatedCost.toFixed(4)}
          </span>
        </div>

      </div>
    </section>
  );
};