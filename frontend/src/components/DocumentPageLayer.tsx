import React from 'react';

interface DocumentPageLayerProps {
  filename: string;
  pageNumber: number;
}

export const DocumentPageLayer: React.FC<DocumentPageLayerProps> = ({
  filename,
  pageNumber,
}) => {
  return (
    <div className="w-full min-h-[1000px] bg-[#fffefa] text-stone-800 px-16 py-14 font-serif pointer-events-none select-none">

      {/* DOCUMENT HEADER */}
      <div className="flex items-start justify-between border-b-2 border-stone-800 pb-4">

        <div>
          <p className="text-[9px] uppercase tracking-[0.2em] text-stone-500 font-sans mb-2">
            Annual Financial Report
          </p>

          <h1 className="text-3xl font-semibold tracking-tight text-stone-900">
            Executive Financial Summary
          </h1>
        </div>

        <div className="text-right">
          <p className="text-[9px] uppercase tracking-wider text-stone-400 font-sans">
            Source
          </p>

          <p className="text-[10px] font-mono text-stone-500 mt-1">
            {filename}
          </p>

          <p className="text-[10px] font-mono text-stone-500">
            PAGE {String(pageNumber).padStart(2, '0')}
          </p>
        </div>

      </div>

      {/* INTRODUCTION */}
      <div className="mt-10 max-w-[720px]">

        <p className="text-[10px] uppercase tracking-[0.18em] text-stone-400 font-sans mb-3">
          01 / Capital Structure
        </p>

        <p className="text-sm leading-7 text-stone-700">
          The following review reflects our consolidated debt obligations
          and capital structure maturities.
        </p>

      </div>

      {/* FINANCIAL TABLE */}
      <div className="mt-10">

        <div className="flex items-end justify-between mb-3">
          <h2 className="text-base font-semibold text-stone-900">
            Debt Obligations
          </h2>

          <span className="text-[9px] uppercase tracking-wider text-stone-400 font-sans">
            USD millions
          </span>
        </div>

        <table className="w-full border-collapse text-left text-xs font-sans">

          <thead>
            <tr className="border-y border-stone-800">
              <th className="py-3 pr-4 font-semibold text-stone-800">
                Tranche
              </th>

              <th className="py-3 px-4 font-semibold text-stone-800 text-right">
                Principal ($M)
              </th>

              <th className="py-3 pl-4 font-semibold text-stone-800 text-right">
                Rate
              </th>
            </tr>
          </thead>

          <tbody>

            <tr className="border-b border-stone-300">
              <td className="py-4 pr-4 font-medium text-stone-800">
                Term Loan B
              </td>

              <td className="py-4 px-4 text-right font-mono text-stone-700">
                620.0
              </td>

              <td className="py-4 pl-4 text-right font-mono text-stone-700">
                SOFR + 2.50%
              </td>
            </tr>

            <tr className="border-b border-stone-300">
              <td className="py-4 pr-4 font-medium text-stone-800">
                Senior Notes
              </td>

              <td className="py-4 px-4 text-right font-mono text-stone-700">
                400.0
              </td>

              <td className="py-4 pl-4 text-right font-mono text-stone-700">
                5.875%
              </td>
            </tr>

          </tbody>

        </table>

      </div>

      {/* BODY TEXT */}
      <div className="mt-12 max-w-[720px] space-y-5 text-sm leading-7 text-stone-700">

        <p>
          Consolidated financing arrangements remain within the
          established reporting framework. Maturity schedules and
          applicable interest rates are presented above for reference.
        </p>

        <p>
          The reported figures should be considered alongside the
          accompanying notes and supporting financial disclosures.
        </p>

      </div>

      {/* NOTE */}
      <div className="mt-16 border-t border-stone-300 pt-4 max-w-[720px]">

        <p className="text-[9px] uppercase tracking-[0.16em] text-stone-400 font-sans mb-2">
          Note 4
        </p>

        <p className="text-[10px] leading-5 text-stone-500 font-sans">
          Excludes $12.5M deferred financing costs amortized over
          facility tenure.
        </p>

      </div>

      {/* DOCUMENT FOOTER */}
      <div className="mt-24 pt-4 border-t border-stone-300 flex items-center justify-between">

        <span className="text-[9px] font-mono text-stone-400">
          CONFIDENTIAL — INTERNAL REVIEW
        </span>

        <span className="text-[9px] font-mono text-stone-400">
          {pageNumber}
        </span>

      </div>

    </div>
  );
};