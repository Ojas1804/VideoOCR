import numpy as np
from paddleocr import PaddleOCR

# Singleton OCR engine - recognition only (det=False).
_recogniser: PaddleOCR | None = None

def _get_recogniser() -> PaddleOCR:
    global _recogniser
    if _recogniser is None:
        _recogniser = PaddleOCR(
            use_angle_cls=False,
            lang="japan",
            det=False,   # skip re-detection; we already have boxes
            rec=True,
            show_log=False,
        )
    return _recogniser


def _crop_region(frame_bgr: np.ndarray, bbox: list[int]) -> np.ndarray:
    """Return the image patch described by [x, y, w, h], clamped to frame bounds."""
    x, y, w, h = bbox
    height, width = frame_bgr.shape[:2]
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(width, x + w)
    y2 = min(height, y + h)
    return frame_bgr[y1:y2, x1:x2]


def run_ocr_on_region(frame_bgr: np.ndarray,frame_number: int,
    bbox: list[int],confidence_threshold: float = 0.6) -> dict | None:
    crop = _crop_region(frame_bgr, bbox)
    if crop.size == 0:
        return None
    recogniser = _get_recogniser()
    result = recogniser.ocr(crop, cls=False)
    if not result or result[0] is None:
        return None
    # Collect all text lines in the crop, pick the one with highest confidence
    best_text = ""
    best_conf = 0.0
    for line in result[0]:
        # Recognition output: [bbox_within_crop, (text, confidence)]
        _, (text, conf) = line
        if conf > best_conf:
            best_conf = conf
            best_text = text
    if best_conf < confidence_threshold or not best_text.strip():
        return None
    return {
        "frame": frame_number,
        "text": best_text.strip(),
        "bbox": bbox,
    }

def run_ocr_on_detections(frame_bgr: np.ndarray,
    detections: list[dict],
    confidence_threshold: float = 0.6) -> list[dict]:
    results = []
    for det in detections:
        ocr_result = run_ocr_on_region(
            frame_bgr,
            det["frame"],
            det["bbox"],
            confidence_threshold,
        )
        if ocr_result is not None:
            results.append(ocr_result)
    return results