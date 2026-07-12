import { mkdtempSync, rmSync, writeFileSync, readFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

import { getVideoInfo, extractFrames } from './frameExtractor.js';
import { processAllFrames } from './textDetector.js';
import { trackAndGroup } from './tracker.js';
import { translateTexts } from './translator.js';

const DISPLAY_PADDING_PX = 10;

function buildMetadata(tracks, translations) {
  const output = [];
  let id = 1;
  for (const track of tracks) {
    const english   = translations[track.text] ?? track.text;
    const positions = track.keyframes.map(kf => {
      const [x, y, , h] = kf.bbox;
      return { t: kf.t, x, y: y + h + DISPLAY_PADDING_PX };
    });
    output.push({
      id,
      japanese:   track.text,
      english,
      start_time: track.startTime,
      end_time:   track.endTime,
      positions,
    });
    id++;
  }
  return output;
}

/**
 * Run the full preprocessing pipeline.
 *
 * @param {object}   opts
 * @param {string}   opts.videoPath
 * @param {number}   [opts.sampleFps=2]
 * @param {number}   [opts.detConf=0.5]         unused (Tesseract has no separate det step)
 * @param {number}   [opts.ocrConf=0.3]
 * @param {number}   [opts.trackDist=60]
 * @param {number}   [opts.minDetections=2]
 * @param {string}   [opts.ocrOutput='ocr_raw.json']
 * @param {string}   [opts.outputPath='translation_metadata.json']
 * @param {boolean}  [opts.skipOcr=false]
 * @param {string}   [opts.translateApiKey='']
 * @param {Function} [onEvent]                   progress event callback
 * @returns {Promise<Array>}
 */
export async function runPipeline(opts, onEvent = () => {}) {
  const {
    videoPath,
    sampleFps       = 2,
    ocrConf         = 0.3,
    trackDist       = 60,
    minDetections   = 2,
    ocrOutput       = 'ocr_raw.json',
    outputPath      = 'translation_metadata.json',
    skipOcr         = false,
    translateApiKey = '',
  } = opts;

  let ocrResults;

  // ── Step 1: Extract frames + OCR ─────────────────────────────────────────
  if (skipOcr) {
    ocrResults = JSON.parse(readFileSync(ocrOutput, 'utf8'));
  } else {
    onEvent({ type: 'step', step_num: 1, total_steps: 4, name: 'Extract & OCR' });

    const info = await getVideoInfo(videoPath);
    console.log(
      `[video] ${info.width}x${info.height}, ${info.fps.toFixed(2)} fps, ` +
      `${info.duration.toFixed(1)}s — sampling at ${sampleFps} fps`
    );

    const framesDir = mkdtempSync(join(tmpdir(), 'videocr-'));
    try {
      await extractFrames(videoPath, framesDir, sampleFps);
      ocrResults = await processAllFrames(
        framesDir,
        sampleFps,
        ocrConf,
        (done, total) => onEvent({ type: 'ocr_progress', current: done, total }),
      );
    } finally {
      rmSync(framesDir, { recursive: true, force: true });
    }

    writeFileSync(ocrOutput, JSON.stringify(ocrResults, null, 2), 'utf8');
    console.log(`[ocr] ${ocrResults.length} detections → ${ocrOutput}`);
  }

  // ── Step 2: Track ─────────────────────────────────────────────────────────
  onEvent({ type: 'step', step_num: 2, total_steps: 4, name: 'Track' });
  const tracks = trackAndGroup(ocrResults, trackDist, minDetections);
  console.log(`[track] ${tracks.length} stable segment(s)`);

  // ── Step 3: Translate ──────────────────────────────────────────────────────
  onEvent({ type: 'step', step_num: 3, total_steps: 4, name: 'Translate' });
  const uniqueTexts  = [...new Set(tracks.map(t => t.text))];
  const translations = await translateTexts(uniqueTexts, {
    apiKey: translateApiKey,
    onItem: (ja, en, current, total) =>
      onEvent({ type: 'translation', japanese: ja, english: en, current, total }),
  });

  // ── Step 4: Build metadata ─────────────────────────────────────────────────
  onEvent({ type: 'step', step_num: 4, total_steps: 4, name: 'Metadata' });
  const metadata = buildMetadata(tracks, translations);
  writeFileSync(outputPath, JSON.stringify(metadata, null, 2), 'utf8');
  console.log(`[meta] ${metadata.length} entr${metadata.length === 1 ? 'y' : 'ies'} → ${outputPath}`);

  onEvent({ type: 'done', count: metadata.length });
  return metadata;
}
