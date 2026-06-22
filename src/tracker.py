import numpy as np
from collections import defaultdict, Counter

from norfair import Detection, Tracker


def _centroid(bbox: list[int]) -> np.ndarray:
    """Convert [x, y, w, h] → centroid array shaped (1, 2) for Norfair."""
    x, y, w, h = bbox
    return np.array([[x + w / 2.0, y + h / 2.0]], dtype=float)


def _split_on_text_change(detections: list[dict]) -> list[list[dict]]:
    if not detections:
        return []
    segments: list[list[dict]] = []
    current: list[dict] = [detections[0]]
    for det in detections[1:]:
        if det["text"] != current[-1]["text"]:
            segments.append(current)
            current = [det]
        else:
            current.append(det)
    segments.append(current)
    return segments

def track_and_group(
    ocr_results: list[dict],
    distance_threshold: float = 60.0,
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
    track_detections: dict[int, list[dict]] = defaultdict(list)
    for frame_number in sorted(frames.keys()):
        norfair_detections = [
            Detection(points=_centroid(r["bbox"]), data=r)
            for r in frames[frame_number]
        ]
        tracked_objects = tracker.update(detections=norfair_detections)
        for obj in tracked_objects:
            if (
                obj.last_detection is None
                or obj.last_detection.data.get("frame") != frame_number
            ):
                continue
            track_detections[obj.id].append(obj.last_detection.data)
    stable_tracks: list[dict] = []
    for tid, det_list in track_detections.items():
        det_list.sort(key=lambda d: d["frame"])
        for segment in _split_on_text_change(det_list):
            if len(segment) < min_detections:
                continue
            # Dominant text (majority vote within this stable segment)
            dominant_text = Counter(d["text"] for d in segment).most_common(1)[0][0]
            # One keyframe per sampled frame — supports moving-camera interpolation
            keyframes = [
                {"t": round(d["timestamp"], 4), "bbox": d["bbox"]}
                for d in segment
            ]
            stable_tracks.append({
                "track_id":    tid,
                "start_frame": segment[0]["frame"],
                "end_frame":   segment[-1]["frame"],
                "start_time":  round(segment[0]["timestamp"], 4),
                "end_time":    round(segment[-1]["timestamp"], 4),
                "text":        dominant_text,
                "keyframes":   keyframes,
            })
    stable_tracks.sort(key=lambda t: t["start_frame"])
    return stable_tracks