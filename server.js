/**
 * VideoOCR HTTP server
 *
 * Serves the frontend, accepts video uploads, and runs the preprocessing
 * pipeline in a worker thread — streaming progress to the browser via SSE.
 *
 * Usage:
 *   node server.js [--host 0.0.0.0] [--port 3000]
 */
import express from 'express';
import multer from 'multer';
import { createRequire } from 'module';
import { Worker } from 'worker_threads';
import { randomUUID } from 'crypto';
import { parseArgs } from 'util';
import { fileURLToPath } from 'url';
import { mkdirSync, mkdtempSync, readFileSync, readdirSync } from 'fs';
import { join, dirname } from 'path';
import { tmpdir } from 'os';

const __dirname = dirname(fileURLToPath(import.meta.url));

const ALLOWED_EXTS = new Set(['.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.m4v']);
const WORK_DIR     = mkdtempSync(join(tmpdir(), 'videocr-srv-'));

// job registry: jobId → { dir, events[], listeners Set }
const jobs = new Map();

// ── Express app ───────────────────────────────────────────────────────────────
const app = express();
app.use(express.static(join(__dirname, 'player')));

// ── Multer storage ────────────────────────────────────────────────────────────
const storage = multer.diskStorage({
  destination: (req, _file, cb) => cb(null, req.jobDir),
  filename:    (_req, file, cb) => {
    const ext = file.originalname.slice(file.originalname.lastIndexOf('.')).toLowerCase();
    cb(null, `video${ext}`);
  },
});

const upload = multer({
  storage,
  limits: { fileSize: 5 * 1024 * 1024 * 1024 },  // 5 GB
  fileFilter: (_req, file, cb) => {
    const ext = file.originalname.slice(file.originalname.lastIndexOf('.')).toLowerCase();
    if (ALLOWED_EXTS.has(ext)) cb(null, true);
    else cb(new Error(`Unsupported file type: ${ext}`));
  },
});

// Middleware: allocate a job ID and directory before multer saves the file
function allocateJob(req, res, next) {
  const jobId  = randomUUID();
  const jobDir = join(WORK_DIR, jobId);
  mkdirSync(jobDir, { recursive: true });
  req.jobId  = jobId;
  req.jobDir = jobDir;
  next();
}

// ── POST /api/preprocess ──────────────────────────────────────────────────────
app.post('/api/preprocess', allocateJob, upload.single('video'), (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'No video file or unsupported format' });

  const { jobId, jobDir } = req;
  jobs.set(jobId, { dir: jobDir, events: [], listeners: new Set() });

  const workerOpts = {
    videoPath:     req.file.path,
    sampleFps:     parseFloat(req.body.sample_fps ?? 2),
    ocrConf:       parseFloat(req.body.ocr_conf   ?? 0.3),
    trackDist:     60,
    minDetections: 2,
    ocrOutput:     join(jobDir, 'ocr_raw.json'),
    outputPath:    join(jobDir, 'translation_metadata.json'),
  };

  const worker = new Worker(join(__dirname, 'src', 'pipelineWorker.js'), {
    workerData: workerOpts,
  });

  function broadcast(event) {
    const job = jobs.get(jobId);
    if (!job) return;
    job.events.push(event);
    for (const fn of job.listeners) fn(event);
  }

  worker.on('message', broadcast);
  worker.on('error',   err  => broadcast({ type: 'error', message: err.message }));
  worker.on('exit',    code => {
    if (code !== 0) broadcast({ type: 'error', message: `Worker exited with code ${code}` });
  });

  res.json({ job_id: jobId });
});

// ── GET /api/progress/:jobId  (Server-Sent Events) ───────────────────────────
app.get('/api/progress/:jobId', (req, res) => {
  const job = jobs.get(req.params.jobId);
  if (!job) return res.status(404).json({ error: 'Unknown job' });

  res.setHeader('Content-Type',      'text/event-stream');
  res.setHeader('Cache-Control',     'no-cache');
  res.setHeader('Connection',        'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');
  res.flushHeaders();

  // Replay events that arrived before this SSE connection opened
  for (const ev of job.events) res.write(`data: ${JSON.stringify(ev)}\n\n`);

  const listener = ev => res.write(`data: ${JSON.stringify(ev)}\n\n`);
  job.listeners.add(listener);
  req.on('close', () => job.listeners.delete(listener));
});

// ── GET /api/metadata/:jobId ──────────────────────────────────────────────────
app.get('/api/metadata/:jobId', (req, res) => {
  const job = jobs.get(req.params.jobId);
  if (!job) return res.status(404).json({ error: 'Job not found' });
  try {
    const data = readFileSync(join(job.dir, 'translation_metadata.json'), 'utf8');
    res.type('application/json').send(data);
  } catch {
    res.status(404).json({ error: 'Metadata not ready yet' });
  }
});

// ── GET /api/video/:jobId ─────────────────────────────────────────────────────
app.get('/api/video/:jobId', (req, res) => {
  const job = jobs.get(req.params.jobId);
  if (!job) return res.status(404).json({ error: 'Job not found' });
  try {
    const file = readdirSync(job.dir).find(f => f.startsWith('video'));
    if (!file) return res.status(404).json({ error: 'Video not found' });
    res.sendFile(join(job.dir, file));
  } catch {
    res.status(500).json({ error: 'Internal error' });
  }
});

// ── Multer error handler ──────────────────────────────────────────────────────
app.use((err, _req, res, _next) => {
  if (err?.code === 'LIMIT_FILE_SIZE') return res.status(413).json({ error: 'File too large (max 5 GB)' });
  res.status(400).json({ error: err.message ?? 'Bad request' });
});

// ── Start ─────────────────────────────────────────────────────────────────────
const { values: cliArgs } = parseArgs({
  options: {
    host: { type: 'string', default: '127.0.0.1' },
    port: { type: 'string', default: '3000' },
  },
  strict: false,
});

const PORT = parseInt(cliArgs.port, 10);
const HOST = cliArgs.host;

app.listen(PORT, HOST, () => {
  console.log(`VideoOCR server → http://${HOST}:${PORT}`);
});
