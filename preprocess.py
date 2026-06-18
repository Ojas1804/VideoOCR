"""
preprocess.py – Phase 1, Steps 1-3 pipeline.

Usage:
    python preprocess.py <video_path> [--sample-fps 2] [--det-conf 0.5] [--ocr-conf 0.6] [--output ocr_raw.json]
"""

import argparse
import json
from pathlib import Path

from tqdm import tqdm

from src.frame_extractor import extract_frames, get_video_info
from src.text_detector import detect_text_regions
from src.ocr_processor import run_ocr_on_detections


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="VideoOCR Phase 1 – Extract frames, detect Japanese text, run OCR."
    )
    parser.add_argument("video", help="Path to the input video file.")
    parser.add_argument(
        "--sample-fps",
        type=float,
        default=2.0,
        help="Frames per second to sample from the video (default: 2).",
    )
    parser.add_argument(
        "--det-conf",
        type=float,
        default=0.5,
        help="Minimum detection confidence (default: 0.5).",
    )
    parser.add_argument(
        "--ocr-conf",
        type=float,
        default=0.6,
        help="Minimum OCR recognition confidence (default: 0.6).",
    )
    parser.add_argument(
        "--output",
        default="ocr_raw.json",
        help="Path for the output JSON file (default: ocr_raw.json).",
    )
    return parser.parse_args()


def run_pipeline(
    video_path: str,
    sample_fps: float = 2.0,
    det_conf: float = 0.5,
    ocr_conf: float = 0.6,
    output_path: str = "ocr_raw.json",
) -> list[dict]:
    """
    Run Steps 1-3 on a video and write raw OCR results to a JSON file.

    Returns:
        List of OCR result dicts:
        [
            {"frame": <int>, "text": "<str>", "bbox": [x, y, w, h]},
            ...
        ]
    """
    video_path = str(Path(video_path).resolve())
    info = get_video_info(video_path)
    print(
        f"Video: {video_path}\n"
        f"  Native FPS : {info['fps']:.2f}\n"
        f"  Duration   : {info['duration_seconds']:.1f}s\n"
        f"  Resolution : {info['width']}x{info['height']}\n"
        f"  Sample FPS : {sample_fps}\n"
    )

    estimated_samples = int(info["duration_seconds"] * sample_fps)
    all_ocr_results: list[dict] = []

    # --- Step 1 + 2 + 3 in one pass over sampled frames ---
    frame_iter = extract_frames(video_path, sample_fps=sample_fps)

    for frame_number, timestamp, frame_bgr in tqdm(
        frame_iter, total=estimated_samples, desc="Processing frames", unit="frame"
    ):
        # Step 2: detect text regions
        detections = detect_text_regions(frame_bgr, frame_number, confidence_threshold=det_conf)

        if not detections:
            continue

        # Step 3: OCR each detected region
        ocr_results = run_ocr_on_detections(frame_bgr, detections, confidence_threshold=ocr_conf)

        # Attach the timestamp to each result
        for result in ocr_results:
            result["timestamp"] = round(timestamp, 4)

        all_ocr_results.extend(ocr_results)

    # Write results to JSON
    output_path = str(Path(output_path).resolve())
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_ocr_results, f, ensure_ascii=False, indent=2)

    print(f"\nDone. {len(all_ocr_results)} OCR results written to: {output_path}")
    return all_ocr_results


if __name__ == "__main__":
    args = parse_args()
    run_pipeline(
        video_path=args.video,
        sample_fps=args.sample_fps,
        det_conf=args.det_conf,
        ocr_conf=args.ocr_conf,
        output_path=args.output,
    )
