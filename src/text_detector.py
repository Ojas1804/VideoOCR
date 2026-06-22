import numpy as np
from paddleocr import PaddleOCR

_detector: PaddleOCR | None = None

def _get_detector() -> PaddleOCR:
    global _detector
    if _detector is None:
        _detector = PaddleOCR(
                        lang="japan",
                        use_doc_orientation_classify=False,
                        use_doc_unwarping=False,
                        use_textline_orientation=False,
                        enable_mkldnn=False
                    )
    return _detector


# def detect_text_regions(
#     frame_bgr: np.ndarray,frame_number: int,
#     confidence_threshold: float = 0.5) -> list[dict]:
#     detector = _get_detector()
#     result = detector.ocr(frame_bgr)
#     detections: list[dict] = []
#     if not result or result[0] is None:
#         return detections
#     for line in result[0]:
#         # polygon_points is a list of 4 [x, y] corners (quad)
#         polygon, confidence = line
#         if confidence < confidence_threshold:
#             continue
#         # Convert quad to axis-aligned bounding box [x, y, w, h]
#         xs = [pt[0] for pt in polygon]
#         ys = [pt[1] for pt in polygon]
#         x = int(min(xs))
#         y = int(min(ys))
#         w = int(max(xs) - x)
#         h = int(max(ys) - y)
#         detections.append({
#             "frame": frame_number,
#             "bbox": [x, y, w, h],
#         })
#     return detections

def detect_text_regions(frame_bgr: np.ndarray,frame_number: int,
    confidence_threshold: float = 0.5) -> list[dict]:
    detector = _get_detector()
    results = detector.predict(frame_bgr)
    detections: list[dict] = []
    if not results:
        return detections
    for result in results:
        polys = result.get("dt_polys", [])
        scores = result.get("dt_scores", [])
        for poly, score in zip(polys, scores):
            if score < confidence_threshold:
                continue
            xs = poly[:, 0]
            ys = poly[:, 1]
            x = int(xs.min())
            y = int(ys.min())
            w = int(xs.max() - x)
            h = int(ys.max() - y)
            detections.append({
                "frame": frame_number,
                "bbox": [x, y, w, h],
            })
    return detections