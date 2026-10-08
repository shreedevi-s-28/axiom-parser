export const MAX_UPLOAD_MB = 50;

/** Client-side pre-check; the backend validates again authoritatively. Returns an error message or null. */
export function validatePdfFile(file: File): string | null {
  const looksLikePdf =
    file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
  if (!looksLikePdf) {
    return `"${file.name}" is not a PDF. Choose a file ending in .pdf.`;
  }
  if (file.size === 0) {
    return `"${file.name}" is empty (0 bytes).`;
  }
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    return `"${file.name}" is larger than the ${MAX_UPLOAD_MB} MB limit.`;
  }
  return null;
}
