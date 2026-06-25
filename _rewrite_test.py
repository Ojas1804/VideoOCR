"""
One-shot script: rewrites test_single_frame.py to use the unified
detect_and_read_text() API instead of the old two-stage approach.
Run once from the project root, then delete this file.
"""
from pathlib import Path

NEW = '''\
"""
Diagnostic test: extract one frame from the test video, save it as an image,
then run the unified detect_and_read_text() pipeline step and translate.

Usage:
    python test_single_frame.py
    python test_single_frame.py --frame-index 30
    python test_single_frame.py --det-conf 0.3 --ocr-conf 0.3
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

VIDEO_PATH = Path("test/original/ytb_jap_mini.mp4")
OUTPUT_DIR = Path("test")

parser = argparse.ArgumentParser(description="Single-frame OCR diagnostic")
parser.add_argument("--frame-index", type=int, default=0,
                    help="0-based native frame index to extract (default: 0)")
parser.add_argument("--det-conf", type=float, default=0.3,
                    help="Detection confidence threshold (default: 0.3)")
parser.add_argument("--ocr-conf", type=float, default=0.3,
                    help="OCR recognition confidence threshold (default: 0.3)")
args = parser.parse_args()

print("=" * 60)
print("STEP 1 – Extract frame")
print("=" * 60)

if not VIDEO_PATH.exists():
    sys.exit(f"[ERROR] Video not found: {VIDEO_PATH}")

cap = cv2.VideoCapture(str(VIDEO_PATH))
if not cap.isOpened():
    sys.exit(f"[ERROR] Cannot open video: {VIDEO_PATH}")

native_fps   = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
width        = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height       = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
duration     = total_frames / native_fps if native_fps > 0 else 0

print(f"  Video       : {VIDEO_PATH}")
print(f"  FPS         : {native_fps:.2f}")
print(f"  Total frames: {total_frames}")
print(f"  Resolution  : {width}x{height}")
print(f"  Duration    : {duration:.2f}s")
print(f"  Frame index : {args.frame_index}")

cap.set(cv2.CAP_PROP_POS_FRAMES, args.frame_index)
ret, frame_bgr = cap.read()
cap.release()

if not ret or frame_bgr is None:
    sys.exit(f"[ERROR] Could not read frame {args.frame_index}")

timestamp = args.frame_index / native_fps if native_fps > 0 else 0
print(f"  Read OK at t={timestamp:.3f}s, shape={frame_bgr.shape}")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
frame_save_path = OUTPUT_DIR / f"test_frame_{args.frame_index}.png"
cv2.imwrite(str(frame_save_path), frame_bgr)
print(f"  Saved frame → {frame_save_path}")

print()
print("=" * 60)
print("STEP 2 – Raw predict() output (key inspection)")
print("=" * 60)
print("  Initialising PaddleOCR (lang=\\'japan\\') ...")

from paddleocr import PaddleOCR
ocr = PaddleOCR(
    lang="japan",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    enable_mkldnn=False,
)

print("  Running ocr.predict() on frame ...")
raw_results = ocr.predict(frame_bgr)

print(f"  type(raw_results) = {type(raw_results)}")
print(f"  len(raw_results)  = {len(raw_results) if raw_results else 0}")

if not raw_results:
    print("  [!] predict() returned empty — nothing detected at all.")
else:
    for i, res in enumerate(raw_results):
        print(f"\\n  raw_results[{i}]:")
        if isinstance(res, dict):
            for key, val in res.items():
                if hasattr(val, "__len__"):
                    print(f"    key=\\'{key}\\'  len={len(val)}  sample={repr(val[:2]) if len(val) else \\'[]\\' }")
                else:
                    print(f"    key=\\'{key}\\'  val={repr(val)}")
        else:
            print(f"    (not a dict — type={type(res)}, repr={repr(res)[:200]})")

print()
print("=" * 60)
print("STEP 3 – detect_and_read_text() results")
print("=" * 60)
print(f"  det_conf={args.det_conf}  ocr_conf={args.ocr_conf}")

from src.text_detector import detect_and_read_text
detections = detect_and_read_text(
    frame_bgr, args.frame_index,
    det_conf=args.det_conf,
    ocr_conf=args.ocr_conf,
)

print(f"  detect_and_read_text() returned {len(detections)} result(s)")
if not detections:
    print("  [!] Nothing passed both thresholds.")
    print("      Check the raw predict() output above for available keys and scores.")

for i, d in enumerate(detections):
    print(f"  [{i}] text=\\'{d[\\'text\\']}\\' "
          f"det={d[\\'det_score\\']:.4f}  ocr={d[\\'ocr_conf\\']:.4f}  bbox={d[\\'bbox\\']}")

    x, y, w, h = d["bbox"]
    crop = frame_bgr[max(0,y):min(height,y+h), max(0,x):min(width,x+w)]
    crop_path = OUTPUT_DIR / f"test_frame_{args.frame_index}_crop_{i}.png"
    cv2.imwrite(str(crop_path), crop)
    print(f"       crop saved → {crop_path}")

# Save annotated frame
annotated = frame_bgr.copy()
if raw_results:
    for res in raw_results:
        if not isinstance(res, dict):
            continue
        polys      = res.get("dt_polys",   [])
        det_scores = res.get("dt_scores",  [])
        rec_texts  = res.get("rec_texts",  [])
        rec_scores = res.get("rec_scores", [])
        for poly, d_sc, txt, r_sc in zip(polys, det_scores, rec_texts, rec_scores):
            accepted = d_sc >= args.det_conf and r_sc >= args.ocr_conf
            color = (0, 255, 0) if accepted else (0, 0, 255)
            pts = poly.reshape((-1, 1, 2)).astype(np.int32)
            cv2.polylines(annotated, [pts], isClosed=True, color=color, thickness=2)
            label = f"d={d_sc:.2f} r={r_sc:.2f}"
            xs = poly[:, 0]; ys = poly[:, 1]
            cv2.putText(annotated, label,
                        (int(xs.min()), max(0, int(ys.min()) - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
annotated_path = OUTPUT_DIR / f"test_frame_{args.frame_index}_detected.png"
cv2.imwrite(str(annotated_path), annotated)
print(f"\\n  Saved annotated frame → {annotated_path}")
print("  (green = accepted, red = below threshold)")

if not detections:
    sys.exit(0)

print()
print("=" * 60)
print("STEP 4 – Translation (MarianMT  ja→en)")
print("=" * 60)

from src.translator import translate_texts
texts_to_translate = [d["text"] for d in detections]
print(f"  Input texts: {texts_to_translate}")

translations = translate_texts(texts_to_translate)

print("\\n  Results:")
for src, tgt in translations.items():
    print(f"    \\'{src}\\'  →  \\'{tgt}\\'")

print()
print("=" * 60)
print("DONE – all steps completed successfully")
print("=" * 60)
'''

Path("test_single_frame.py").write_text(NEW, encoding="utf-8")
print("test_single_frame.py rewritten successfully.")
