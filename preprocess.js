#!/usr/bin/env node
/**
 * VideoOCR CLI — preprocess a video into translation_metadata.json
 *
 * Usage:
 *   node preprocess.js <video> [options]
 */
import { program } from 'commander';
import { createRequire } from 'module';
import { SingleBar, Presets } from 'cli-progress';
import { runPipeline } from './src/pipeline.js';

const require  = createRequire(import.meta.url);
const { version } = require('./package.json');

program
  .name('preprocess')
  .description('Tesseract.js-based Japanese video OCR and translation')
  .version(version)
  .argument('<video>', 'Path to the input video file')
  .option('--sample-fps <n>',     'Frames per second to sample',          parseFloat, 2.0)
  .option('--ocr-conf <n>',       'Minimum OCR confidence (0–1)',         parseFloat, 0.3)
  .option('--track-dist <n>',     'Centroid distance threshold (px)',      parseFloat, 60)
  .option('--min-detections <n>', 'Min frames for a stable text segment',  parseInt,   2)
  .option('--ocr-output <path>',  'Intermediate raw-OCR JSON path',       'ocr_raw.json')
  .option('--output <path>',      'Final metadata JSON path',             'translation_metadata.json')
  .option('--skip-ocr',           'Skip frame extraction; load existing --ocr-output')
  .option('--api-key <key>',      'MyMemory API key for higher daily limits', '')
  .parse();

const opts      = program.opts();
const [videoPath] = program.args;

console.log(`\nVideoOCR  ·  ${videoPath}\n`);

let ocrBar = null;

function onEvent(ev) {
  switch (ev.type) {
    case 'step':
      if (ocrBar) { ocrBar.stop(); ocrBar = null; }
      console.log(`\n[${ev.step_num}/${ev.total_steps}] ${ev.name}`);
      break;

    case 'ocr_progress':
      if (!ocrBar) {
        ocrBar = new SingleBar(
          { format: '  OCR |{bar}| {value}/{total} frames', clearOnComplete: false },
          Presets.shades_classic
        );
        ocrBar.start(ev.total, 0);
      }
      ocrBar.update(ev.current);
      break;

    case 'translation':
      process.stdout.write(`  ${ev.japanese}  →  ${ev.english}  (${ev.current}/${ev.total})\n`);
      break;

    case 'done':
      console.log(`\nDone — ${ev.count} translation entr${ev.count === 1 ? 'y' : 'ies'} written.\n`);
      break;

    case 'error':
      console.error(`\nError: ${ev.message}\n`);
      process.exit(1);
  }
}

try {
  await runPipeline({
    videoPath,
    sampleFps:       opts.sampleFps,
    ocrConf:         opts.ocrConf,
    trackDist:       opts.trackDist,
    minDetections:   opts.minDetections,
    ocrOutput:       opts.ocrOutput,
    outputPath:      opts.output,
    skipOcr:         opts.skipOcr ?? false,
    translateApiKey: opts.apiKey,
  }, onEvent);
} catch (err) {
  if (ocrBar) ocrBar.stop();
  console.error(`\nFatal: ${err.message}\n`);
  process.exit(1);
}
