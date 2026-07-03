import numpy as np
import cv2
from PIL import Image
from paddleocr import PaddleOCR
from manga_ocr import MangaOcr

# PaddleOCR is used here for text *detection* only (bounding boxes).
# Recognition is delegated to manga-ocr, which is purpose-built for
# manga/anime-style Japanese text and performs far better than
# PaddleOCR's generic Japanese recognition model on this kind of content.
_detector: PaddleOCR | None = None
_recognizer: MangaOcr | None = None


def _get_detector() -> PaddleOCR:
    global _detector
    if _detector is None:
        _detector = PaddleOCR(
            lang="japan",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,
        )
    return _detector


def _get_recognizer() -> MangaOcr:
    global _recognizer
    if _recognizer is None:
        _recognizer = MangaOcr()
    return _recognizer


def _crop_region(frame_bgr: np.ndarray, x: int, y: int, w: int, h: int) -> np.ndarray:
    """Return the image patch described by (x, y, w, h), clamped to frame bounds."""
    height, width = frame_bgr.shape[:2]
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(width, x + w)
    y2 = min(height, y + h)
    return frame_bgr[y1:y2, x1:x2]


def detect_and_read_text(
    frame_bgr: np.ndarray,
    frame_number: int,
    det_conf: float = 0.5,
    ocr_conf: float = 0.6,
) -> list[dict]:
    """Detect text regions with PaddleOCR, then recognise each cropped region
    with manga-ocr.  Returns a list of dicts with keys:
        frame, bbox ([x, y, w, h]), text, det_score

    Note: ``ocr_conf`` is accepted for backwards compatibility but is unused,
    since manga-ocr does not expose a recognition confidence score.
    """
    detector = _get_detector()
    recognizer = _get_recognizer()
    results = detector.predict(frame_bgr)
    detections: list[dict] = []
    if not results:
        return detections
    for result in results:
        polys      = result.get("dt_polys",  [])
        det_scores = result.get("dt_scores", [])
        for poly, d_score in zip(polys, det_scores):
            if d_score < det_conf:
                continue
            xs = poly[:, 0]
            ys = poly[:, 1]
            x = int(xs.min())
            y = int(ys.min())
            w = int(xs.max() - x)
            h = int(ys.max() - y)

            crop = _crop_region(frame_bgr, x, y, w, h)
            if crop.size == 0:
                continue

            crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            text = recognizer(Image.fromarray(crop_rgb)).strip()
            if not text:
                continue

            detections.append({
                "frame":     frame_number,
                "bbox":      [x, y, w, h],
                "text":      text,
                "det_score": float(d_score),
            })
    return detections
