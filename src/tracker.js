/**
 * Simple centroid-based text tracker.
 * Groups per-frame OCR detections into stable text segments across frames.
 */

function centroid([x, y, w, h]) {
  return [x + w / 2, y + h / 2];
}

function euclidean([ax, ay], [bx, by]) {
  return Math.hypot(ax - bx, ay - by);
}

function dominantText(dets) {
  const counts = Object.create(null);
  for (const d of dets) counts[d.text] = (counts[d.text] ?? 0) + 1;
  return Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0];
}

function splitOnTextChange(dets) {
  if (!dets.length) return [];
  const segs = [];
  let cur = [dets[0]];
  for (let i = 1; i < dets.length; i++) {
    if (dets[i].text !== cur[cur.length - 1].text) {
      segs.push(cur);
      cur = [dets[i]];
    } else {
      cur.push(dets[i]);
    }
  }
  segs.push(cur);
  return segs;
}

function r4(n) { return Math.round(n * 10000) / 10000; }

class Track {
  constructor(id, det) {
    this.id        = id;
    this.detections = [det];
    this.centroid  = centroid(det.bbox);
    this.lastFrame = det.frame;
  }
  update(det) {
    this.detections.push(det);
    this.centroid  = centroid(det.bbox);
    this.lastFrame = det.frame;
  }
}

/**
 * Link per-frame detections into stable tracks, then collapse into segments.
 *
 * @param {Array}  ocrResults
 * @param {number} [distThreshold=60]   max centroid distance (px) to link detections
 * @param {number} [minDetections=2]    minimum frames a track must appear in
 * @param {number} [maxSkip=3]          frames a track may be absent before being killed
 * @returns {Array<{trackId,startFrame,endFrame,startTime,endTime,text,keyframes}>}
 */
export function trackAndGroup(ocrResults, distThreshold = 60, minDetections = 2, maxSkip = 3) {
  // Group detections by frame number
  const byFrame = new Map();
  for (const r of ocrResults) {
    if (!byFrame.has(r.frame)) byFrame.set(r.frame, []);
    byFrame.get(r.frame).push(r);
  }

  const frames = [...byFrame.keys()].sort((a, b) => a - b);
  const active = [];
  const dead   = [];
  let nextId   = 0;

  for (const frameNum of frames) {
    const dets    = byFrame.get(frameNum);
    const usedDets = new Set();

    // Greedy nearest-centroid matching
    for (const track of active) {
      let bestDist = distThreshold;
      let bestDet  = null;
      for (const det of dets) {
        if (usedDets.has(det)) continue;
        const d = euclidean(track.centroid, centroid(det.bbox));
        if (d < bestDist) { bestDist = d; bestDet = det; }
      }
      if (bestDet) { track.update(bestDet); usedDets.add(bestDet); }
    }

    // Spawn new tracks for unmatched detections
    for (const det of dets) {
      if (!usedDets.has(det)) active.push(new Track(nextId++, det));
    }

    // Kill tracks that have not been seen for maxSkip frames
    for (let i = active.length - 1; i >= 0; i--) {
      if (frameNum - active[i].lastFrame > maxSkip) {
        dead.push(active.splice(i, 1)[0]);
      }
    }
  }

  dead.push(...active);

  const segments = [];
  for (const track of dead) {
    track.detections.sort((a, b) => a.frame - b.frame);
    for (const seg of splitOnTextChange(track.detections)) {
      if (seg.length < minDetections) continue;
      segments.push({
        trackId:    track.id,
        startFrame: seg[0].frame,
        endFrame:   seg[seg.length - 1].frame,
        startTime:  r4(seg[0].timestamp),
        endTime:    r4(seg[seg.length - 1].timestamp),
        text:       dominantText(seg),
        keyframes:  seg.map(d => ({ t: r4(d.timestamp), bbox: d.bbox })),
      });
    }
  }

  segments.sort((a, b) => a.startFrame - b.startFrame);
  return segments;
}
