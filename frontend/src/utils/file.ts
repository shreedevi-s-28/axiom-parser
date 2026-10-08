export const MAX_UPLOAD_MB = 50;

export const SUPPORTED_EXTENSIONS = [
  '.pdf',
  '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.heic', '.heif',
  '.docx', '.pptx', '.xlsx', '.xls', '.csv',
  '.txt', '.md', '.markdown', '.html', '.htm', '.rtf',
  '.eml', '.msg',
] as const;

const ACCEPT_ATTR = [
  '.pdf,application/pdf',
  '.png,.jpg,.jpeg,.tiff,.tif,.heic,image/*',
  '.docx,.pptx,.xlsx,.xls,.csv',
  '.txt,.md,.markdown,.html,.htm,.rtf,text/*',
  '.eml,.msg',
].join(',');

export function fileAcceptAttribute(): string {
  return ACCEPT_ATTR;
}

function extensionOf(name: string): string {
  const i = name.lastIndexOf('.');
  return i >= 0 ? name.slice(i).toLowerCase() : '';
}

export function validateUploadFile(file: File): string | null {
  const ext = extensionOf(file.name);
  if (!SUPPORTED_EXTENSIONS.includes(ext as (typeof SUPPORTED_EXTENSIONS)[number])) {
    return `"${file.name}" is not a supported type. Use PDF, DOCX, PPTX, XLSX, CSV, images, TXT, MD, HTML, RTF, EML, or MSG.`;
  }
  if (file.size === 0) {
    return `"${file.name}" is empty (0 bytes).`;
  }
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    return `"${file.name}" is larger than the ${MAX_UPLOAD_MB} MB limit.`;
  }
  return null;
}

export function validatePdfFile(file: File): string | null {
  return validateUploadFile(file);
}
