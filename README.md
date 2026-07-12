# VideoOCR

Automatically detect Japanese text in a video, translate it to English, and produce a metadata file that tells a playback app exactly **when**, **where**, and **what** to display — similar to subtitles, but with on-screen coordinates so translations appear right below the original text.

**Stack:** Node.js · Tesseract.js · fluent-ffmpeg · Express

---

## How it works

```
Video
 │
 ├─ Extract sampled frames        (ffmpeg via fluent-ffmpeg)
 ├─ Detect & read Japanese text   (Tesseract.js — jpn language)
 ├─ Track regions across frames   (centroid tracker)
 ├─ Collapse tracks into segments (dominant text, time range)
 ├─ Translate unique strings once (MyMemory API — ja → en)
 └─ Compute display coordinates   (below source bounding box)
          │
          ▼
  translation_metadata.json
```

---

## Requirements

- **Node.js 18+**
- ffmpeg is **bundled automatically** via `@ffmpeg-installer/ffmpeg` — no separate install needed.

Install all dependencies:

```bash
npm install
```

> **Tesseract language data** is downloaded automatically on first run and cached in `tessdata/`.

---

## Usage

### Preprocess a video (CLI)

```bash
node preprocess.js path/to/video.mp4
```

This runs all steps and writes two files:

| File | Contents |
|---|---|
| `ocr_raw.json` | Raw per-frame OCR detections (intermediate) |
| `translation_metadata.json` | Final playback-ready metadata |

### Options

| Flag | Default | Description |
|---|---|---|
| `--sample-fps <n>` | `2` | Frames per second to sample. Lower = faster, higher = more accurate timing. |
| `--ocr-conf <n>` | `0.3` | Minimum OCR confidence (0–1). |
| `--track-dist <n>` | `60` | Max pixel distance between frames to link two detections as the same text. |
| `--min-detections <n>` | `2` | A text region must appear in at least this many frames to be included. |
| `--ocr-output <path>` | `ocr_raw.json` | Path for the intermediate OCR file. |
| `--output <path>` | `translation_metadata.json` | Path for the final metadata file. |
| `--skip-ocr` | off | Skip frame extraction and OCR; load an existing `ocr_raw.json` instead. |
| `--api-key <key>` | `` | [MyMemory](https://mymemory.translated.net/) API key for 10 000 words/day (vs 1 000 anonymous). |

### Examples

Process at higher quality (4 fps):
```bash
node preprocess.js anime.mp4 --sample-fps 4
```

Re-run only tracking and translation (OCR already done):
```bash
node preprocess.js anime.mp4 --skip-ocr --ocr-output ocr_raw.json
```

### Web UI

```bash
node server.js
```

Open **http://localhost:3000**, upload a video, watch real-time progress, then switch to the Player tab.  
Options: `--host 0.0.0.0 --port 3000`

---

## Output format

`translation_metadata.json` is an array — one entry per stable text segment:

```json
[
  {
    "id": 1,
    "japanese": "ラーメン屋",
    "english": "Ramen Shop",
    "start_time": 4.17,
    "end_time": 8.33,
    "positions": [
      { "t": 4.17, "x": 500, "y": 355 },
      { "t": 6.25, "x": 560, "y": 355 }
    ]
  }
]
```

| Field | Description |
|---|---|
| `japanese` | Original text detected on screen |
| `english` | Translated text |
| `start_time` / `end_time` | Seconds when the text is visible |
| `positions` | Per-keyframe display coordinates. `x, y` is 10 px below the bottom of the source bounding box. The player interpolates between keyframes to follow a panning camera. |

---

## Playback

Open `player/index.html` directly in any modern browser (offline), or via `node server.js`.

1. Click **Load Video** and pick your video file.
2. Click **Load Metadata** and pick `translation_metadata.json`.
3. Press play — translations appear below each Japanese text region.

**Keyboard shortcuts:** `Space` play/pause · `→` +5 s · `←` −5 s

---

## Project structure

```
preprocess.js          # CLI entry point
server.js              # Express web server + worker-thread pipeline runner
src/
  frameExtractor.js    # Extract frames via ffmpeg
  textDetector.js      # Tesseract.js OCR (Japanese)
  tracker.js           # Centroid-based cross-frame tracker
  translator.js        # MyMemory REST translation
  pipeline.js          # Full pipeline function (used by both CLI and server)
  pipelineWorker.js    # worker_threads entry point for the server
player/
  index.html           # Browser UI
  player.js            # Playback logic: metadata lookup, interpolation, drawing
  style.css            # Styles
```
