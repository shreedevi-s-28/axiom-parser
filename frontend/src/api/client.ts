import type { DocumentResult, RFC7807Error } from '../types/document';

export const API_BASE_URL: string = (
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
).replace(/\/+$/, '');

/** A failure the UI can show verbatim: a short title plus an explanation. */
export class ApiError extends Error {
  title: string;
  code: string | null;
  status: number | null;

  constructor(title: string, detail: string, code: string | null = null, status: number | null = null) {
    super(detail);
    this.name = 'ApiError';
    this.title = title;
    this.code = code;
    this.status = status;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isProblem(value: unknown): value is RFC7807Error {
  return (
    isRecord(value) &&
    typeof value.title === 'string' &&
    typeof value.detail === 'string'
  );
}

/** Minimal structural check so a malformed response never reaches the components. */
function isDocumentResult(value: unknown): value is DocumentResult {
  if (!isRecord(value)) return false;
  const metrics = value.metrics;
  return (
    typeof value.document_id === 'string' &&
    typeof value.filename === 'string' &&
    typeof value.page_count === 'number' &&
    Array.isArray(value.blocks) &&
    isRecord(metrics) &&
    typeof metrics.processing_time_ms === 'number' &&
    typeof metrics.estimated_cost_usd === 'number' &&
    value.blocks.every(
      (block) =>
        isRecord(block) &&
        typeof block.id === 'string' &&
        typeof block.page === 'number' &&
        typeof block.text === 'string' &&
        isRecord(block.bbox),
    )
  );
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}

/** Uploads the selected PDF to the backend and returns the real analysis. */
export async function analyzeDocument(
  file: File,
  signal?: AbortSignal,
): Promise<DocumentResult> {
  const form = new FormData();
  form.append('file', file, file.name);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/parse`, {
      method: 'POST',
      body: form,
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(
      'Backend unavailable',
      `Could not reach the AxiomParse backend at ${API_BASE_URL}. Make sure it is running and that this origin is allowed by its CORS settings.`,
    );
  }

  const body = await readJson(response);

  if (!response.ok) {
    // Backend errors arrive as { detail: <RFC 7807 problem> }.
    const problem = isRecord(body) ? body.detail : undefined;
    if (isProblem(problem)) {
      throw new ApiError(problem.title, problem.detail, problem.error_code ?? null, response.status);
    }
    if (isRecord(body) && typeof body.detail === 'string') {
      throw new ApiError(`Request failed (${response.status})`, body.detail, null, response.status);
    }
    throw new ApiError(
      `Request failed (${response.status})`,
      response.statusText || 'The backend returned an error without details.',
      null,
      response.status,
    );
  }

  if (!isDocumentResult(body)) {
    throw new ApiError(
      'Unexpected response',
      'The backend responded successfully but the data is not a valid analysis result.',
    );
  }

  return body;
}

/** URL of the server-rendered preview of one page of an analysed PDF. */
export function pageImageUrl(documentId: string, page: number): string {
  return `${API_BASE_URL}/api/v1/documents/${encodeURIComponent(documentId)}/pages/${page}/image`;
}
