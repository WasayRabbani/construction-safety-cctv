"""
Video Processor Service — Thin HTTP Controller
===============================================
Port  : 5002
Routes:
  POST /api/process-video   — Upload + start async job
  GET  /api/status/<job_id> — Poll job progress
  GET  /outputs/<filename>  — Download annotated video
  GET  /health              — Health check

All AI logic (YOLO inference, face recognition) is handled by:
  core.PPEDetector    — YOLOv8 frame-by-frame inference
  core.FaceEngine     — Per-worker face recognition
"""

import os
import sys
import subprocess
import threading
import traceback
import uuid
import time
import logging

import cv2
import numpy as np
import imageio_ffmpeg
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# Make core/ importable when run standalone or via app.py
_AI_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AI_ROOT not in sys.path:
    sys.path.insert(0, _AI_ROOT)

from core.config import (                          # noqa: E402
    UPLOAD_DIR, OUTPUT_DIR, COLOR_VIOLATION, COLOR_SAFE, FONT,
    HEAD_CLASSES, VIOLATIONS,
)
from core.ppe_detector import PPEDetector, Detection  # noqa: E402
from core.face_engine import FaceEngine, FaceTracker  # noqa: E402

# ── App setup ─────────────────────────────────────────────────────────────────
PORT = 5002
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

# The base URL used to build the download link returned to the frontend.
# Locally: master app runs on 7860 and mounts this service at /video
BASE_URL = os.environ.get("AI_BASE_URL", "http://127.0.0.1:7860")

app = Flask(__name__)
CORS(app)
logging.getLogger("werkzeug").setLevel(logging.ERROR)

# ── Job tracker ───────────────────────────────────────────────────────────────
_jobs: dict = {}          # job_id -> { status, progress, result, error }
_jobs_lock = threading.Lock()


# ── Core processing function ──────────────────────────────────────────────────

def _run_yolo_on_video(
    input_path: str,
    output_raw_path: str,
    job_id: str,
    detector: PPEDetector,
    face_engine: FaceEngine,
) -> tuple:
    """
    Process video frame-by-frame with PPEDetector and optional FaceEngine.
    Returns (safe_total, viol_total, fps).
    """
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {input_path}")

    fps    = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Downscale very large videos (e.g. 4K → 720p) for speed
    MAX_WIDTH = 1280
    if width > MAX_WIDTH:
        ratio  = MAX_WIDTH / float(width)
        width  = MAX_WIDTH
        height = int(height * ratio)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_raw_path, fourcc, fps, (width, height))

    safe_total = 0
    viol_total = 0
    frame_idx  = 0

    # Lightweight frame-based tracker (no clock, uses frame count instead)
    tracker = FaceTracker(match_radius=150, timeout=999.0, cooldown=0.0)
    FACE_SCAN_COOLDOWN_FRAMES = 30  # re-scan if unseen for 30 frames

    skip_interval = 3        # run YOLO every 3rd frame
    cached_boxes: list = []  # holds detections for skipped frames
    # Per-frame face scan-attempt tracking (frame index of last scan per slot)
    last_scan_frame: dict = {}  # str(cx,cy) -> frame_idx

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame.shape[1] > MAX_WIDTH:
            frame = cv2.resize(frame, (width, height))

        # ── YOLO inference every `skip_interval` frames ───────────────────────
        if frame_idx % skip_interval == 0:
            detections = detector.detect(frame, conf=0.15, iou=0.7, imgsz=480)
            frame_safe = 0
            frame_viol = 0
            cached_boxes = []

            for det in detections:
                if det.is_violation:
                    frame_viol += 1
                else:
                    frame_safe += 1

                # ── Face recognition on head-class bounding boxes ─────────────
                if det.is_head and face_engine.backend is not None and face_engine.known_encodings:
                    cx, cy = det.center
                    slot = f"{cx},{cy}"
                    cached_name, _ = tracker.get_cached_identity(cx, cy)
                    last_f = last_scan_frame.get(slot, -FACE_SCAN_COOLDOWN_FRAMES - 1)

                    if cached_name in ("", "Unknown Person") and (frame_idx - last_f) >= FACE_SCAN_COOLDOWN_FRAMES:
                        x1, y1, x2, y2 = det.bbox
                        h, w = frame.shape[:2]
                        pad = 60
                        crop = frame[max(0, y1-pad): min(h, y2+pad), max(0, x1-pad): min(w, x2+pad)]

                        if crop.size > 0:
                            last_scan_frame[slot] = frame_idx
                            status, name, _ = face_engine.recognize_crop(crop)
                            if status in ("match", "unknown"):
                                tracker.update_cache(cx, cy, name)
                                cached_name = name
                                if status == "match":
                                    print(f"[FACE] Recognized offline: {name}")
                            elif status == "no_face":
                                tracker.update_cache(cx, cy, cached_name, is_scan_attempt=True)

                    det.person_name = cached_name

                cached_boxes.append(det)

            safe_total += frame_safe
            viol_total += frame_viol

        # ── Draw bounding boxes (fresh or cached) ─────────────────────────────
        frame_has_violations = any(d.is_violation for d in cached_boxes)
        PPEDetector.draw_overlays(frame, cached_boxes)

        # Bottom banner
        if frame_has_violations:
            cv2.rectangle(frame, (0, height - 40), (width, height), COLOR_VIOLATION, -1)
            cv2.putText(frame, "  !! VIOLATION DETECTED !!", (10, height - 12), FONT, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        else:
            cv2.rectangle(frame, (0, height - 40), (width, height), COLOR_SAFE, -1)
            cv2.putText(frame, "  ALL PPE OK", (10, height - 12), FONT, 0.7, (0, 0, 0), 2, cv2.LINE_AA)

        writer.write(frame)
        frame_idx += 1

        # Update progress every 5 frames
        if total > 0 and frame_idx % 5 == 0:
            progress = int((frame_idx / total) * 100)
            with _jobs_lock:
                if job_id in _jobs:
                    _jobs[job_id]["progress"] = progress

    cap.release()
    writer.release()
    return safe_total, viol_total, fps


def _convert_to_web_mp4(raw_path: str, final_path: str):
    """Re-encode OpenCV raw output to web-safe H.264 MP4."""
    cmd = [
        FFMPEG_PATH, "-y",
        "-i", raw_path,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-movflags", "+faststart",
        "-an",
        final_path,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr.decode(errors='ignore')}")


def _process_video_async(job_id: str, input_path: str, job_name: str):
    """Background thread: load engines → infer → unload → convert to H.264."""
    start_time   = time.time()
    raw_output   = os.path.join(OUTPUT_DIR, f"{job_id}_raw.mp4")
    final_output = os.path.join(OUTPUT_DIR, f"{job_id}_annotated.mp4")

    # Per-job engine instances (isolated from CCTV service)
    detector    = PPEDetector()
    face_engine = FaceEngine()

    try:
        with _jobs_lock:
            _jobs[job_id]["status"] = "loading_model"

        # Step 1: Load engines
        detector.load()
        face_engine.load_faces()

        with _jobs_lock:
            _jobs[job_id]["status"] = "processing"

        # Step 2: Inference
        safe_count, viol_count, fps = _run_yolo_on_video(
            input_path, raw_output, job_id, detector, face_engine
        )

        # Step 3: Unload immediately to free GPU / RAM
        detector.unload()
        face_engine.unload_faces()

        with _jobs_lock:
            _jobs[job_id]["status"] = "converting"
            _jobs[job_id]["progress"] = 99

        # Step 4: Convert to web-safe MP4
        _convert_to_web_mp4(raw_output, final_output)

        # Cleanup temp files
        for p in [raw_output, input_path]:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

        elapsed = round(time.time() - start_time, 1)

        with _jobs_lock:
            _jobs[job_id].update({
                "status": "done",
                "progress": 100,
                "result": {
                    "safe_count": safe_count,
                    "viol_count": viol_count,
                    "processing_time_sec": elapsed,
                    "processed_video_url": f"{BASE_URL}/video/outputs/{job_id}_annotated.mp4",
                    "download_filename": f"{job_name}_annotated.mp4",
                },
            })
        print(f"[DONE] Job {job_id}: safe={safe_count}, violations={viol_count}, time={elapsed}s")

    except Exception as e:
        traceback.print_exc()
        detector.unload()
        face_engine.unload_faces()
        with _jobs_lock:
            _jobs[job_id].update({"status": "error", "error": str(e)})
        for p in [raw_output, final_output, input_path]:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/process-video", methods=["POST"])
def process_video():
    """Accept uploaded video, start async processing job, return job_id."""
    if "video" not in request.files:
        return jsonify({"status": "error", "message": "No video file received. Label your file 'video'."}), 400

    video_file = request.files["video"]
    if video_file.filename == "":
        return jsonify({"status": "error", "message": "Empty filename received."}), 400

    allowed = {".mp4", ".avi", ".mov", ".mkv", ".wmv"}
    ext = os.path.splitext(video_file.filename)[1].lower()
    if ext not in allowed:
        return jsonify({"status": "error", "message": f"File type '{ext}' not supported."}), 400

    job_id   = str(uuid.uuid4())[:8]
    job_name = os.path.splitext(video_file.filename)[0]
    save_path = os.path.join(UPLOAD_DIR, f"{job_id}_input{ext}")
    video_file.save(save_path)
    print(f"[UPLOAD] Job {job_id}: {video_file.filename} → {save_path}")

    with _jobs_lock:
        _jobs[job_id] = {"status": "queued", "progress": 0, "result": None, "error": None}

    threading.Thread(
        target=_process_video_async,
        args=(job_id, save_path, job_name),
        daemon=True,
    ).start()

    return jsonify({
        "status": "queued",
        "job_id": job_id,
        "message": "Video received! Processing started. Poll /api/status/<job_id> for updates.",
    }), 202


@app.route("/api/status/<job_id>", methods=["GET"])
def get_status(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return jsonify({"status": "error", "message": "Job not found."}), 404
        response = {"status": job["status"], "progress": job.get("progress", 0)}
        if job["status"] == "done":
            response.update(job["result"])
        elif job["status"] == "error":
            response["message"] = job.get("error", "Unknown error")
    return jsonify(response)


@app.route("/outputs/<filename>")
def serve_output(filename):
    return send_from_directory(OUTPUT_DIR, filename)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "port": PORT})


if __name__ == "__main__":
    print("=" * 55)
    print(f"🎬 Video Processor API — http://0.0.0.0:{PORT}")
    print(f"   POST /api/process-video   → Upload & analyze")
    print(f"   GET  /api/status/<job_id> → Poll progress")
    print(f"   GET  /outputs/<filename>  → Download result")
    print("=" * 55)
    app.run(host="0.0.0.0", port=PORT, threaded=True)
