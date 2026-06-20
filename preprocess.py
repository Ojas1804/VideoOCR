import argparse
import json
from pathlib import Path

from tqdm import tqdm

from src.frame_extractor import extract_frames, get_video_info
from src.text_detector import detect_text_regions
from src.ocr_processor import run_ocr_on_detections
from src.tracker import track_and_group
from src.translator import translate_texts

_DISPLAY_PADDING_PX = 10

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="VideoOCR Phase 1 - Full pipeline: extract, detect, OCR, track, translate."
    )
    parser.add_argument("video", help="Path to the input video file.")
    parser.add_argument(
        "--sample-fps", type=float, default=2.0,
        help="Frames per second to sample from the video (default: 2).",
    )
    parser.add_argument(
        "--det-conf", type=float, default=0.5,
        help="Minimum detection confidence (default: 0.5).",
    )
    parser.add_argument(
        "--ocr-conf", type=float, default=0.6,
        help="Minimum OCR recognition confidence (default: 0.6).",
    )
    parser.add_argument(
        "--track-dist", type=float, default=60.0,
        help="Norfair centroid distance threshold in pixels (default: 60).",
    )
    parser.add_argument(
        "--min-detections", type=int, default=2,
        help="Minimum per-frame detections for a track to be kept (default: 2).",
    )
    parser.add_argument(
        "--ocr-output", default="ocr_raw.json",
        help="Path for the intermediate raw-OCR JSON (default: ocr_raw.json).",
    )
    parser.add_argument(
        "--output", default="translation_metadata.json",
        help="Path for the final metadata JSON (default: translation_metadata.json).",
    )
    parser.add_argument(
        "--skip-ocr", action="store_true",
        help="Skip Steps 1-3 and load OCR results from --ocr-output instead.",
    )
    return parser.parse_args()

def _extract_frames_and_ocr(video_path: str,sample_fps: float,det_conf: float,
    ocr_conf: float,ocr_output: str,) -> list[dict]:
    video_path = str(Path(video_path).resolve())
    info = get_video_info(video_path)
    print(
        f"Video : {video_path}\n"
        f"  Native FPS  : {info['fps']:.2f}\n"
        f"  Duration    : {info['duration_seconds']:.1f}s\n"
        f"  Resolution  : {info['width']}x{info['height']}\n"
        f"  Sample FPS  : {sample_fps}\n"
    )
    estimated_samples = int(info["duration_seconds"] * sample_fps)
    all_ocr: list[dict] = []
    frame_iter = extract_frames(video_path, sample_fps=sample_fps)
    for frame_number, timestamp, frame_bgr in tqdm(
        frame_iter, total=estimated_samples,
        desc="Extracting frames and running OCR", unit="frame",
    ):
        # Step 2
        detections = detect_text_regions(
            frame_bgr, frame_number, confidence_threshold=det_conf
        )
        if not detections:
            continue
        # Step 3
        ocr_results = run_ocr_on_detections(
            frame_bgr, detections, confidence_threshold=ocr_conf
        )
        for r in ocr_results:
            r["timestamp"] = round(timestamp, 4)
        all_ocr.extend(ocr_results)
    ocr_output = str(Path(ocr_output).resolve())
    with open(ocr_output, "w", encoding="utf-8") as f:
        json.dump(all_ocr, f, ensure_ascii=False, indent=2)
    print(f"[OCR] {len(all_ocr)} detections → {ocr_output}")
    return all_ocr

def _track_and_group_detections(
    ocr_results: list[dict],distance_threshold: float,
    min_detections: int) -> list[dict]:
    print("\n[Tracking] Associating detections across frames and grouping …")
    tracks = track_and_group(
        ocr_results,
        distance_threshold=distance_threshold,
        min_detections=min_detections,
    )
    print(f"[Tracking] {len(tracks)} stable track(s) found.")
    return tracks

def _translate_track_texts(tracks: list[dict]) -> list[dict]:
    print("\n[Translation] Translating unique Japanese strings …")
    unique_texts = list({t["text"] for t in tracks})
    translations = translate_texts(unique_texts)
    for track in tracks:
        track["translation"] = translations.get(track["text"], "")
    print(f"[Translation] {len(translations)} unique string(s) translated.")
    return tracks

def _build_display_metadata(tracks: list[dict]) -> list[dict]:
    metadata: list[dict] = []
    for i, track in enumerate(tracks, start=1):
        x, y, w, h = track["bbox"]
        display_x = x
        display_y = y + h + _DISPLAY_PADDING_PX
        metadata.append({
            "id":         i,
            "japanese":   track["text"],
            "english":    track["translation"],
            "start_time": track["start_time"],   # seconds
            "end_time":   track["end_time"],     # seconds
            "x":          display_x,
            "y":          display_y,
            "source_bbox": {
                "x":      x,
                "y":      y,
                "width":  w,
                "height": h,
            },
        })
    return metadata

def run_pipeline(
    video_path: str,sample_fps: float = 2.0,det_conf: float = 0.5,
    ocr_conf: float = 0.6,distance_threshold: float = 60.0,
    min_detections: int = 2,ocr_output: str = "ocr_raw.json",
    output_path: str = "translation_metadata.json",
    skip_ocr: bool = False,) -> list[dict]:
    if skip_ocr:
        ocr_path = str(Path(ocr_output).resolve())
        print(f"[OCR] --skip-ocr: loading from {ocr_path}")
        with open(ocr_path, "r", encoding="utf-8") as f:
            ocr_results: list[dict] = json.load(f)
    else:
        ocr_results = _extract_frames_and_ocr(
            video_path, sample_fps, det_conf, ocr_conf, ocr_output
        )
    if not ocr_results:
        print("No OCR results - nothing to process.")
        return []
    tracks = _track_and_group_detections(ocr_results, distance_threshold, min_detections)
    if not tracks:
        print("No stable tracks found - nothing to translate.")
        return []
    tracks = _translate_track_texts(tracks)
    metadata = _build_display_metadata(tracks)
    output_path = str(Path(output_path).resolve())
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"\n[Done] {len(metadata)} translation entry/entries → {output_path}")
    return metadata

if __name__ == "__main__":
    args = parse_args()
    run_pipeline(
        video_path=args.video,
        sample_fps=args.sample_fps,
        det_conf=args.det_conf,
        ocr_conf=args.ocr_conf,
        distance_threshold=args.track_dist,
        min_detections=args.min_detections,
        ocr_output=args.ocr_output,
        output_path=args.output,
        skip_ocr=args.skip_ocr,
    )