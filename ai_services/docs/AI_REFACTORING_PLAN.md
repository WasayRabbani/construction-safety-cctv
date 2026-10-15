# AI Architecture Refactoring & OOP Decomposition Plan

## Overview
Decompose the 3 monolithic service files (`face_api.py`, `intelligent_cctv.py`, `video_processor.py`) into reusable, single-responsibility Object-Oriented Programming (OOP) classes in `ai_services/core/`. The service files in `services/` will become thin Flask HTTP controllers.

---

## 1. Target Directory Architecture

```
ai_services/
│
├── core/                                # Reusable OOP Engines (Domain Logic)
│   ├── __init__.py
│   ├── config.py                        # Centralized paths, constants, device detection
│   ├── ppe_detector.py                  # Class PPEDetector (YOLO model lifecycle & inference)
│   ├── face_engine.py                   # Class FaceEngine (Face encodings, matching, caching)
│   └── camera_stream.py                 # Class CameraStream (Webcam & RTSP/FFmpeg background capture)
│
├── services/                            # Thin HTTP Routing Controllers
│   ├── face_api.py                      # Flask routes for Attendance Web API (< 50 lines)
│   ├── intelligent_cctv.py              # Flask routes for Live CCTV Streaming (< 90 lines)
│   └── video_processor.py               # Flask routes for Offline Video Upload Analysis (< 100 lines)
│
├── app.py                               # Master Server Dispatcher (Port 7860)
└── docs/
    └── AI_REFACTORING_PLAN.md           # This master task document
```

---

## 2. Component Specifications

### Step 1: Configuration Module (`ai_services/core/config.py`)
- **Purpose:** Eliminate hardcoded, repetitive paths and device checks across multiple files.
- **Exports:**
  - `AI_ROOT_DIR`, `MODEL_PATH`, `EMPLOYEES_DIR`, `BACKEND_URL`, `DEFAULT_RTSP_URL`.
  - `DEVICE`: Auto-detects CUDA GPU vs CPU.
  - `VIOLATION_CLASSES`: Standardized set of PPE violation class names.
  - `UI_COLORS`: Standardized BGR tuples (`COLOR_SAFE`, `COLOR_VIOLATION`, `COLOR_CYAN`, `FONT`).

---

### Step 2: YOLO PPE Detector Class (`ai_services/core/ppe_detector.py`)
- **Class:** `PPEDetector`
- **Responsibilities:**
  - Lazy loading and explicit unloading of YOLOv8 model weights with thread locking.
  - `load()`: Loads `best.pt` into GPU/RAM.
  - `unload()`: Deletes model and calls `torch.cuda.empty_cache()` to free memory.
  - `detect(frame, conf=0.35, iou=0.45, imgsz=640)`:
    - Runs inference using `torch.inference_mode()`.
    - Parses predictions into structured DTOs: `(cls_name, confidence, bbox(x1, y1, x2, y2), is_violation, is_head)`.
  - `draw_detection(frame, detection, person_name=None)`: Clean visualization helper.

---

### Step 3: Face Recognition Engine Class (`ai_services/core/face_engine.py`)
- **Class:** `FaceEngine`
- **Responsibilities:**
  - Auto-selects backend: `dlib` (local HOG) with fallback to `facenet-pytorch`.
  - `load_faces(local_dir, backend_url)`:
    - Scans `ai_services/employees/<Worker Name>/` on disk first.
    - Falls back to cloud API `/api/workers/face-database`.
  - `recognize_face(crop_image, threshold=0.50)`:
    - Pre-scales image to max 640px for 4x faster HOG scanning.
    - Computes 128-d or 512-d encodings and compares distance against known faces.
    - Returns: `(status, worker_name, confidence, distance)`.
  - `FaceTracker`: Spatial/temporal bounding box identity cache (5-second TTL, 1.5s cooldown) to prevent repetitive recognition scans.

---

### Step 4: Camera Stream Engine Class (`ai_services/core/camera_stream.py`)
- **Class:** `CameraStream`
- **Responsibilities:**
  - Background daemon thread for continuous frame grabbing.
  - Dual-mode ingest:
    - Local USB / Integrated Webcam via OpenCV `VideoCapture`.
    - IP Camera via low-latency `FFmpeg` subprocess with non-blocking pipe queue.
  - `start()`, `stop()`, `get_frame()`, `set_source(source)`.
  - Zero-lag frame consumption (drops stale frames, returns latest buffer).

---

### Step 5: Refactor Service Controllers (`services/`)
- **`services/face_api.py`:**
  - Initializes `FaceEngine()`.
  - Routes: `POST /recognize`, `POST /load-model`, `POST /unload-model`, `GET /health`.
  - Zero camera or YOLO code.
- **`services/intelligent_cctv.py`:**
  - Composes `CameraStream`, `PPEDetector`, and `FaceEngine`.
  - Single background loop: reads from `CameraStream`, runs `PPEDetector.detect()`, draws overlays.
  - Routes: `GET /video_feed`, `POST /start_camera`, `POST /stop_camera`, `POST /set_camera`, `POST /reload_faces`.
- **`services/video_processor.py`:**
  - Composes `PPEDetector` and `FaceEngine`.
  - Runs frame-by-frame batch processing on uploaded video files.
  - Routes: `POST /api/process-video`, `GET /api/progress/<id>`, `GET /api/download/<filename>`.

---

## 3. Execution Checklist & Order of Work

- [x] **Task 1: Create `ai_services/core/config.py`** [COMPLETED]
  - Centralized paths (`MODEL_PATH`, `EMPLOYEES_DIR`, `UPLOAD_DIR`, `OUTPUT_DIR`).
  - Centralized device detection (`cuda:0` vs `cpu`) and styling constants.
- [x] **Task 2: Create `ai_services/core/ppe_detector.py`** [COMPLETED]
  - Implemented `PPEDetector` class with lazy `load()`, `unload()`, `detect()`, and `draw_overlays()`.
  - Added structured `Detection` dataclass and `torch.inference_mode()` acceleration.
- [x] **Task 3: Create `ai_services/core/face_engine.py`** [COMPLETED]
  - Implemented `FaceEngine` class with dual `dlib` + `facenet-pytorch` backends.
  - Implemented `load_faces()` (local disk scanning with cloud fallback).
  - Implemented `FaceTracker` class for spatial/temporal cooldown caching.
- [x] **Task 4: Create `ai_services/core/camera_stream.py`** [COMPLETED]
  - Implemented `CameraStream` class with background daemon thread.
  - Dual-mode: local webcam via `cv2.VideoCapture` and RTSP via FFmpeg subprocess.
  - Drop-stale-frame queue (maxsize=1) for zero-lag delivery.
  - Full `start()`, `stop()`, `get_frame()`, `set_source()` API with standby/offline frames.
- [x] **Task 5: Refactor `services/face_api.py`** [COMPLETED]
  - Reduced from 160 lines → ~80 lines.
  - All recognition logic delegated to `FaceEngine`.
  - Routes: `POST /recognize`, `POST /load-model`, `POST /unload-model`, `GET /health`.
- [x] **Task 6: Refactor `services/intelligent_cctv.py`** [COMPLETED]
  - Reduced from 718 lines → ~175 lines.
  - Composes `CameraStream`, `PPEDetector`, `FaceEngine` via clean class APIs.
  - AI worker, face scan dispatch, and frame overlay all remain intact but use class methods.
- [x] **Task 7: Refactor `services/video_processor.py`** [COMPLETED]
  - Reduced from 500 lines → ~220 lines.
  - Per-job `PPEDetector` and `FaceEngine` instances: loaded at start, unloaded immediately after.
  - Face tracking uses `FaceTracker` with frame-count-based cooldown.
  - Draw logic delegated to `PPEDetector.draw_overlays()`.
- [x] **Task 8: Updated `app.py` and created `core/__init__.py`** [COMPLETED]
  - `app.py` adds both `services/` and the ai_services root to `sys.path`.
  - `core/__init__.py` created so `from core.xxx import yyy` works as a proper package.

---

## 4. Final Architecture Summary

| File | Lines Before | Lines After | Reduction |
|---|---|---|---|
| `services/face_api.py` | 160 | ~80 | −50% |
| `services/intelligent_cctv.py` | 718 | ~175 | −76% |
| `services/video_processor.py` | 500 | ~220 | −56% |
| `core/config.py` | — | 52 | New |
| `core/ppe_detector.py` | — | 122 | New |
| `core/face_engine.py` | — | 255 | New |
| `core/camera_stream.py` | — | ~210 | New |
