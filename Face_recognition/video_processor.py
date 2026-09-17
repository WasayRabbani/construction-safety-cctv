# ============================================================
# VIDEO PROCESSOR - Offline PPE Detection API
# Port: 5002
# Standalone Flask microservice. Receives an uploaded video,
# runs YOLOv8 PPE detection frame-by-frame (same model as
# the live CCTV), draws bounding boxes, and saves the
# annotated video so the user can download it.
# ============================================================

import os
import time
import uuid
import threading
import traceback

import cv2
import numpy as np
import torch
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from ultralytics import YOLO
import imageio_ffmpeg
try:
    import face_recognition
    FACE_BACKEND = 'dlib'
except ImportError:
    FACE_BACKEND = None
    print("[INFO] face_recognition not available — face ID disabled in video processor.")

# ── CONFIG ───────────────────────────────────────────────────
PORT        = 5002
MODEL_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'best.pt')
UPLOAD_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'processed_videos', 'uploads')
OUTPUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'processed_videos', 'outputs')
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
EMPLOYEES_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'employees')

# The base URL used to build the download link returned to the frontend.
# Locally: master app runs on 7860 and mounts this at /video
# Cloud:   set AI_BASE_URL env var to e.g. https://wasayrabbani-ppe-system.hf.space
BASE_URL = os.environ.get('AI_BASE_URL', 'http://127.0.0.1:7860')

KNOWN_ENCODINGS = []
KNOWN_NAMES = []
faces_loaded = False
FACE_MATCH_RADIUS = 150
FACE_SCAN_COOLDOWN = 30 # frames

# Violation class names (same list as intelligent_cctv.py)
VIOLATIONS = {
    'NO-Hardhat', 'NO-Gloves', 'NO-Mask',
    'NO-Goggles', 'NO-Safety Vest', 'Fall-Detected'
}

COLOR_VIOLATION = (0, 0, 255)    # Red
COLOR_SAFE      = (0, 200, 80)   # Green
FONT            = cv2.FONT_HERSHEY_SIMPLEX

# ── DEVICE ───────────────────────────────────────────────────
if torch.cuda.is_available():
    DEVICE = 0
    torch.backends.cudnn.benchmark = True
    print(f"✅ GPU: {torch.cuda.get_device_name(0)}")
else:
    DEVICE = 'cpu'
    print("ℹ️  No GPU found. Using CPU.")

# ── DIRECTORIES ──────────────────────────────────────────────
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── LAZY MODEL LOADING ───────────────────────────────────────
# The model is NOT loaded at startup. It loads only when a video
# is submitted, and is unloaded (freeing GPU/RAM) when done.
yolo_model      = None
yolo_model_lock = threading.Lock()

def load_model():
    global yolo_model, faces_loaded, KNOWN_ENCODINGS, KNOWN_NAMES
    
    if not faces_loaded:
        print("[FACE] Loading Employee Database into Memory...")
        try:
            for root, dirs, files in os.walk(EMPLOYEES_DB):
                for f in files:
                    if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                        path = os.path.join(root, f)
                        img = face_recognition.load_image_file(path)
                        encs = face_recognition.face_encodings(img)
                        if encs:
                            KNOWN_ENCODINGS.append(encs[0])
                            worker_id = os.path.basename(root)
                            KNOWN_NAMES.append(worker_id)
            faces_loaded = True
            print(f"[FACE] Loaded {len(KNOWN_NAMES)} employees.")
        except Exception as e:
            print(f"[ERROR] Failed to load faces: {e}")

    with yolo_model_lock:
        if yolo_model is None:
            print("[INFO] Loading YOLO model into memory…")
            yolo_model = YOLO(MODEL_PATH)
            yolo_model.overrides['verbose'] = False
            print("[INFO] YOLO model ready.")

def unload_model():
    global yolo_model
    with yolo_model_lock:
        if yolo_model is not None:
            print("[INFO] Unloading YOLO model and freeing memory…")
            del yolo_model
            yolo_model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("[INFO] YOLO model unloaded.")

# ── JOB TRACKER (for async status polling) ───────────────────
jobs = {}   # job_id -> { status, progress, result, error }
jobs_lock = threading.Lock()

# ── FLASK APP ────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

import logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)


# ─────────────────────────────────────────────────────────────
# CORE AI FUNCTION
# Takes an input video path, runs YOLO on every frame, draws
# boxes, writes the annotated video to disk, and returns stats.
# ─────────────────────────────────────────────────────────────
def run_yolo_on_video(input_path, output_raw_path, job_id):
    """Process video frames with YOLOv8 and write annotated output."""
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {input_path}")

    fps    = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Optimization: Downscale huge videos (e.g. 4K) to 720p for massive speedups
    MAX_WIDTH = 1280
    if width > MAX_WIDTH:
        ratio = MAX_WIDTH / float(width)
        width = MAX_WIDTH
        height = int(height * ratio)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(output_raw_path, fourcc, fps, (width, height))

    safe_total = 0
    viol_total = 0
    frame_idx  = 0

    # Optimization: Process YOLO on every 3rd frame, use cached boxes for the skipped frames
    skip_interval = 3
    cached_boxes = []
    
    recognized_faces = [] # list of dicts: {"cx", "cy", "name", "last_scan_frame"}
    
    def get_cached_face(cx, cy):
        best_dist = FACE_MATCH_RADIUS
        best_entry = None
        for entry in recognized_faces:
            if entry.get("last_seen_frame") == frame_idx:
                continue # Already claimed by another bounding box in this frame!
                
            dist = abs(entry["cx"] - cx) + abs(entry["cy"] - cy)
            if dist < best_dist:
                best_dist = dist
                best_entry = entry
        
        if best_entry:
            best_entry["cx"] = cx
            best_entry["cy"] = cy
            best_entry["last_seen_frame"] = frame_idx
            return best_entry["name"], best_entry.get("last_scan_frame", 0)
        return "", -999
        
    def update_face_cache(cx, cy, name, is_scan_attempt=False):
        for entry in recognized_faces:
            dist = abs(entry["cx"] - cx) + abs(entry["cy"] - cy)
            if dist < FACE_MATCH_RADIUS:
                if not is_scan_attempt:
                    entry["name"] = name
                entry["cx"] = cx
                entry["cy"] = cy
                entry["last_scan_frame"] = frame_idx
                entry["last_seen_frame"] = frame_idx
                return
        recognized_faces.append({
            "cx": cx, "cy": cy, "name": name, 
            "last_scan_frame": frame_idx, "last_seen_frame": frame_idx
        })

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame.shape[1] > MAX_WIDTH:
            frame = cv2.resize(frame, (width, height))

        # Only run heavy YOLO inference every `skip_interval` frames
        if frame_idx % skip_interval == 0:
            results = yolo_model(
                frame, imgsz=480, conf=0.15, iou=0.7,
                agnostic_nms=True, device=DEVICE,
                verbose=False
            )
            
            cached_boxes = []
            frame_safe_count = 0
            frame_viol_count = 0
            
            for result in results:
                for box in result.boxes:
                    cls_name = yolo_model.names[int(box.cls)]
                    conf_val = float(box.conf)
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    is_viol = cls_name in VIOLATIONS
                    is_head = cls_name in ["Person", "NO-Hardhat", "Hardhat", "Mask", "NO-Mask"]
                    
                    if is_viol:
                        frame_viol_count += 1
                        color = COLOR_VIOLATION
                    else:
                        frame_safe_count += 1
                        color = COLOR_SAFE
                        
                    worker_id = ""
                    if is_head:
                        cx = (x1 + x2) // 2
                        cy = (y1 + y2) // 2
                        cached_name, last_scan_frame = get_cached_face(cx, cy)
                        
                        if cached_name in ["", "Unknown Person"] and (frame_idx - last_scan_frame) > FACE_SCAN_COOLDOWN:
                            h, w = frame.shape[:2]
                            padding = 60
                            px1, py1 = max(0, x1 - padding), max(0, y1 - padding)
                            px2, py2 = min(w, x2 + padding), min(h, y2 + padding)
                            
                            crop = frame[py1:py2, px1:px2]
                            if crop.size > 0:
                                rgb_img = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                                max_width = 150
                                if rgb_img.shape[1] > max_width:
                                    ratio = max_width / rgb_img.shape[1]
                                    rgb_img = cv2.resize(rgb_img, (max_width, int(rgb_img.shape[0] * ratio)))
                                
                                locs = face_recognition.face_locations(rgb_img, model="hog")
                                if locs:
                                    encs = face_recognition.face_encodings(rgb_img, locs)
                                    if encs and len(KNOWN_ENCODINGS) > 0:
                                        dists = face_recognition.face_distance(KNOWN_ENCODINGS, encs[0])
                                        if len(dists) > 0:
                                            best_idx = np.argmin(dists)
                                            if dists[best_idx] < 0.45:
                                                cached_name = KNOWN_NAMES[best_idx]
                                                update_face_cache(cx, cy, cached_name)
                                                print(f"[FACE] Recognized offline: {cached_name}")
                                            else:
                                                update_face_cache(cx, cy, "Unknown Person")
                                else:
                                    update_face_cache(cx, cy, cached_name, is_scan_attempt=True)
                        
                        worker_id = cached_name
                        
                    cached_boxes.append((x1, y1, x2, y2, cls_name, conf_val, color, worker_id))
            
            safe_total += frame_safe_count
            viol_total += frame_viol_count

        # Draw bounding boxes (either fresh or cached)
        frame_viol_detected = False
        for (x1, y1, x2, y2, cls_name, conf_val, color, worker_id) in cached_boxes:
            if color == COLOR_VIOLATION:
                frame_viol_detected = True
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = f"{cls_name} {conf_val:.2f}"
            if worker_id:
                label += f" - {worker_id}"
                
            (tw, th), _ = cv2.getTextSize(label, FONT, 0.55, 1)
            cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
            cv2.putText(frame, label, (x1 + 2, y1 - 4), FONT, 0.55, (0, 0, 0), 1, cv2.LINE_AA)

        # Violation banner at the bottom
        if frame_viol_detected:
            cv2.rectangle(frame, (0, height - 40), (width, height), COLOR_VIOLATION, -1)
            cv2.putText(frame, "  !! VIOLATION DETECTED !!", (10, height - 12), FONT, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        else:
            cv2.rectangle(frame, (0, height - 40), (width, height), COLOR_SAFE, -1)
            cv2.putText(frame, "  ALL PPE OK", (10, height - 12), FONT, 0.7, (0, 0, 0), 2, cv2.LINE_AA)

        writer.write(frame)
        frame_idx += 1

        # Update progress percentage
        if total > 0 and frame_idx % 5 == 0:
            progress = int((frame_idx / total) * 100)
            with jobs_lock:
                if job_id in jobs:
                    jobs[job_id]['progress'] = progress

    cap.release()
    writer.release()
    return safe_total, viol_total, fps


def convert_to_web_mp4(raw_path, final_path):
    """Re-encode raw OpenCV output to web-safe H.264 MP4 using FFmpeg."""
    import subprocess
    cmd = [
        FFMPEG_PATH, '-y',
        '-i', raw_path,
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '28',
        '-movflags', '+faststart',
        '-an',
        final_path
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr.decode(errors='ignore')}")


def process_video_async(job_id, input_path, job_name):
    """Background thread: load YOLO → run inference → unload YOLO → convert."""
    start_time   = time.time()
    raw_output   = os.path.join(OUTPUT_DIR, f"{job_id}_raw.mp4")
    final_output = os.path.join(OUTPUT_DIR, f"{job_id}_annotated.mp4")

    try:
        with jobs_lock:
            jobs[job_id]['status'] = 'loading_model'

        # ── STEP 1: Load the model (only for this job) ──────────
        load_model()

        with jobs_lock:
            jobs[job_id]['status'] = 'processing'

        # ── STEP 2: Run YOLO on every frame ─────────────────────
        safe_count, viol_count, fps = run_yolo_on_video(input_path, raw_output, job_id)

        # ── STEP 3: Unload the model immediately after inference ─
        unload_model()

        with jobs_lock:
            jobs[job_id]['status'] = 'converting'
            jobs[job_id]['progress'] = 99

        # ── STEP 4: Convert raw output to H.264 MP4 ─────────────
        convert_to_web_mp4(raw_output, final_output)

        # Clean up raw file and uploaded input
        for p in [raw_output, input_path]:
            try:
                if os.path.exists(p): os.remove(p)
            except: pass

        elapsed = round(time.time() - start_time, 1)

        with jobs_lock:
            jobs[job_id].update({
                'status': 'done',
                'progress': 100,
                'result': {
                    'safe_count': safe_count,
                    'viol_count': viol_count,
                    'processing_time_sec': elapsed,
                    'processed_video_url': f"{BASE_URL}/video/outputs/{job_id}_annotated.mp4",
                    'download_filename': f"{job_name}_annotated.mp4"
                }
            })
        print(f"[DONE] Job {job_id}: safe={safe_count}, violations={viol_count}, time={elapsed}s")

    except Exception as e:
        traceback.print_exc()
        # Make sure model is unloaded even if something crashed mid-way
        unload_model()
        with jobs_lock:
            jobs[job_id].update({
                'status': 'error',
                'error': str(e)
            })
        # Cleanup files on failure
        for p in [raw_output, final_output, input_path]:
            try:
                if os.path.exists(p): os.remove(p)
            except: pass


# ─────────────────────────────────────────────────────────────
# API ROUTES
# ─────────────────────────────────────────────────────────────

# RULE 1 - THE ROUTER: Upload a video and start processing
@app.route('/api/process-video', methods=['POST'])
def process_video():

    # RULE 2 - THE BOUNCER: Validate the incoming request
    if 'video' not in request.files:
        return jsonify({"status": "error", "message": "No video file received. Label your file 'video'."}), 400

    video_file = request.files['video']
    if video_file.filename == '':
        return jsonify({"status": "error", "message": "Empty filename received."}), 400

    # Only allow video files
    allowed = {'.mp4', '.avi', '.mov', '.mkv', '.wmv'}
    ext = os.path.splitext(video_file.filename)[1].lower()
    if ext not in allowed:
        return jsonify({"status": "error", "message": f"File type '{ext}' not supported. Use MP4, AVI, MOV, MKV, or WMV."}), 400

    # RULE 3 - BUSINESS LOGIC: Save file & kick off async processing
    job_id   = str(uuid.uuid4())[:8]
    job_name = os.path.splitext(video_file.filename)[0]
    save_path = os.path.join(UPLOAD_DIR, f"{job_id}_input{ext}")
    video_file.save(save_path)
    print(f"[UPLOAD] Job {job_id} received: {video_file.filename} → {save_path}")

    with jobs_lock:
        jobs[job_id] = {
            'status': 'queued',
            'progress': 0,
            'result': None,
            'error': None
        }

    thread = threading.Thread(
        target=process_video_async,
        args=(job_id, save_path, job_name),
        daemon=True
    )
    thread.start()

    # RULE 4 - THE FORMATTER: Return job ID immediately so frontend can poll
    return jsonify({
        "status": "queued",
        "job_id": job_id,
        "message": "Video received! Processing started. Poll /api/status/<job_id> for updates."
    }), 202


# Status polling endpoint
@app.route('/api/status/<job_id>', methods=['GET'])
def get_status(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return jsonify({"status": "error", "message": "Job not found."}), 404

        response = {
            "status": job['status'],
            "progress": job.get('progress', 0)
        }
        if job['status'] == 'done':
            response.update(job['result'])
        elif job['status'] == 'error':
            response['message'] = job.get('error', 'Unknown error')

    return jsonify(response)


# Serve the processed annotated video files
@app.route('/outputs/<filename>')
def serve_output(filename):
    return send_from_directory(OUTPUT_DIR, filename)


# Health check
@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "port": PORT,
        "model": MODEL_PATH,
        "device": str(DEVICE)
    })


# ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 55)
    print(f"🎬 Video Processor API — http://0.0.0.0:{PORT}")
    print(f"   POST /api/process-video   → Upload & analyze")
    print(f"   GET  /api/status/<job_id> → Poll progress")
    print(f"   GET  /outputs/<filename>  → Download result")
    print("=" * 55)
    app.run(host='0.0.0.0', port=PORT, threaded=True)
