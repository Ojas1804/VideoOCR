import numpy as np
from paddleocr import PaddleOCR

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
    frame_bgr: np.ndarray,frame_number: int,
    confidence_threshold: float = 0.5) -> list[dict]:
    detector = _get_detector()
    result = detector.ocr(frame_bgr, cls=False)
    detections: list[dict] = []
    if not result or result[0] is None:
        return detections
    for line in result[0]:
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