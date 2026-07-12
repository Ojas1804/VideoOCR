'use strict';

// ── DOM references ────────────────────────────────────────────────────────────
const video         = document.getElementById('video');
const canvas        = document.getElementById('overlay');
const ctx           = canvas.getContext('2d');
const wrapper       = document.getElementById('player-wrapper');
const statusTime    = document.getElementById('status-time');
const statusActive  = document.getElementById('status-active');
const videoFilename = document.getElementById('video-filename');
const metaFilename  = document.getElementById('meta-filename');

let metadata       = [];
let animationId    = null;

// ── Overlay rendering constants ───────────────────────────────────────────────
const FONT_SIZE      = 16;          // px
const FONT_FAMILY    = 'system-ui, -apple-system, "Segoe UI", sans-serif';
const PAD_X          = 8;           // horizontal padding inside label
const PAD_Y          = 5;           // vertical padding inside label
const CORNER_RADIUS  = 5;           // px
const BG_COLOR       = 'rgba(0, 0, 0, 0.72)';
const TEXT_COLOR     = '#ffffff';
const OUTLINE_COLOR  = 'rgba(255,255,255,0.12)';

// ── File loading ──────────────────────────────────────────────────────────────

document.getElementById('video-input').addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;

  // Revoke any previous object URL to free memory
  if (video.src) URL.revokeObjectURL(video.src);

  video.src = URL.createObjectURL(file);
  videoFilename.textContent = file.name;
  wrapper.classList.add('has-video');
});

document.getElementById('meta-input').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  try {
    const text = await file.text();
    metadata = JSON.parse(text);
    metaFilename.textContent = `${file.name} — ${metadata.length} entr${metadata.length === 1 ? 'y' : 'ies'}`;
    // Re-render in case the video is paused
    renderCurrentFrame();
  } catch {
    metaFilename.textContent = 'Error: invalid JSON';
    metadata = [];
  }
});

// ── Canvas sizing ─────────────────────────────────────────────────────────────

/**
 * Keep the canvas pixel dimensions in sync with the video's displayed size.
 * Called on load, resize, and fullscreen changes.
 */
function syncCanvasSize() {
  const rect = video.getBoundingClientRect();
  if (rect.width === 0) return;       // video not yet visible
  canvas.width  = rect.width;
  canvas.height = rect.height;
  renderCurrentFrame();
}

new ResizeObserver(syncCanvasSize).observe(video);
video.addEventListener('loadedmetadata', syncCanvasSize);

// ── Position interpolation ────────────────────────────────────────────────────

/**
 * Linearly interpolate the overlay position from an entry's keyframes.
 *
 * @param {Array<{t:number, x:number, y:number}>} positions
 * @param {number} t  Current video time in seconds
 * @returns {{x:number, y:number} | null}
 */
function interpolatePosition(positions, t) {
  if (!positions || positions.length === 0) return null;

  // Clamp to first / last keyframe
  if (t <= positions[0].t)                       return positions[0];
  if (t >= positions[positions.length - 1].t)    return positions[positions.length - 1];

  // Find the bracketing pair and lerp
  for (let i = 0; i < positions.length - 1; i++) {
    const p0 = positions[i];
    const p1 = positions[i + 1];
    if (t >= p0.t && t <= p1.t) {
      const alpha = (t - p0.t) / (p1.t - p0.t);
      return {
        x: p0.x + (p1.x - p0.x) * alpha,
        y: p0.y + (p1.y - p0.y) * alpha,
      };
    }
  }

  return positions[positions.length - 1];
}

// ── Drawing ───────────────────────────────────────────────────────────────────

/**
 * Draw a rounded-rectangle label at (rawX, rawY), scaling from the original
 * video resolution to the current canvas (display) resolution.
 *
 * @param {string} text
 * @param {number} rawX   x coordinate in original video pixels
 * @param {number} rawY   y coordinate in original video pixels
 */
function drawLabel(text, rawX, rawY) {
  // Scale from original resolution → current display resolution
  const videoW = video.videoWidth  || canvas.width;
  const videoH = video.videoHeight || canvas.height;
  const sx = canvas.width  / videoW;
  const sy = canvas.height / videoH;

  const x = Math.round(rawX * sx);
  const y = Math.round(rawY * sy);

  ctx.font = `bold ${FONT_SIZE}px ${FONT_FAMILY}`;
  const textW = ctx.measureText(text).width;

  const bgX = x - PAD_X;
  const bgY = y - FONT_SIZE - PAD_Y;
  const bgW = textW + PAD_X * 2;
  const bgH = FONT_SIZE + PAD_Y * 2;

  // Background pill
  ctx.fillStyle = BG_COLOR;
  ctx.beginPath();
  drawRoundRect(bgX, bgY, bgW, bgH, CORNER_RADIUS);
  ctx.fill();

  // Subtle border
  ctx.strokeStyle = OUTLINE_COLOR;
  ctx.lineWidth = 1;
  ctx.beginPath();
  drawRoundRect(bgX, bgY, bgW, bgH, CORNER_RADIUS);
  ctx.stroke();

  // Text
  ctx.fillStyle = TEXT_COLOR;
  ctx.fillText(text, x, y);
}

/**
 * Trace a rounded rectangle path on the current canvas context.
 * Compatible with all browsers (fallback for ctx.roundRect).
 */
function drawRoundRect(x, y, w, h, r) {
  const r2 = Math.min(r, w / 2, h / 2);
  ctx.moveTo(x + r2, y);
  ctx.lineTo(x + w - r2, y);
  ctx.arcTo(x + w, y,     x + w, y + r2,     r2);
  ctx.lineTo(x + w, y + h - r2);
  ctx.arcTo(x + w, y + h, x + w - r2, y + h, r2);
  ctx.lineTo(x + r2, y + h);
  ctx.arcTo(x,     y + h, x,     y + h - r2, r2);
  ctx.lineTo(x, y + r2);
  ctx.arcTo(x,     y,     x + r2, y,          r2);
  ctx.closePath();
}

// ── Render loop ───────────────────────────────────────────────────────────────

/** Render translation overlays for the current video timestamp. */
function renderCurrentFrame() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const t = video.currentTime;
  statusTime.textContent = `${t.toFixed(2)} s`;

  const activeItems = metadata.filter(
    (item) => t >= item.start_time && t <= item.end_time
  );

  for (const item of activeItems) {
    const pos = interpolatePosition(item.positions, t);
    if (pos) drawLabel(item.english, pos.x, pos.y);
  }

  statusActive.textContent = activeItems.length > 0
    ? activeItems.map((i) => `"${i.english}"`).join('  ·  ')
    : '';
}

/** Start the rAF loop (only while playing). */
function startLoop() {
  cancelAnimationFrame(animationId);
  animationId = null;

  function loop() {
    renderCurrentFrame();
    if (!video.paused && !video.ended) {
      animationId = requestAnimationFrame(loop);
    }
  }

  loop();
}

// ── Video event wiring ────────────────────────────────────────────────────────

video.addEventListener('play',   startLoop);
video.addEventListener('pause',  () => { cancelAnimationFrame(animationId); animationId = null; renderCurrentFrame(); });
video.addEventListener('ended',  () => { cancelAnimationFrame(animationId); animationId = null; renderCurrentFrame(); });
video.addEventListener('seeked', renderCurrentFrame);
video.addEventListener('timeupdate', () => { if (video.paused) renderCurrentFrame(); });

// ── Keyboard shortcuts ────────────────────────────────────────────────────────

document.addEventListener('keydown', (e) => {
  // Ignore when focus is in an input
  if (e.target.tagName === 'INPUT') return;

  if (e.code === 'Space') {
    e.preventDefault();
    video.paused ? video.play() : video.pause();
  } else if (e.code === 'ArrowRight') {
    e.preventDefault();
    video.currentTime = Math.min(video.duration || 0, video.currentTime + 5);
  } else if (e.code === 'ArrowLeft') {
    e.preventDefault();
    video.currentTime = Math.max(0, video.currentTime - 5);
  }
});

// ═══════════════════════════════════════════════════════════════════════════════
// PREPROCESSING UI
// ═══════════════════════════════════════════════════════════════════════════════

// ── Tab switching ─────────────────────────────────────────────────────────────

function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(
    (b) => b.classList.toggle('active', b.dataset.tab === name)
  );
  document.querySelectorAll('.tab-pane').forEach(
    (p) => p.classList.toggle('hidden', p.id !== `tab-${name}`)
  );
}

document.querySelectorAll('.tab-btn').forEach((btn) => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// ── Upload area ───────────────────────────────────────────────────────────────

const uploadArea   = document.getElementById('upload-area');
const ppVideoInput = document.getElementById('pp-video-input');
const ppFilename   = document.getElementById('pp-filename');
const startBtn     = document.getElementById('start-btn');

let preprocessFile = null;

function handleVideoSelect(file) {
  preprocessFile = file;
  ppFilename.textContent = file.name;
  uploadArea.classList.add('has-file');
  startBtn.disabled = false;
}

uploadArea.addEventListener('click',     () => ppVideoInput.click());
uploadArea.addEventListener('dragover',  (e) => { e.preventDefault(); uploadArea.classList.add('dragover'); });
uploadArea.addEventListener('dragleave', ()  => uploadArea.classList.remove('dragover'));
uploadArea.addEventListener('drop',      (e) => {
  e.preventDefault();
  uploadArea.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) handleVideoSelect(file);
});
ppVideoInput.addEventListener('change', (e) => {
  if (e.target.files[0]) handleVideoSelect(e.target.files[0]);
});

// ── Progress UI helpers ───────────────────────────────────────────────────────

const progressSection  = document.getElementById('progress-section');
const ppProgressWrap   = document.getElementById('pp-progress-bar-wrap');
const ppProgressFill   = document.getElementById('pp-progress-bar-fill');
const ppProgressText   = document.getElementById('pp-progress-text');
const ppLog            = document.getElementById('pp-log');
const ppDone           = document.getElementById('pp-done');
const ppError          = document.getElementById('pp-error');

function activateStep(stepNum) {
  for (let i = 1; i <= 4; i++) {
    const node = document.getElementById(`step-node-${i}`);
    node.className = 'step-node ' + (i < stepNum ? 'done' : i === stepNum ? 'active' : 'pending');
  }
}

function setProgressBar(current, total) {
  ppProgressWrap.classList.remove('hidden');
  const pct = total > 0 ? Math.round((current / total) * 100) : 0;
  ppProgressFill.style.width = `${pct}%`;
  ppProgressText.textContent = `${current} / ${total}`;
}

function addLogEntry(japanese, english) {
  const row = document.createElement('div');
  row.className = 'pp-log-entry';
  row.innerHTML = `<span class="pp-log-ja">${_esc(japanese)}</span>`
                + `<span class="pp-log-arrow">→</span>`
                + `<span class="pp-log-en">${_esc(english)}</span>`;
  ppLog.prepend(row);   // newest on top
}

function _esc(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function resetProgressUI() {
  for (let i = 1; i <= 4; i++)
    document.getElementById(`step-node-${i}`).className = 'step-node pending';
  ppProgressWrap.classList.add('hidden');
  ppProgressFill.style.width = '0%';
  ppProgressText.textContent = '';
  ppLog.innerHTML = '';
  ppDone.classList.add('hidden');
  ppError.classList.add('hidden');
}

// ── SSE event handler ─────────────────────────────────────────────────────────

function handleProgressEvent(ev, jobId) {
  if (ev.type === 'step') {
    activateStep(ev.step_num);
    // Hide progress bar when moving to a non-frame step
    if (ev.step_num !== 1) ppProgressWrap.classList.add('hidden');

  } else if (ev.type === 'ocr_progress') {
    setProgressBar(ev.current, ev.total);

  } else if (ev.type === 'translation') {
    setProgressBar(ev.current, ev.total);
    addLogEntry(ev.japanese, ev.english);

  } else if (ev.type === 'done') {
    // Mark all steps complete
    for (let i = 1; i <= 4; i++)
      document.getElementById(`step-node-${i}`).className = 'step-node done';
    ppProgressWrap.classList.add('hidden');
    ppDone.classList.remove('hidden');
    setTimeout(() => autoLoadResult(jobId), 1200);

  } else if (ev.type === 'error') {
    ppError.textContent = `Error: ${ev.message}`;
    ppError.classList.remove('hidden');
    startBtn.disabled = false;
    startBtn.textContent = 'Start Preprocessing';
  }
}

// ── Auto-load results into the Player tab ────────────────────────────────────

async function autoLoadResult(jobId) {
  // Fetch the generated metadata from the server
  const resp = await fetch(`/api/metadata/${jobId}`);
  metadata = await resp.json();
  metaFilename.textContent = `${metadata.length} translation entr${metadata.length === 1 ? 'y' : 'ies'} loaded`;

  // Point the player video element at the server-served video
  video.src = `/api/video/${jobId}`;
  wrapper.classList.add('has-video');
  videoFilename.textContent = ppFilename.textContent;

  // Switch to the Player tab
  switchTab('player');
}

// ── Start preprocessing ───────────────────────────────────────────────────────

startBtn.addEventListener('click', async () => {
  if (!preprocessFile) return;

  if (location.protocol === 'file:') {
    ppError.textContent = 'Run "node server.js" and open http://localhost:3000 to use preprocessing.';
    ppError.classList.remove('hidden');
    return;
  }

  startBtn.disabled = true;
  startBtn.textContent = 'Processing…';
  resetProgressUI();
  progressSection.classList.remove('hidden');

  const form = new FormData();
  form.append('video',      preprocessFile);
  form.append('sample_fps', document.getElementById('pp-sample-fps').value);
  form.append('det_conf',   document.getElementById('pp-det-conf').value);
  form.append('ocr_conf',   document.getElementById('pp-ocr-conf').value);

  let jobId;
  try {
    const resp = await fetch('/api/preprocess', { method: 'POST', body: form });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.error || resp.statusText);
    }
    ({ job_id: jobId } = await resp.json());
  } catch (err) {
    ppError.textContent = `Upload failed: ${err.message}`;
    ppError.classList.remove('hidden');
    startBtn.disabled = false;
    startBtn.textContent = 'Start Preprocessing';
    return;
  }

  // Stream progress via SSE
  const es = new EventSource(`/api/progress/${jobId}`);
  es.onmessage = (e) => {
    const ev = JSON.parse(e.data);
    handleProgressEvent(ev, jobId);
    if (ev.type === 'done' || ev.type === 'error') {
      es.close();
      if (ev.type !== 'done') {
        startBtn.disabled = false;
        startBtn.textContent = 'Start Preprocessing';
      }
    }
  };
  es.onerror = () => {
    es.close();
    ppError.textContent = 'Connection to server lost.';
    ppError.classList.remove('hidden');
    startBtn.disabled = false;
    startBtn.textContent = 'Start Preprocessing';
  };
});
