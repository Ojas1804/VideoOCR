"""
One-shot script: rewrites the two-step detect+OCR block inside
preprocess.py to use the new unified detect_and_read_text() call.
Run once from the project root, then delete this file.
"""
from pathlib import Path

path = Path("preprocess.py")
text = path.read_text(encoding="utf-8")

OLD = (
    "        # Step 2\n"
    "        detections = detect_text_regions(\n"
    "            frame_bgr, frame_number, confidence_threshold=det_conf\n"
    "        )\n"
    "        if not detections:\n"
    "            continue\n"
    "        # Step 3\n"
    "        ocr_results = run_ocr_on_detections(\n"
    "            frame_bgr, detections, confidence_threshold=ocr_conf\n"
    "        )\n"
    "        for r in ocr_results:\n"
    "            r[\"timestamp\"] = round(timestamp, 4)\n"
    "        all_ocr.extend(ocr_results)"
)

NEW = (
    "        ocr_results = detect_and_read_text(\n"
    "            frame_bgr, frame_number, det_conf=det_conf, ocr_conf=ocr_conf\n"
    "        )\n"
    "        for r in ocr_results:\n"
    "            r[\"timestamp\"] = round(timestamp, 4)\n"
    "        all_ocr.extend(ocr_results)"
)

# Normalise to LF for matching, then apply
text_lf = text.replace("\r\n", "\n")
if OLD not in text_lf:
    print("[ERROR] Could not find the expected block — preprocess.py may have changed.")
    print("Expected block (repr):")
    print(repr(OLD))
else:
    result = text_lf.replace(OLD, NEW, 1)
    path.write_text(result, encoding="utf-8")
    print("preprocess.py updated successfully.")
