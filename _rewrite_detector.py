content = '''\
import numpy as np
from paddleocr import PaddleOCR

_ocr: PaddleOCR | None = None

def _get_ocr() -> PaddleOCR:
    global _ocr
    if _ocr is None:
        _ocr = PaddleOCR(
            lang="japan",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,
        )
    return _ocr


def detect_and_read_text(
    frame_bgr: np.ndarray,
    frame_number: int,
    det_conf: float = 0.5,
    ocr_conf: float = 0.6,
) -> list[dict]:
    """Run the full PaddleOCR v3 pipeline (detection + recognition) in one
    ``predict()`` call.  Returns a list of dicts with keys:
        frame, bbox ([x, y, w, h]), text, det_score, ocr_conf
    """
    ocr = _get_ocr()
    results = ocr.predict(frame_bgr)
    detections: list[dict] = []
    if not results:
        return detections
    for result in results:
        polys      = result.get("dt_polys",   [])
        det_scores = result.get("dt_scores",  [])
        rec_texts  = result.get("rec_texts",  [])
        rec_scores = result.get("rec_scores", [])
        for poly, d_score, text, r_score in zip(
            polys, det_scores, rec_texts, rec_scores
        ):
            if d_score < det_conf:
                continue
            if r_score < ocr_conf:
                continue
            text = str(text).strip()
            if not text:
                continue
            xs = poly[:, 0]
            ys = poly[:, 1]
            x = int(xs.min())
            y = int(ys.min())
            w = int(xs.max() - x)
            h = int(ys.max() - y)
            detections.append({
                "frame":     frame_number,
                "bbox":      [x, y, w, h],
                "text":      text,
                "det_score": float(d_score),
                "ocr_conf":  float(r_score),
            })
    return detections
'''

with open("src/text_detector.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)

print("src/text_detector.py rewritten successfully.")
