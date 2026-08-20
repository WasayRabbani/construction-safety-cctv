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
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from ultralytics import YOLO
import torch

try:
    import face_recognition
except ImportError:
    pass
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

# Absolute path to employees folder so DeepFace always finds it regardless of where the script is launched from
EMPLOYEES_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'employees')

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

print(f"[INFO] Loading YOLO model: {MODEL_PATH}")
yolo_model = YOLO(MODEL_PATH)
yolo_model.overrides['verbose'] = False

global_frame = None
latest_detections = []
metrics = {
    "safe_count": 0,
    "viol_count": 0,
    "current_fps": 0.0
}

# ── PER-PERSON FACE TRACKING ──────────────────────────────────────────────────
face_recognition_active = False
recognized_faces = []  # [{"cx": int, "cy": int, "name": str, "time": float}]
FACE_CACHE_TIMEOUT = 5.0   # seconds before a cached identity expires
FACE_MATCH_RADIUS  = 150   # pixels — max distance to reuse a cached name

def find_cached_name(cx, cy):
    """Find the closest cached identity near pixel position (cx, cy)."""
    now = time.time()
    best_name = "Unknown"
    best_dist = FACE_MATCH_RADIUS
    for entry in recognized_faces:
        if now - entry["time"] > FACE_CACHE_TIMEOUT:
            continue
        dist = abs(entry["cx"] - cx) + abs(entry["cy"] - cy)
        if dist < best_dist:
            best_dist = dist
            best_name = entry["name"]
    return best_name

def update_face_cache(cx, cy, name):
    """Insert or update a cached identity at pixel position (cx, cy)."""
    now = time.time()
    for entry in recognized_faces:
        dist = abs(entry["cx"] - cx) + abs(entry["cy"] - cy)
        if dist < FACE_MATCH_RADIUS:
            entry["name"] = name
            entry["cx"] = cx
            entry["cy"] = cy
            entry["time"] = now
            return
    recognized_faces.append({"cx": cx, "cy": cy, "name": name, "time": now})
    # Purge stale entries
    recognized_faces[:] = [e for e in recognized_faces if now - e["time"] < FACE_CACHE_TIMEOUT * 2]

def run_face_recognition(crop_img, cx, cy):
    global face_recognition_active
    try:
        if 'face_recognition' not in globals():
            return
            
        rgb_img = cv2.cvtColor(crop_img, cv2.COLOR_BGR2RGB)
        
        face_locations = face_recognition.face_locations(rgb_img, model="hog")
        if face_locations:
            unknown_encodings = face_recognition.face_encodings(rgb_img, face_locations)
            if unknown_encodings and len(KNOWN_ENCODINGS) > 0:
                distances = face_recognition.face_distance(KNOWN_ENCODINGS, unknown_encodings[0])
                if len(distances) > 0:
                    best_match_index = np.argmin(distances)
                    if distances[best_match_index] < 0.50:
                        worker_id = KNOWN_NAMES[best_match_index]
                        update_face_cache(cx, cy, worker_id)
                        print(f"[FACE] Recognized: {worker_id}")
                    else:
                        update_face_cache(cx, cy, "Unknown")
    except Exception as e:
        print("[WARN] Face Recognition Thread Error:", e)
    finally:
        face_recognition_active = False

def background_ai_worker():
    global global_frame, latest_detections, metrics, face_recognition_active
    global KNOWN_ENCODINGS, KNOWN_NAMES
    
    total_images = 0
    start_time = time.time()
    print(f"🔄 Initializing Employee Database into Memory...")
    
    try:
        for root, dirs, files in os.walk(EMPLOYEES_DB):
            for f in files:
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    total_images += 1
                    path = os.path.join(root, f)
                    worker_id = os.path.basename(root)
                    try:
                        if 'face_recognition' in globals():
                            img = cv2.imread(path)
                            if img is not None:
                                rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                                encodings = face_recognition.face_encodings(rgb_img)
                                if len(encodings) > 0:
                                    KNOWN_ENCODINGS.append(encodings[0])
                                    KNOWN_NAMES.append(worker_id)
                    except:
                        pass
        elapsed = time.time() - start_time
        print(f"✅ SYSTEM READY: PPE Model and Face Database ({total_images} employees) loaded in {elapsed:.2f}s.")
        print(f"🚀 Monitoring is now active on http://127.0.0.1:{PORT}")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[WARN] Database pre-build issue ({elapsed:.1f}s): {e}")
        print(f"[INFO] Will attempt to build cache on first face scan instead.")

    while True:
        if global_frame is None:
            time.sleep(0.05)
            continue

        frame_copy = global_frame.copy()

        try:
            # 1. Run YOLO (Extreme sensitivity mode)
            # device=DEVICE : Automatically uses GPU if available
            # half=True : Use FP16 for much faster GPU inference
            # imgsz=640 : Standard YOLO resolution, extremely fast, stops the CPU/GPU from lagging the rest of the stream
            # conf=0.15 : Balanced confidence for surveillance
            results = yolo_model(frame_copy, imgsz=640,
                                 conf=0.15, iou=0.7, agnostic_nms=True, 
                                 device=DEVICE, half=(DEVICE == 0), verbose=False)

            new_detections = []
            safe_cnt = 0
            viol_cnt = 0
            
            # For debugging: collect what we found this frame
            found_classes = []

            for result in results:
                for box in result.boxes:
                    cls_name = yolo_model.names[int(box.cls)]
                    conf_val = float(box.conf)
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    
                    found_classes.append(cls_name)

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

                    if is_head and not face_recognition_active:
                        cached = find_cached_name(box_cx, box_cy)
                        if cached == "Unknown":
                            # Only scan faces we haven't identified yet
                            # Increase padding significantly so hats don't cut off the face
                            h, w = frame_copy.shape[:2]
                            padding = 60
                            px1, py1 = max(0, x1 - padding), max(0, y1 - padding)
                            px2, py2 = min(w, x2 + padding), min(h, y2 + padding)

                            crop = frame_copy[py1:py2, px1:px2]
                            if crop.size > 0:
                                face_recognition_active = True
                                threading.Thread(target=run_face_recognition, args=(
                                    crop, box_cx, box_cy), daemon=True).start()

                    # Each head box gets its own name from the spatial cache
                    name_to_display = find_cached_name(box_cx, box_cy) if is_head else ""

                    new_detections.append(
                        (cls_name, conf_val, x1, y1, x2, y2, is_viol, name_to_display))

            # detections logged only if needed for debugging

            # Atomic update for thread safety
            latest_detections = new_detections
            metrics["safe_count"] = safe_cnt
            metrics["viol_count"] = viol_cnt

        except Exception as e:
            print("[ERROR] AI Thread Exception:", e)
            traceback.print_exc()
            time.sleep(1)  # Prevent tight crash loop

        # Give CPU a breather. Targeting ~10-15 FPS for AI processing.
        time.sleep(0.05)



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


def generate_frames():
    global global_frame, latest_detections, metrics

    fps_deque = collections.deque(maxlen=30)
    prev_time = time.time()

    while True:
        if global_frame is None:
            time.sleep(0.05)
            continue

        frame = global_frame.copy()
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

        # Broadcast immediately! JPEG quality 95 provides crystal clear image
        ret, buffer = cv2.imencode(
            '.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        if ret:
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

        # Minimal sleep so we yield thread control but stream as fast as possible (up to 100 FPS)
        time.sleep(0.01)




@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start_camera', methods=['POST'])
def start_camera():
    global CAMERA_ACTIVE
    CAMERA_ACTIVE = True
    print("[INFO] Camera started by frontend.")
    return jsonify({"status": "ok"})

@app.route('/stop_camera', methods=['POST'])
def stop_camera():
    global CAMERA_ACTIVE
    CAMERA_ACTIVE = False
    print("[INFO] Camera stopped by frontend (Tab hidden/closed).")
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
