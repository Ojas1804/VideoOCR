import argparse
import json
import queue
import tempfile
import threading
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from preprocess import run_pipeline

app = Flask(__name__, static_folder="player", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024 * 1024  # 5 GB upload limit

_ALLOWED_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".m4v"}

# Temporary directory for uploaded videos and generated metadata
_WORK_DIR = Path(tempfile.gettempdir()) / "videocr_jobs"
_WORK_DIR.mkdir(exist_ok=True)

_job_queues: dict[str, queue.Queue] = {}

_STREAM_END = object()  # sentinel that signals the SSE generator to stop

@app.route("/")
def index():
    return send_from_directory("player", "index.html")

@app.route("/api/preprocess", methods=["POST"])
def start_preprocess():
    """Accept a video upload and start the preprocessing pipeline in a thread."""
    if "video" not in request.files:
        return jsonify({"error": "No video file"}), 400

    file = request.files["video"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    ext = Path(file.filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: {ext}"}), 400

    # Isolate every job in its own UUID directory
    job_id  = str(uuid.uuid4())
    job_dir = _WORK_DIR / job_id
    job_dir.mkdir()
    video_path = job_dir / f"video{ext}"
    file.save(str(video_path))

    sample_fps = float(request.form.get("sample_fps", 2.0))
    det_conf   = float(request.form.get("det_conf",   0.5))
    ocr_conf   = float(request.form.get("ocr_conf",   0.6))

    q: queue.Queue = queue.Queue()
    _job_queues[job_id] = q

    thread = threading.Thread(
        target=_run_pipeline_thread,
        args=(job_id, str(video_path), job_dir, sample_fps, det_conf, ocr_conf, q),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id})


def _run_pipeline_thread(job_id, video_path, job_dir, sample_fps, det_conf, ocr_conf, q):
    """Background thread: run the pipeline and push progress events to the queue."""
    ocr_output  = str(job_dir / "ocr_raw.json")
    meta_output = str(job_dir / "translation_metadata.json")

    def on_progress(event: dict):
        q.put(event)

    try:
        metadata = run_pipeline(
            video_path=video_path,
            sample_fps=sample_fps,
            det_conf=det_conf,
            ocr_conf=ocr_conf,
            ocr_output=ocr_output,
            output_path=meta_output,
            on_progress=on_progress,
        )
        q.put({"type": "done", "count": len(metadata)})
    except Exception as exc:
        q.put({"type": "error", "message": str(exc)})
    finally:
        q.put(_STREAM_END)


@app.route("/api/progress/<job_id>")
def stream_progress(job_id):
    if job_id not in _job_queues:
        return jsonify({"error": "Unknown job"}), 404

    q = _job_queues[job_id]

    def generate():
        try:
            while True:
                event = q.get()
                if event is _STREAM_END:
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except GeneratorExit:
            pass

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",     # disable nginx buffering if behind a proxy
        },
    )


@app.route("/api/metadata/<job_id>")
def get_metadata(job_id):
    meta_path = _WORK_DIR / job_id / "translation_metadata.json"
    if not meta_path.exists():
        return jsonify({"error": "Metadata not ready or job not found"}), 404
    with open(meta_path, "r", encoding="utf-8") as f:
        return Response(f.read(), mimetype="application/json")


@app.route("/api/video/<job_id>")
def get_video(job_id):
    job_dir = _WORK_DIR / job_id
    if not job_dir.exists():
        return jsonify({"error": "Job not found"}), 404
    for p in job_dir.iterdir():
        if p.stem == "video":
            return send_from_directory(str(job_dir), p.name)
    return jsonify({"error": "Video file not found"}), 404

def _parse_args():
    parser = argparse.ArgumentParser(description="VideoOCR web server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Port (default: 5000)")
    return parser.parse_args()

if __name__ == "__main__":
    args = _parse_args()
    url = f"http://{args.host}:{args.port}"
    print(f"VideoOCR server → {url}")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
