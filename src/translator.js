/**
 * Translation via the MyMemory public API (free, no API key required).
 * With a free key from https://mymemory.translated.net you get 10 000 words/day.
 */

const MYMEMORY_URL  = 'https://api.mymemory.translated.net/get';
const DEFAULT_DELAY = 600; // ms between requests — stays under rate limits

async function translateOne(text, apiKey = '') {
  const qs = new URLSearchParams({ q: text, langpair: 'ja|en' });
  if (apiKey) qs.set('key', apiKey);

  const res = await fetch(`${MYMEMORY_URL}?${qs}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);

  const json = await res.json();
  if (json.responseStatus !== 200) {
    throw new Error(`MyMemory: ${json.responseDetails ?? 'unknown error'}`);
  }
  return json.responseData.translatedText;
}

/**
 * Translate an array of Japanese strings to English.
 * Deduplicates inputs and rate-limits requests.
 *
 * @param {string[]} texts
 * @param {object}   [opts]
 * @param {string}   [opts.apiKey='']       Optional MyMemory API key
 * @param {number}   [opts.delayMs=600]     Milliseconds between requests
 * @param {Function} [opts.onItem]          (ja, en, current, total) progress callback
 * @returns {Promise<Record<string, string>>}  { japanese → english }
 */
export async function translateTexts(texts, { apiKey = '', delayMs = DEFAULT_DELAY, onItem = null } = {}) {
  const unique = [...new Set(texts.map(t => t.trim()).filter(Boolean))];
  if (!unique.length) return {};

  const map = Object.create(null);
  for (let i = 0; i < unique.length; i++) {
    const src = unique[i];
    try {
      map[src] = await translateOne(src, apiKey);
    } catch {
      map[src] = src;   // graceful fallback: keep original on failure
    }
    if (onItem) onItem(src, map[src], i + 1, unique.length);
    if (i < unique.length - 1) await new Promise(r => setTimeout(r, delayMs));
  }
  return map;
}
