import os
# Prevent TensorFlow (DeepFace) from hugging all VRAM, leaving space for PyTorch (YOLO)
os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'
import cv2
import time
import collections
import threading
import traceback
import subprocess
import numpy as np
import requests
from PIL import Image
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from ultralytics import YOLO
import torch

# ── FACE RECOGNITION BACKEND ─────────────────────────────────────────────────
# Tries dlib/face_recognition first (fast, for local use).
# Falls back to facenet-pytorch (no compilation required, for cloud/HF).
try:
    import face_recognition
    FACE_BACKEND = 'dlib'
    print("[INFO] Face backend: dlib/face_recognition (local/fast)")
except ImportError:
    try:
        from facenet_pytorch import MTCNN, InceptionResnetV1
        _mtcnn = MTCNN(image_size=160, margin=20, keep_all=False, device='cpu')
        _resnet = InceptionResnetV1(pretrained='vggface2').eval()
        FACE_BACKEND = 'facenet'
        print("[INFO] Face backend: facenet-pytorch (cloud mode)")
    except ImportError:
        FACE_BACKEND = None
        print("[WARN] No face recognition library found. Face ID disabled.")
import imageio_ffmpeg
# ── DEVICE DETECTION (GPU/CPU) ────────────────────────────────────────────────
if torch.cuda.is_available():
    DEVICE = 0
    torch.backends.cudnn.benchmark = True  # Optimize for fixed input sizes
    print(f"✅ GPU DETECTED: {torch.cuda.get_device_name(0)}. Using GPU for AI.")
else:
    DEVICE = 'cpu'
    print("ℹ️ NO GPU DETECTED. Using CPU (this may be slower).")

MODEL_PATH = 'best.pt'
PORT = 5001
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

# URL of the Node.js backend - reads from environment variable for cloud support
BACKEND_URL = os.environ.get('BACKEND_URL', 'http://localhost:3000')

# IMOU CAMERA CONFIGURATION
# Replace the URL below with your actual camera RTSP link
# Format: rtsp://admin:PASSWORD@IP_ADDRESS:554/cam/realmonitor?channel=1&subtype=0
IMOU_CAMERA_URL = "rtsp://admin:L2C9A3C5@192.168.137.142:554/cam/realmonitor?channel=1&subtype=0"

# --- CAMERA SELECTION --- 
#   0 : Default Built-in Laptop Webcam
#   1 : External USB Webcam
CAMERA_SOURCE = 0
CAMERA_ACTIVE = False

VIOLATIONS = {
    'NO-Hardhat', 'NO-Gloves', 'NO-Mask',
    'NO-Goggles', 'NO-Safety Vest', 'Fall-Detected'
}

COLOR_VIOLATION = (0, 0, 255)
COLOR_SAFE = (0, 200, 80)
COLOR_INFO = (255, 255, 255)
FONT = cv2.FONT_HERSHEY_SIMPLEX

# ── INITIALIZATION ────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# Silence Flask logging for a cleaner terminal
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# ── LAZY MODEL LOADING ────────────────────────────────────────────────────────
# YOLO model is NOT loaded at startup. It loads when the user opens the CCTV
# tab (start_camera) and unloads when they leave (stop_camera) to free RAM/GPU.
yolo_model = None
yolo_model_lock = threading.Lock()

def load_yolo_model():
    global yolo_model
    with yolo_model_lock:
        if yolo_model is None:
            print(f"[INFO] Loading YOLO model: {MODEL_PATH}")
            yolo_model = YOLO(MODEL_PATH)
            yolo_model.overrides['verbose'] = False
            print(f"[INFO] YOLO model loaded and ready.")

def unload_yolo_model():
    global yolo_model
    with yolo_model_lock:
        if yolo_model is not None:
            print("[INFO] Unloading YOLO model to free memory…")
            del yolo_model
            yolo_model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("[INFO] YOLO model unloaded. GPU/RAM freed.")

global_frame = None
latest_detections = []
metrics = {
    "safe_count": 0,
    "viol_count": 0,
    "current_fps": 0.0
}

KNOWN_ENCODINGS = []
KNOWN_NAMES = []

# ── PER-PERSON FACE TRACKING ──────────────────────────────────────────────────
face_recognition_active = False
recognized_faces = []  # [{"cx": int, "cy": int, "name": str, "time": float, "last_scan": float}]
FACE_CACHE_TIMEOUT = 5.0   # seconds before a cached identity expires completely
FACE_SCAN_COOLDOWN = 1.5   # seconds to wait before trying to scan the SAME person again if failed
FACE_MATCH_RADIUS  = 150   # pixels — max distance to reuse a cached name

def get_cached_face(cx, cy):
    """Find the closest cached identity near pixel position (cx, cy). Returns (name, last_scan_time)"""
    now = time.time()
    best_dist = FACE_MATCH_RADIUS
    best_entry = None
    for entry in recognized_faces:
        if now - entry["time"] > FACE_CACHE_TIMEOUT:
            continue
        dist = abs(entry["cx"] - cx) + abs(entry["cy"] - cy)
        if dist < best_dist:
            best_dist = dist
            best_entry = entry
    
    if best_entry:
        return best_entry["name"], best_entry.get("last_scan", 0)
    return "", 0

def update_face_cache(cx, cy, name, is_scan_attempt=False):
    """Insert or update a cached identity. If is_scan_attempt is True, just updates last_scan time."""
    now = time.time()
    for entry in recognized_faces:
        dist = abs(entry["cx"] - cx) + abs(entry["cy"] - cy)
        if dist < FACE_MATCH_RADIUS:
            if not is_scan_attempt:
                entry["name"] = name
                entry["cx"] = cx
                entry["cy"] = cy
                entry["time"] = now
            entry["last_scan"] = now
            return
            
    recognized_faces.append({"cx": cx, "cy": cy, "name": name, "time": now, "last_scan": now})
    # Purge stale entries
    recognized_faces[:] = [e for e in recognized_faces if now - e["time"] < FACE_CACHE_TIMEOUT * 2]

def _get_facenet_embedding(rgb_img):
    """Use facenet-pytorch to extract a 512-d face embedding from an RGB image."""
    try:
        img_pil = Image.fromarray(rgb_img)
        face_tensor = _mtcnn(img_pil)
        if face_tensor is None:
            return None
        with torch.no_grad():
            embedding = _resnet(face_tensor.unsqueeze(0))
        return embedding.numpy().flatten()
    except Exception:
        return None

def run_face_recognition(crop_img, cx, cy):
    global face_recognition_active
    try:
        if FACE_BACKEND is None:
            return

        rgb_img = cv2.cvtColor(crop_img, cv2.COLOR_BGR2RGB)

        if FACE_BACKEND == 'dlib':
            # ── Local mode: fast HOG-based dlib ──────────────────────────────
            max_width = 150
            if rgb_img.shape[1] > max_width:
                ratio = max_width / rgb_img.shape[1]
                rgb_img = cv2.resize(rgb_img, (max_width, int(rgb_img.shape[0] * ratio)))

            face_locations = face_recognition.face_locations(rgb_img, model="hog")
            if face_locations:
                unknown_encodings = face_recognition.face_encodings(rgb_img, face_locations)
                if unknown_encodings and len(KNOWN_ENCODINGS) > 0:
                    distances = face_recognition.face_distance(KNOWN_ENCODINGS, unknown_encodings[0])
                    if len(distances) > 0:
                        best_match_index = np.argmin(distances)
                        if distances[best_match_index] < 0.50:
                            update_face_cache(cx, cy, KNOWN_NAMES[best_match_index])
                            print(f"[FACE] Recognized: {KNOWN_NAMES[best_match_index]}")
                        else:
                            update_face_cache(cx, cy, "Unknown Person")

        elif FACE_BACKEND == 'facenet':
            # ── Cloud mode: facenet-pytorch ───────────────────────────────────
            embedding = _get_facenet_embedding(rgb_img)
            if embedding is not None and len(KNOWN_ENCODINGS) > 0:
                # Cosine similarity comparison
                sims = [
                    float(np.dot(embedding, k) / (np.linalg.norm(embedding) * np.linalg.norm(k) + 1e-9))
                    for k in KNOWN_ENCODINGS
                ]
                best_idx = int(np.argmax(sims))
                if sims[best_idx] > 0.75:   # threshold for facenet cosine sim
                    update_face_cache(cx, cy, KNOWN_NAMES[best_idx])
                    print(f"[FACE] Recognized (facenet): {KNOWN_NAMES[best_idx]}")
                else:
                    update_face_cache(cx, cy, "Unknown Person")

    except Exception as e:
        print("[WARN] Face Recognition Thread Error:", e)
    finally:
        face_recognition_active = False

def background_ai_worker():
    global global_frame, latest_detections, metrics, face_recognition_active
    global KNOWN_ENCODINGS, KNOWN_NAMES
    
    total_images = 0
    db_loaded = False
    ai_frame_counter = 0
    AI_SKIP_FRAMES   = 2   # Run YOLO on every 2nd frame

    while True:
        if global_frame is None or not CAMERA_ACTIVE:
            time.sleep(0.1)
            continue

        if not db_loaded:
            start_time = time.time()
            print(f"🔄 Loading Employee Face Database from Cloud...")
            try:
                # --- CORE LOGIC: Fetch face photos from backend API ---
                resp = requests.get(f"{BACKEND_URL}/api/workers/face-database", timeout=15)
                workers_data = resp.json()
                
                for entry in workers_data:
                    worker_id = entry.get('worker_id')
                    photo_url  = entry.get('photo_url')
                    if not worker_id or not photo_url:
                        continue
                    try:
                        if FACE_BACKEND == 'dlib':
                            img_bytes = requests.get(photo_url, timeout=10).content
                            img_array = np.frombuffer(img_bytes, np.uint8)
                            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                            if img is not None:
                                rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                                encodings = face_recognition.face_encodings(rgb_img)
                                if len(encodings) > 0:
                                    KNOWN_ENCODINGS.append(encodings[0])
                                    KNOWN_NAMES.append(worker_id)
                                    total_images += 1
                        elif FACE_BACKEND == 'facenet':
                            img_bytes = requests.get(photo_url, timeout=10).content
                            img_array = np.frombuffer(img_bytes, np.uint8)
                            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                            if img is not None:
                                rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                                embedding = _get_facenet_embedding(rgb_img)
                                if embedding is not None:
                                    KNOWN_ENCODINGS.append(embedding)
                                    KNOWN_NAMES.append(worker_id)
                                    total_images += 1
                    except Exception as e:
                        print(f"[WARN] Could not encode photo for {worker_id}: {e}")
                
                elapsed = time.time() - start_time
                print(f"✅ Face Database Ready: {total_images} photos loaded from cloud in {elapsed:.2f}s.")
            except Exception as e:
                print(f"[WARN] Could not load face database from API: {e}")
                print(f"[INFO] Face recognition will be disabled until backend is reachable.")
            db_loaded = True

        # Skip AI processing if model isn't loaded yet
        if yolo_model is None:
            time.sleep(0.1)
            continue

        # OPTION C: Skip frames — only run YOLO on every Nth frame
        ai_frame_counter += 1
        if ai_frame_counter % AI_SKIP_FRAMES != 0:
            time.sleep(0.01)
            continue

        frame_copy = global_frame.copy()

        try:
            # 1. Run YOLO
            results = yolo_model(frame_copy, imgsz=640,
                                 conf=0.15, iou=0.7, agnostic_nms=True, 
                                 device=DEVICE, verbose=False)

            new_detections = []
            safe_cnt = 0
            viol_cnt = 0

            for result in results:
                for box in result.boxes:
                    cls_name = yolo_model.names[int(box.cls)]
                    conf_val = float(box.conf)
                    x1, y1, x2, y2 = map(int, box.xyxy[0])

                    is_viol = cls_name in VIOLATIONS
                    if is_viol:
                        viol_cnt += 1
                    else:
                        safe_cnt += 1

                    is_head = cls_name in [
                        "Person", "NO-Hardhat", "Hardhat", "Mask", "NO-Mask"]

                    # 2. Per-person Face Recognition
                    box_cx = (x1 + x2) // 2
                    box_cy = (y1 + y2) // 2
                    
                    cached_name, last_scan = get_cached_face(box_cx, box_cy)
                    name_to_display = cached_name if is_head and cached_name else ""

                    if is_head and not face_recognition_active:
                        # Only scan if we don't know who they are, AND we haven't tried recently
                        if cached_name in ["", "Unknown Person"] and (time.time() - last_scan) > FACE_SCAN_COOLDOWN:
                            h, w = frame_copy.shape[:2]
                            padding = 60
                            px1, py1 = max(0, x1 - padding), max(0, y1 - padding)
                            px2, py2 = min(w, x2 + padding), min(h, y2 + padding)

                            crop = frame_copy[py1:py2, px1:px2]
                            if crop.size > 0:
                                face_recognition_active = True
                                update_face_cache(box_cx, box_cy, cached_name, is_scan_attempt=True) # mark as scanned to trigger cooldown
                                threading.Thread(target=run_face_recognition, args=(
                                    crop, box_cx, box_cy), daemon=True).start()

                    new_detections.append(
                        (cls_name, conf_val, x1, y1, x2, y2, is_viol, name_to_display))

            # Atomic update for thread safety
            latest_detections = new_detections
            metrics["safe_count"] = safe_cnt
            metrics["viol_count"] = viol_cnt

        except Exception as e:
            print("[ERROR] AI Thread Exception:", e)
            traceback.print_exc()
            time.sleep(1)  # Prevent tight crash loop



ai_thread = threading.Thread(target=background_ai_worker, daemon=True)
ai_thread.start()




def camera_worker():
    global global_frame, CAMERA_SOURCE, CAMERA_ACTIVE

    current_source = None
    cap = None
    pipe = None

    fail_count = 0
    frame_size = 0
    frame_width = 0
    frame_height = 0
    is_rtsp = False

    while True:
        if not CAMERA_ACTIVE:
            if cap:
                cap.release()
                cap = None
            if pipe:
                try: pipe.kill()
                except: pass
                pipe = None
            current_source = None
            
            global_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
            cv2.putText(global_frame, "CAMERA STANDBY (TAB INACTIVE)", (350, 360), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (150, 150, 150), 2)
            time.sleep(0.5)
            continue
            
        if current_source != CAMERA_SOURCE or (pipe is None and cap is None):
            # If we have no active stream, wait a bit and try to (re)connect
            if current_source != CAMERA_SOURCE:
                # Switching cameras - clear frame to a blank connecting screen
                global_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
                cv2.putText(global_frame, "CONNECTING TO CAMERA...", (400, 360), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
            elif pipe is None and cap is None and current_source is not None:
                # Camera is offline / failing to connect
                global_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
                cv2.putText(global_frame, "CAMERA OFFLINE", (480, 360), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
                print(f"[INFO] No active stream. Retrying connection to {CAMERA_SOURCE} in 2s...")
                for _ in range(20):
                    if current_source != CAMERA_SOURCE:
                        break
                    time.sleep(0.1)

            # Cleanup old connection
            if cap:
                cap.release()
                cap = None
            if pipe:
                try: pipe.kill()
                except: pass
                pipe = None

            current_source = CAMERA_SOURCE
            is_rtsp = isinstance(current_source, str) and current_source.startswith("rtsp")

            if is_rtsp:
                # 1280x720 Native Resolution for better detail at a distance
                frame_width, frame_height = 1280, 720
                frame_size = frame_width * frame_height * 3

                ffmpeg_cmd = [
                    FFMPEG_PATH,
                    '-loglevel', 'error',
                    '-rtsp_transport', 'tcp',
                    '-timeout', '5000000',
                    '-fflags', 'nobuffer',
                    '-flags', 'low_delay',
                    '-nostdin',
                    '-i', current_source,
                    '-vf', 'scale=1280:720',
                    '-f', 'image2pipe',
                    '-pix_fmt', 'bgr24',
                    '-vcodec', 'rawvideo',
                    '-an', '-'
                ]

                print(f"✅ CRYSTAL-SMOOTH FEED ACTIVE: FFmpeg is processing the camera stream.")
                try:
                    import queue
                    frame_queue = queue.Queue(maxsize=1)
                    pipe = subprocess.Popen(
                        ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=frame_size * 2)
                    
                    # Background thread to log FFmpeg errors
                    def logger():
                        while pipe and pipe.poll() is None:
                            line = pipe.stderr.readline()
                            if line:
                                print(f"[FFMPEG] {line.decode(errors='ignore').strip()}")
                            else: break
                    threading.Thread(target=logger, daemon=True).start()

                    # Background thread to read from pipe
                    def reader():
                        while pipe and pipe.poll() is None:
                            try:
                                data = pipe.stdout.read(frame_size)
                                if not data or len(data) != frame_size: break
                                if frame_queue.full():
                                    try: frame_queue.get_nowait()
                                    except: pass
                                frame_queue.put(data)
                            except: break
                    threading.Thread(target=reader, daemon=True).start()
                    
                    # Wait longer (5s) for RTSP handshake over hotspot, but allow instant interruption
                    for _ in range(50):
                        if current_source != CAMERA_SOURCE:
                            break
                        time.sleep(0.1)
                    if frame_queue.empty():
                        if pipe.poll() is not None:
                            print(f"[ERROR] FFmpeg crashed on startup.")
                        else:
                            print(f"[WARN] FFmpeg is running but not receiving video. Retrying...")
                            pipe.kill()
                        pipe = None
                        # Removed OpenCV fallback for RTSP to prevent 30-second thread hang when offline
                except Exception as e:
                    print(f"[WARN] FFmpeg Launch Error: {e}.")
                    pipe = None
                    # Removed OpenCV fallback for RTSP to prevent 30-second thread hang
            else:
                print(f"[INFO] Launching Local Webcam Capture (Device {current_source})...")
                # Removed cv2.CAP_DSHOW to prevent Windows hangs and speed up initialization
                cap = cv2.VideoCapture(current_source)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                if not cap.isOpened(): cap = None

        # --- DATA CONSUMPTION ---
        if pipe:
            try:
                # Get the latest frame from queue with a short timeout
                import queue
                raw_image = frame_queue.get(timeout=0.1)
                frame = np.frombuffer(raw_image, dtype='uint8').reshape((frame_height, frame_width, 3)).copy()
                global_frame = frame
            except queue.Empty:
                # If pipe is alive but queue is empty, just wait
                if pipe.poll() is not None:
                    print("[INFO] FFmpeg process ended.")
                    pipe = None
            except Exception as e:
                print(f"[ERROR] Frame processing error: {e}")
                pipe = None

        elif cap and cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                global_frame = frame
            else:
                time.sleep(0.01)
        else:
            time.sleep(0.1)

cam_thread = threading.Thread(target=camera_worker, daemon=True)
cam_thread.start()


# OPTION A: Stream at full camera FPS (30+), overlaying cached AI detections.
# The raw camera frame is always smooth. AI boxes update at their own speed.
def generate_frames():
    global global_frame, latest_detections, metrics

    fps_deque = collections.deque(maxlen=30)
    prev_time = time.time()
    TARGET_FPS = 30
    frame_time = 1.0 / TARGET_FPS

    while True:
        if global_frame is None:
            time.sleep(0.03)
            continue

        frame_start = time.time()

        # Grab the latest raw camera frame (this updates at camera speed, ~30 FPS)
        frame = global_frame.copy()

        # Overlay the CACHED AI detections on top (these update at AI speed)
        current_dets = list(latest_detections)

        for (cls_name, conf_val, x1, y1, x2, y2, is_viol, person_name) in current_dets:
            color = COLOR_VIOLATION if is_viol else COLOR_SAFE

            # Draw Box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Draw Label
            label = f"[{person_name}] {cls_name} {conf_val:.2f}"
            (tw, th), _ = cv2.getTextSize(label, FONT, 0.55, 1)
            cv2.rectangle(frame, (x1, y1-th-8), (x1+tw+4, y1), color, -1)
            cv2.putText(frame, label, (x1+2, y1-4), FONT,
                        0.55, (0, 0, 0), 1, cv2.LINE_AA)

        # FPS Calculation
        now = time.time()
        fps_deque.append(1.0 / max(now - prev_time, 1e-6))
        fps = sum(fps_deque) / len(fps_deque)
        prev_time = now

        # Overlay Metrics
        cv2.putText(frame, f"Stream FPS: {fps:.1f}",
                    (10, 25), FONT, 0.65, COLOR_INFO, 2, cv2.LINE_AA)
        cv2.putText(frame, f"Safe:{metrics['safe_count']}  Violations:{metrics['viol_count']}",
                    (10, 55), FONT, 0.6, COLOR_INFO, 1, cv2.LINE_AA)

        # Bottom Banner
        if metrics['viol_count'] > 0:
            cv2.rectangle(
                frame, (0, frame.shape[0]-40), (frame.shape[1], frame.shape[0]), COLOR_VIOLATION, -1)
            cv2.putText(frame, f"  !! VIOLATION DETECTED: {metrics['viol_count']}",
                        (10, frame.shape[0]-12), FONT, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        else:
            cv2.rectangle(
                frame, (0, frame.shape[0]-40), (frame.shape[1], frame.shape[0]), COLOR_SAFE, -1)
            cv2.putText(frame, "  ALL PPE OK",
                        (10, frame.shape[0]-12), FONT, 0.7, (0, 0, 0), 2, cv2.LINE_AA)

        # Encode JPEG — quality 80 gives crisp image at much smaller size for smoother streaming
        ret, buffer = cv2.imencode(
            '.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if ret:
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

        # Pace the stream to the target FPS for smooth, consistent playback
        elapsed = time.time() - frame_start
        sleep_time = max(0, frame_time - elapsed)
        if sleep_time > 0:
            time.sleep(sleep_time)




@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start_camera', methods=['POST'])
def start_camera():
    global CAMERA_ACTIVE
    # Load YOLO model into memory when user opens CCTV tab
    load_yolo_model()
    CAMERA_ACTIVE = True
    print("[INFO] Camera + AI model started by frontend.")
    return jsonify({"status": "ok"})

@app.route('/stop_camera', methods=['POST'])
def stop_camera():
    global CAMERA_ACTIVE
    CAMERA_ACTIVE = False
    # Unload YOLO model from memory when user leaves CCTV tab
    unload_yolo_model()
    print("[INFO] Camera + AI model stopped (Tab hidden/closed). Resources freed.")
    return jsonify({"status": "ok"})

@app.route('/set_camera', methods=['POST'])
def set_camera():
    global CAMERA_SOURCE
    data = request.get_json()
    source = data.get('source', 0)
    
    if source == 'imou':
        CAMERA_SOURCE = IMOU_CAMERA_URL
    else:
        try:
            CAMERA_SOURCE = int(source)
        except (ValueError, TypeError):
            CAMERA_SOURCE = source
            
    print(f"[INFO] Camera source changed to: {CAMERA_SOURCE}")
    return jsonify({"status": "ok", "camera": source})

@app.route('/get_camera', methods=['GET'])
def get_camera():
    return jsonify({"camera": CAMERA_SOURCE})


if __name__ == '__main__':

    print(f"🚀 Intelligent CCTV Server starting on port {PORT}")

    app.run(host='0.0.0.0', port=PORT, threaded=True)
