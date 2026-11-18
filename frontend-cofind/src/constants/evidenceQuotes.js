/** Selaras dengan recommendation/quote_snippet.py MODAL_QUOTE_CHAR_LIMIT */
export const MODAL_QUOTE_MAX_CHARS = 280;

export function formatModalQuote(text, max = MODAL_QUOTE_MAX_CHARS) {
  const cleaned = String(text ?? '').trim().replace(/\s+/g, ' ');
  if (!cleaned) return '';
  if (cleaned.length <= max) return cleaned;
  return `${cleaned.slice(0, max - 1).trimEnd()}…`;
}

export function quoteWasTruncated(text, max = MODAL_QUOTE_MAX_CHARS) {
  const cleaned = String(text ?? '').trim().replace(/\s+/g, ' ');
  return cleaned.length > max;
}