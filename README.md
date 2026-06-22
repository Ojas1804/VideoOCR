# VideoOCR

Automatically detect Japanese text in a video, translate it to English, and produce a metadata file that tells a playback app exactly **when**, **where**, and **what** to display — similar to subtitles, but with on-screen coordinates so translations appear right below the original text.

---

## How it works

```
Video
 │
 ├─ Extract sampled frames        (2 fps by default)
 ├─ Detect Japanese text regions  (PaddleOCR detector)
 ├─ Read the text in each region  (PaddleOCR recogniser)
 ├─ Track regions across frames   (Norfair)
 ├─ Collapse tracks into segments (dominant text, time range)
 ├─ Translate unique strings once (MarianMT  ja→en)
 └─ Compute display coordinates   (below source bounding box)
          │
          ▼
  translation_metadata.json
```

---

## Requirements

- Python 3.11+
- A CUDA-capable GPU is recommended for translation (CPU works too, but is slower)

Install all dependencies:

```bash
pip install -r requirements.txt
```

> **PaddlePaddle note:** the `requirements.txt` installs the CPU build by default. For a CUDA build visit the [PaddlePaddle install page](https://www.paddlepaddle.org.cn/en/install/quick).

---

## Usage

### Preprocess a video (full pipeline)

```bash
python preprocess.py path/to/video.mp4
```

This runs all steps and writes two files:

| File | Contents |
|---|---|
| `ocr_raw.json` | Raw per-frame OCR detections (intermediate) |
| `translation_metadata.json` | Final playback-ready metadata |

### Options

| Flag | Default | Description |
|---|---|---|
| `--sample-fps` | `2.0` | Frames per second to sample. Lower = faster, higher = more accurate timing. |
| `--det-conf` | `0.5` | Minimum detection confidence to accept a text region. |
| `--ocr-conf` | `0.6` | Minimum OCR confidence to accept a recognised string. |
| `--track-dist` | `60` | Max pixel distance between frames to link two detections as the same text. |
| `--min-detections` | `2` | A text region must appear in at least this many frames to be included. |
| `--ocr-output` | `ocr_raw.json` | Path for the intermediate OCR file. |
| `--output` | `translation_metadata.json` | Path for the final metadata file. |
| `--skip-ocr` | off | Skip frame extraction and OCR; load an existing `ocr_raw.json` instead. |

### Examples

Process at higher quality (4 fps, stricter confidence):
```bash
python preprocess.py anime.mp4 --sample-fps 4 --det-conf 0.6 --ocr-conf 0.7
```

Re-run only tracking and translation (OCR already done):
```bash
python preprocess.py anime.mp4 --skip-ocr --ocr-output ocr_raw.json
```

---

## Output format

`translation_metadata.json` is an array of entries, one per stable text segment:

```json
[
  {
    "id": 1,
    "japanese": "ラーメン屋",
    "english": "Ramen Shop",
    "start_time": 4.17,
    "end_time": 8.33,
    "positions": [
      { "t": 4.17, "x": 500, "y": 345 },
      { "t": 6.25, "x": 560, "y": 345 },
      { "t": 8.33, "x": 650, "y": 345 }
    ]
  }
]
```

| Field | Description |
|---|---|
| `japanese` | Original text detected on screen |
| `english` | Translated text |
| `start_time` / `end_time` | Seconds when the text is visible |
| `positions` | Per-frame display coordinates (pixels). The playback layer interpolates between these to follow a panning or zooming camera. `x`, `y` is where to render the translation — 10 px below the bottom of the source bounding box. |

Dynamic text (e.g. a scoreboard changing from "100" to "110") produces separate entries, one per stable value.

---

## Playback

Open `player/index.html` directly in any modern browser — no server needed.

```
player/index.html
```

### Steps

1. Click **Load Video** and pick your video file.
2. Click **Load Metadata** and pick the `translation_metadata.json` produced by `preprocess.py`.
3. Press play. Translations appear below each Japanese text region, following the camera if it pans.

### Keyboard shortcuts

| Key | Action |
|---|---|
| `Space` | Play / pause |
| `→` | Seek forward 5 s |
| `←` | Seek backward 5 s |

### How the overlay works

```
video.currentTime = 5.0 s
        │
        ▼
filter metadata where start_time ≤ 5.0 ≤ end_time
        │
        ├── for each active entry
        │     interpolate (x, y) from its keyframes   ← handles moving camera
        │     draw label on <canvas> overlay
        ▼
requestAnimationFrame → repeat
```

The canvas is kept pixel-perfect to the video element via a `ResizeObserver`, so overlays scale correctly when the window is resized or the browser zooms.

---

## Project structure

```
preprocess.py          # CLI entry point — runs the full pipeline
requirements.txt       # Python dependencies
src/
  frame_extractor.py   # Sample frames from a video at a given FPS
  text_detector.py     # Detect text regions with PaddleOCR
  ocr_processor.py     # Recognise text inside detected regions
  tracker.py           # Track regions across frames; split on text change
  translator.py        # Translate Japanese strings with MarianMT
player/
  index.html           # Browser player UI
  player.js            # Playback logic: metadata lookup, interpolation, drawing
  style.css            # Dark-theme styles
```
