import React, { useState } from 'react';

interface DocumentPageLayerProps {
  /** Server-rendered image of the real page; null when no preview exists (non-PDF files). */
  imageUrl: string | null;
  pageNumber: number;
}

/**
 * The page itself. Renders the actual page of the uploaded PDF. Remount it (via `key`)
 * when the image URL changes so the load state resets.
 */
export const DocumentPageLayer: React.FC<DocumentPageLayerProps> = ({
  imageUrl,
  pageNumber,
}) => {
  const [status, setStatus] = useState<'loading' | 'ready' | 'failed'>('loading');

  if (!imageUrl) {
    return (
      <div className="absolute inset-0 flex items-center justify-center bg-[#fffefa] pointer-events-none select-none">
        <p className="text-[10px] font-mono uppercase tracking-wider text-stone-400">
          No page preview for this file type
        </p>
      </div>
    );
  }

  return (
    <div className="absolute inset-0 bg-[#fffefa] pointer-events-none select-none">
      <img
        src={imageUrl}
        alt={`Page ${pageNumber} of the uploaded document`}
        draggable={false}
        onLoad={() => setStatus('ready')}
        onError={() => setStatus('failed')}
        className={`h-full w-full object-fill ${status === 'ready' ? '' : 'invisible'}`}
      />

      {status !== 'ready' && (
        <div className="absolute inset-0 flex items-center justify-center">
          <p className="text-[10px] font-mono uppercase tracking-wider text-stone-400">
            {status === 'loading'
              ? 'Rendering page…'
              : 'Page preview unavailable. The stored copy may have expired.'}
          </p>
        </div>
      )}
    </div>
  );
};
