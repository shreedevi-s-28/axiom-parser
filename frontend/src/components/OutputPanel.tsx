import React, { useEffect, useMemo, useRef, useState } from 'react';
import type { DocumentResult } from '../types/document';

export type OutputFormat = 'markdown' | 'json';

interface OutputPanelProps {
  result: DocumentResult | null;
  format: OutputFormat;
  onFormatChange: (format: OutputFormat) => void;
}

const baseName = (filename: string) => filename.replace(/\.[^.]+$/, '') || 'document';

export const OutputPanel: React.FC<OutputPanelProps> = ({ result, format, onFormatChange }) => {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => () => {
    if (timer.current !== null) window.clearTimeout(timer.current);
  }, []);

  const text = useMemo(() => {
    if (!result) return '';
    return format === 'json' ? JSON.stringify(result, null, 2) : result.markdown;
  }, [result, format]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Fallback for non-secure contexts where the Clipboard API is unavailable.
      const area = document.createElement('textarea');
      area.value = text;
      document.body.appendChild(area);
      area.select();
      document.execCommand('copy');
      document.body.removeChild(area);
    }
    setCopied(true);
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setCopied(false), 1500);
  };

  const handleDownload = () => {
    if (!result) return;
    const isJson = format === 'json';
    const blob = new Blob([text], { type: isJson ? 'application/json' : 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${baseName(result.filename)}.${isJson ? 'json' : 'md'}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const tab = (value: OutputFormat, label: string) => (
    <button
      type="button"
      onClick={() => onFormatChange(value)}
      className={`h-7 px-3 text-[10px] font-mono uppercase tracking-wider border transition-colors ${
        format === value
          ? 'bg-slate-900 text-white border-slate-900'
          : 'bg-white text-stone-600 border-stone-300 hover:bg-stone-100'
      }`}
    >
      {label}
    </button>
  );

  const actionClass =
    'h-7 px-3 text-[10px] font-mono uppercase tracking-wider border border-stone-300 bg-white text-stone-700 hover:bg-stone-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed';

  return (
    <div className="h-full w-full bg-[#f7f5f0] flex flex-col">
      <div className="h-14 shrink-0 border-b border-stone-300 px-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {tab('markdown', 'Markdown')}
          {tab('json', 'JSON')}
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={handleCopy} disabled={!result} className={actionClass}>
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button type="button" onClick={handleDownload} disabled={!result} className={actionClass}>
            Download .{format === 'json' ? 'json' : 'md'}
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto p-6">
        {result ? (
          text.trim() ? (
            <pre className="text-[12px] leading-relaxed font-mono text-slate-800 whitespace-pre-wrap break-words bg-white border border-stone-300 p-5">
              {text}
            </pre>
          ) : (
            <p className="text-xs text-stone-500">The analysis produced no Markdown content.</p>
          )
        ) : (
          <div className="h-full flex items-center justify-center text-center">
            <p className="max-w-sm text-xs leading-relaxed text-stone-500">
              Analyze a PDF to see its Markdown and JSON output here.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
