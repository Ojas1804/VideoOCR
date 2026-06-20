import cv2
import numpy as np
from pathlib import Path
from typing import Generator

def get_video_info(video_path: str) -> dict:
    """Return basic metadata about a video file."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")
    info = {
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    }
    info["duration_seconds"] = info["total_frames"] / info["fps"] if info["fps"] > 0 else 0
    cap.release()
    return info

def extract_frames(video_path: str,
                   sample_fps: float = 2.0) -> Generator[tuple[int, float, np.ndarray], None, None]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")
    native_fps: float = cap.get(cv2.CAP_PROP_FPS)
    if native_fps <= 0:
        raise ValueError("Could not determine video FPS.")
    # How many native frames to skip between each sample
    frame_interval = max(1, round(native_fps / sample_fps))
    frame_number = 0
    sampled = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_number % frame_interval == 0:
            timestamp = frame_number / native_fps
            yield frame_number, timestamp, frame
            sampled += 1
        frame_number += 1
    cap.release()
    print(
        f"[extract_frames] Video FPS={native_fps:.2f}, "
        f"sample_fps={sample_fps}, interval={frame_interval} frames. "
        f"Yielded {sampled} frames out of {frame_number} total."
    )