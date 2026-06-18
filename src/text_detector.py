"""
Step 2: Detect Japanese Text Regions
Runs PaddleOCR's detector on a frame and returns bounding boxes.
"""

import numpy as np
from paddleocr import PaddleOCR


# Singleton OCR engine – detection only (rec=False) to keep this step lean.
# lang='japan' activates the Japanese detection/recognition models.
_detector: PaddleOCR | None = None


def _get_detector() -> PaddleOCR:
    global _detector
    if _detector is None:
        _detector = PaddleOCR(
            use_angle_cls=False,
            lang="japan",
            det=True,
            rec=False,   # detection only for this step
            show_log=False,
        )
    return _detector


def detect_text_regions(
    frame_bgr: np.ndarray,
    frame_number: int,
    confidence_threshold: float = 0.5,
) -> list[dict]:
    """
    Detect text bounding boxes in a single frame.

    Args:
        frame_bgr:            BGR image (as returned by OpenCV).
        frame_number:         Original frame index in the video.
        confidence_threshold: Minimum detection confidence to keep a box.

    Returns:
        List of dicts:
        [
            {
                "frame": <int>,
                "bbox":  [x, y, width, height]   # top-left origin, pixel coords
            },
            ...
        ]
    """
    detector = _get_detector()
    result = detector.ocr(frame_bgr, cls=False)

    detections: list[dict] = []

    if not result or result[0] is None:
        return detections

    for line in result[0]:
        # PaddleOCR detection-only output: [polygon_points, confidence]
        # polygon_points is a list of 4 [x, y] corners (quad)
        polygon, confidence = line

        if confidence < confidence_threshold:
            continue

        # Convert quad to axis-aligned bounding box [x, y, w, h]
        xs = [pt[0] for pt in polygon]
        ys = [pt[1] for pt in polygon]
        x = int(min(xs))
        y = int(min(ys))
        w = int(max(xs) - x)
        h = int(max(ys) - y)

        detections.append({
            "frame": frame_number,
            "bbox": [x, y, w, h],
        })

    return detections
