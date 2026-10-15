"""
Intelligent CCTV Service — Thin HTTP Controller
================================================
Port  : 5001
Routes:
  GET  /video_feed       — MJPEG stream
  POST /start_camera     — Activate YOLO + camera
  POST /stop_camera      — Deactivate and free memory
  POST /set_camera       — Switch source (webcam / RTSP)
  GET  /get_camera       — Current source
  POST /reload_faces     — Reload face DB without restart

All AI logic is handled by:
  core.PPEDetector    — YOLOv8 inference
  core.FaceEngine     — Face recognition + tracking
  core.CameraStream   — Background frame capture
"""

import os
import sys
import collections
import threading
import time
import logging

import cv2
from flask import Flask, Response, jsonify, request
from flask_cors import CORS

# Make core/ importable when run standalone or via app.py
_AI_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AI_ROOT not in sys.path:
    sys.path.insert(0, _AI_ROOT)

from core.config import (                        # noqa: E402
    DEFAULT_RTSP_URL, VIOLATIONS, HEAD_CLASSES,
    COLOR_VIOLATION, COLOR_SAFE, COLOR_INFO, COLOR_NAME, FONT,
)
from core.ppe_detector import PPEDetector, Detection  # noqa: E402
from core.face_engine import FaceEngine               # noqa: E402
from core.camera_stream import CameraStream           # noqa: E402

# ── TF GPU safety (must precede any TF / DeepFace import) ─────────────────────
os.environ["TF_FORCE_GPU_ALLOW_GROWTH"] = "true"

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)
logging.getLogger("werkzeug").setLevel(logging.ERROR)

# ── Core engine instances (one per service process) ───────────────────────────
_detector = PPEDetector()
_face_engine = FaceEngine()
_stream = CameraStream()

# ── Shared state (updated by AI worker, read by frame generator) ──────────────
_latest_detections: list = []          # List[Detection]
_metrics = {"safe_count": 0, "viol_count": 0}
_camera_active = False
_state_lock = threading.Lock()         # Guards _latest_detections and _metrics

# ── AI worker thread ──────────────────────────────────────────────────────────
# Reads frames from CameraStream, runs PPEDetector, dispatches face recognition
# threads using FaceEngine + FaceTracker.

_face_scan_active = False              # Global flag: only one face scan at a time
AI_SKIP_FRAMES = 2                     # Run YOLO on every Nth frame for speed


def _ai_worker():
    """Background loop: PPE detection + face recognition on camera frames."""
    global _camera_active, _face_scan_active

    face_db_loaded = False
    frame_counter = 0

    while True:
        if not _camera_active:
            time.sleep(0.1)
            continue

        # Lazy face-db load once per CCTV session
        if not face_db_loaded:
            _face_engine.load_faces()
            face_db_loaded = True

        # Wait for model to be loaded
        if not _detector.is_loaded:
            time.sleep(0.1)
            continue

        frame = _stream.get_frame()
        if frame is None:
            time.sleep(0.05)
            continue

        # Frame skipping to improve throughput
        frame_counter += 1
        if frame_counter % AI_SKIP_FRAMES != 0:
            time.sleep(0.01)
            continue

        frame_copy = frame.copy()

        try:
            detections = _detector.detect(frame_copy, conf=0.15, iou=0.7, imgsz=640)
        except Exception as e:
            print(f"[ERROR] PPEDetector: {e}")
            time.sleep(1)
            continue

        safe_cnt, viol_cnt = 0, 0

        for det in detections:
            if det.is_violation:
                viol_cnt += 1
            else:
                safe_cnt += 1

            if not det.is_head:
                continue

            cx, cy = det.center
            cached_name, last_scan_ts = _face_engine.tracker.get_cached_identity(cx, cy)
            det.person_name = cached_name

            # Dispatch face scan in a thread if identity is unknown and cooldown is over
            if not _face_scan_active:
                if cached_name in ("", "Unknown Person") and (time.time() - last_scan_ts) > 1.5:
                    x1, y1, x2, y2 = det.bbox
                    h, w = frame_copy.shape[:2]
                    pad = 60
                    crop = frame_copy[
                        max(0, y1 - pad): min(h, y2 + pad),
                        max(0, x1 - pad): min(w, x2 + pad),
                    ]
                    if crop.size > 0:
                        _face_scan_active = True
                        # Mark as scan-attempted to start cooldown
                        _face_engine.tracker.update_cache(cx, cy, cached_name, is_scan_attempt=True)
                        threading.Thread(
                            target=_run_face_scan,
                            args=(crop, cx, cy),
                            daemon=True,
                        ).start()

        with _state_lock:
            _latest_detections[:] = detections
            _metrics["safe_count"] = safe_cnt
            _metrics["viol_count"] = viol_cnt


def _run_face_scan(crop, cx: int, cy: int):
    """Thread target: run FaceEngine on a crop and update the tracker."""
    global _face_scan_active
    try:
        status, name, _ = _face_engine.recognize_crop(crop)
        if status in ("match", "unknown"):
            _face_engine.tracker.update_cache(cx, cy, name)
            if status == "match":
                print(f"[FACE] Recognized: {name}")
    except Exception as e:
        print(f"[WARN] Face scan error: {e}")
    finally:
        _face_scan_active = False


# Start background AI worker
threading.Thread(target=_ai_worker, daemon=True).start()


# ── Frame streaming ────────────────────────────────────────────────────────────

def _generate_frames():
    """Generator: annotates frames with cached detections and yields MJPEG."""
    fps_deque = collections.deque(maxlen=30)
    prev_time = time.time()
    TARGET_FPS = 30
    frame_time = 1.0 / TARGET_FPS

    while True:
        frame_start = time.time()
        raw = _stream.get_frame()

        if raw is None:
            time.sleep(0.03)
            continue

        frame = raw.copy()

        # Overlay cached AI detections
        with _state_lock:
            detections = list(_latest_detections)
            safe_cnt = _metrics["safe_count"]
            viol_cnt = _metrics["viol_count"]

        PPEDetector.draw_overlays(frame, detections)

        # FPS overlay
        now = time.time()
        fps_deque.append(1.0 / max(now - prev_time, 1e-6))
        fps = sum(fps_deque) / len(fps_deque)
        prev_time = now

        cv2.putText(frame, f"Stream FPS: {fps:.1f}", (10, 25), FONT, 0.65, COLOR_INFO, 2, cv2.LINE_AA)
        cv2.putText(frame, f"Safe:{safe_cnt}  Violations:{viol_cnt}", (10, 55), FONT, 0.6, COLOR_INFO, 1, cv2.LINE_AA)

        # Bottom banner
        h, w = frame.shape[:2]
        if viol_cnt > 0:
            cv2.rectangle(frame, (0, h - 40), (w, h), COLOR_VIOLATION, -1)
            cv2.putText(frame, f"  !! VIOLATION DETECTED: {viol_cnt}", (10, h - 12), FONT, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        else:
            cv2.rectangle(frame, (0, h - 40), (w, h), COLOR_SAFE, -1)
            cv2.putText(frame, "  ALL PPE OK", (10, h - 12), FONT, 0.7, (0, 0, 0), 2, cv2.LINE_AA)

        ret, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if ret:
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")

        # Pace to target FPS
        elapsed = time.time() - frame_start
        sleep_time = max(0.0, frame_time - elapsed)
        if sleep_time > 0:
            time.sleep(sleep_time)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/video_feed")
def video_feed():
    return Response(_generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/start_camera", methods=["POST"])
def start_camera():
    global _camera_active
    data = request.get_json(silent=True) or {}
    # If a source is passed with start_camera, apply it now.
    # Otherwise keep whatever was previously set (default is 0 from CameraStream init).
    source = data.get("source")
    if source is not None:
        if source == "imou":
            _stream.set_source(DEFAULT_RTSP_URL)
        else:
            try:
                _stream.set_source(int(source))
            except (ValueError, TypeError):
                _stream.set_source(source)

    _detector.load()
    _face_engine.load_faces()
    _stream.start()
    _camera_active = True
    print(f"[INFO] Camera (source={_stream._source}) + AI model + Face DB started by frontend.")
    return jsonify({"status": "ok", "loaded_faces": len(_face_engine.known_names)})


@app.route("/stop_camera", methods=["POST"])
def stop_camera():
    global _camera_active
    _camera_active = False
    _stream.stop()
    _detector.unload()
    print("[INFO] Camera + AI model stopped. Resources freed.")
    return jsonify({"status": "ok"})


@app.route("/set_camera", methods=["POST"])
def set_camera():
    data = request.get_json()
    source = data.get("source", 0)
    if source == "imou":
        _stream.set_source(DEFAULT_RTSP_URL)
        source_label = DEFAULT_RTSP_URL
    else:
        try:
            source_int = int(source)
            _stream.set_source(source_int)
            source_label = source_int
        except (ValueError, TypeError):
            _stream.set_source(source)
            source_label = source
    print(f"[INFO] Camera source changed to: {source_label}")
    return jsonify({"status": "ok", "camera": str(source_label)})


@app.route("/get_camera", methods=["GET"])
def get_camera():
    return jsonify({"camera": str(_stream._source)})


@app.route("/reload_faces", methods=["POST", "GET"])
def reload_faces():
    """Reload face database without restarting the server."""
    _face_engine.unload_faces()
    count = _face_engine.load_faces()
    return jsonify({
        "status": "ok",
        "loaded_faces": count,
        "workers": list(set(_face_engine.known_names)),
    })


if __name__ == "__main__":
    print("🚀 Intelligent CCTV Server starting on port 5001")
    app.run(host="0.0.0.0", port=5001, threaded=True)
