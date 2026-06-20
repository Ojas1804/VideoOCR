# 345
import numpy as np
from collections import defaultdict, Counter

from norfair import Detection, Tracker

def _centroid(bbox: list[int]) -> np.ndarray:
    """Convert [x, y, w, h] → centroid array shaped (1, 2) for Norfair."""
    x, y, w, h = bbox
    return np.array([[x + w / 2.0, y + h / 2.0]], dtype=float)


def _median_bbox(bboxes: list[list[int]]) -> list[int]:
    """Return element-wise median of a list of [x, y, w, h] bounding boxes."""
    arr = np.array(bboxes, dtype=float)
    return [int(np.median(arr[:, i])) for i in range(4)]

def track_and_group(ocr_results: list[dict],distance_threshold: float = 60.0,
    min_detections: int = 2,) -> list[dict]:
    frames: dict[int, list[dict]] = defaultdict(list)
    for r in ocr_results:
        frames[r["frame"]].append(r)
    tracker = Tracker(
        distance_function="euclidean",
        distance_threshold=distance_threshold,
        hit_counter_max=3,
        initialization_delay=0,
    )
    track_data: dict[int, dict] = {}

    for frame_number in sorted(frames.keys()):
        frame_results = frames[frame_number]

        norfair_detections = [
            Detection(points=_centroid(r["bbox"]), data=r)
            for r in frame_results
        ]
        tracked_objects = tracker.update(detections=norfair_detections)
        for obj in tracked_objects:
            tid = obj.id
            if (
                obj.last_detection is None
                or obj.last_detection.data.get("frame") != frame_number
            ):
                continue

            if tid not in track_data:
                track_data[tid] = {
                    "texts": [],
                    "bboxes": [],
                    "frames": [],
                    "timestamps": [],
                }
            d = obj.last_detection.data
            track_data[tid]["texts"].append(d["text"])
            track_data[tid]["bboxes"].append(d["bbox"])
            track_data[tid]["frames"].append(d["frame"])
            track_data[tid]["timestamps"].append(d["timestamp"])
    stable_tracks: list[dict] = []
    for tid, td in track_data.items():
        if len(td["frames"]) < min_detections:
            continue
        dominant_text = Counter(td["texts"]).most_common(1)[0][0]
        rep_bbox = _median_bbox(td["bboxes"])
        start_frame = min(td["frames"])
        end_frame = max(td["frames"])
        frame_to_ts = dict(zip(td["frames"], td["timestamps"]))
        start_time = frame_to_ts[start_frame]
        end_time = frame_to_ts[end_frame]
        stable_tracks.append({
            "track_id": tid,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "start_time": round(start_time, 4),
            "end_time": round(end_time,   4),
            "text": dominant_text,
            "bbox": rep_bbox,
        })
    stable_tracks.sort(key=lambda t: t["start_frame"])
    return stable_tracks