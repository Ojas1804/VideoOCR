import { createWorker, createScheduler } from 'tesseract.js';
import { readdirSync } from 'fs';
import { join } from 'path';

// Matches any Japanese character (hiragana, katakana, kanji, full-width)
const JAPANESE_RE = /[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\uff00-\uffef\u4e00-\u9faf\u3400-\u4dbf]/;

let _scheduler = null;

async function getScheduler(numWorkers = 2) {
  if (_scheduler) return _scheduler;
  _scheduler = createScheduler();
  const workers = await Promise.all(
    Array.from({ length: numWorkers }, () =>
      createWorker('jpn', 1, { logger: () => {} })
    )
  );
  for (const w of workers) _scheduler.addWorker(w);
  return _scheduler;
}

export async function terminateOCR() {
  if (_scheduler) {
    await _scheduler.terminate();
    _scheduler = null;
  }
}

/**
 * Run Tesseract OCR on a single frame image and return Japanese text detections.
 *
 * @param {string} imagePath
 * @param {number} frameNumber  1-based index (as written by ffmpeg)
 * @param {number} timestamp    Seconds into the video
 * @param {number} [confThreshold=0.3]  0–1 confidence cutoff
 * @returns {Promise<Array<{frame,timestamp,text,bbox,confidence}>>}
 */
export async function detectText(imagePath, frameNumber, timestamp, confThreshold = 0.3) {
  const sched = await getScheduler();
  const { data } = await sched.addJob('recognize', imagePath);

  const detections = [];
  for (const line of data.lines ?? []) {
    const text = line.text.trim().replace(/\s+/g, '');
    if (!text || !JAPANESE_RE.test(text)) continue;
    const conf = line.confidence / 100;   // Tesseract reports 0–100
    if (conf < confThreshold) continue;

    const { x0, y0, x1, y1 } = line.bbox;
    detections.push({
      frame:      frameNumber,
      timestamp,
      text,
      bbox:       [x0, y0, x1 - x0, y1 - y0],   // [x, y, w, h]
      confidence: Math.round(conf * 1000) / 1000,
    });
  }
  return detections;
}

/**
 * Process every JPEG frame in framesDir in order and return all detections.
 *
 * @param {string}   framesDir
 * @param {number}   [sampleFps=2]
 * @param {number}   [confThreshold=0.3]
 * @param {Function} [onFrame]  Called with (processed, total) after each frame
 * @returns {Promise<Array>}
 */
export async function processAllFrames(framesDir, sampleFps = 2, confThreshold = 0.3, onFrame = null) {
  const files = readdirSync(framesDir).filter(f => f.endsWith('.jpg')).sort();
  const total = files.length;

  // Pre-warm a pool of workers; cap at 4 to avoid memory pressure
  await getScheduler(Math.min(4, Math.max(1, Math.ceil(total / 20))));

  const all = [];
  for (let i = 0; i < files.length; i++) {
    const frameNumber = parseInt(files[i].replace('frame_', '').replace('.jpg', ''), 10);
    const timestamp   = (frameNumber - 1) / sampleFps;
    const dets = await detectText(join(framesDir, files[i]), frameNumber, timestamp, confThreshold);
    all.push(...dets);
    if (onFrame) onFrame(i + 1, total);
  }

  await terminateOCR();
  return all;
}
