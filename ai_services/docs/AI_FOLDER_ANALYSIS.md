# AI Services — Folder Analysis
> Studied and written after reading every file in this folder.

---

## 1. What Should This Folder Be Called?

**Rename it to `ai_services/`.**

Reason: The folder contains 3 separate AI services (Face Recognition, Live CCTV, Video Processing). Calling it `Face_recognition` only describes one of them. `ai_services/` is what every developer will understand at a glance.

---

## 2. The Big Picture — What This Folder Is

This folder is a **Python microservice cluster**. It runs as a single Flask server on port `7860` and hosts 3 sub-services internally.

```
app.py  (Master Entry Point — Port 7860)
 ├── /face  → face_api.py          (Face Recognition)
 ├── /cctv  → intelligent_cctv.py  (Live PPE CCTV Detection)
 └── /video → video_processor.py   (Offline Video Analysis)
```

Each service can also run **standalone** on its own port for local testing, or be mounted under the master server for cloud/Hugging Face deployment.

---

## 3. File-by-File Breakdown

### `app.py` — The Master Server
- Uses Werkzeug `DispatcherMiddleware` to mount all 3 Flask apps under one server.
- Starts on port `7860` (Hugging Face's required default port).
- Has a HF ZeroGPU compatibility block — harmless on local machines.
- **Doesn't do any AI itself** — just boots up and routes traffic.

---

### `intelligent_cctv.py` — Live CCTV Detection (661 lines — biggest file)

1. **YOLO (PPE Detection):**
   - Uses `best.pt` to detect 6 violations: No Hardhat, No Gloves, No Mask, No Goggles, No Safety Vest, Fall-Detected.
   - **Lazy loads** into RAM/GPU only when user opens the CCTV tab. Unloads when they leave.
   - Runs YOLO on every **2nd frame** (`AI_SKIP_FRAMES = 2`) — half the compute.

2. **Camera Worker (Separate Thread):**
   - Supports webcam (device `0` or `1`) AND RTSP IP cameras.
   - For RTSP uses **FFmpeg subprocess** — way more stable than OpenCV for network cameras.
   - For local webcam uses OpenCV directly.

3. **Face Recognition (Per-Person):**
   - Dual-backend: tries **dlib/face_recognition** first (fast, local), falls back to **facenet-pytorch** (cloud-safe).
   - **Face cache**: once a person is recognized, identity is remembered for 5 seconds so it doesn't scan the same face 30 times/sec.
   - Loads employee face data **from the backend API** (`/api/workers/face-database`) — stays in sync automatically.
   - Runs face recognition in a **daemon thread** so it never blocks the video stream.

4. **Video Streaming:**
   - Streams annotated MJPEG frames at 30 FPS via `/video_feed`.
   - Raw frames stream at 30 FPS; AI boxes overlay at AI speed. Video is always smooth even on slow hardware.

5. **API Routes:**
   - `POST /start_camera` — loads YOLO, starts stream
   - `POST /stop_camera` — unloads YOLO, frees GPU memory
   - `POST /set_camera` — switch between webcam, USB cam, or RTSP
   - `GET /video_feed` — the live MJPEG stream

---

### `face_api.py` — Dedicated Face Recognition API

- A separate simpler Flask service for the **Face Recognition tab** in the frontend.
- Receives a base64-encoded image, runs dlib HOG detection, returns a match result (worker_id + confidence).
- Lazy-loads the face database from the local `employees/` folder on disk.
- Routes: `POST /recognize`, `POST /load-model`, `POST /unload-model`, `GET /health`.

> ⚠️ **Inconsistency:** This uses the local `employees/` folder. `intelligent_cctv.py` uses the backend API. See Issue 1 below.

---

### `video_processor.py` — Offline Video Analysis

- Accepts an uploaded `.mp4` via `POST /api/process-video`.
- Runs YOLO on every **3rd frame** and draws bounding boxes.
- Downscales videos wider than 1280px before processing (saves a lot of time on 4K footage).
- Uses a **job tracker** (`jobs` dict) — processing runs in background, frontend polls for progress.
- Returns a download link to the annotated output video.
- Lazy-loads YOLO only when a video is submitted, unloads when done.

---

### `best.pt` — YOLOv8 Model (52 MB)
- Custom-trained weights for PPE detection.
- This is the "brain" of the entire project.

### `employees/` — Local Face Database
- Used by `face_api.py`.
- Structure: `employees/<worker_id>/<photo.jpg>`

### `recognize.py`, `register.py`, `rename.py`, `cleanup_photos.py`, `check_gpu.py`, `test.py`
- Developer utility scripts — **not part of the running server**.
- `register.py`: adds a new employee face to the local database.
- `recognize.py`: quick CLI test of face recognition.
- `check_gpu.py`: prints CUDA/VRAM info.

### `Dockerfile` + `packages.txt`
- Cloud deployment config for Hugging Face Spaces.

### `PPE_YOLOv8_Colab_(1).ipynb`
- Training notebook — archive/reference only, not deployed.

### `api_contract.md`
- Documents the frontend ↔ video processor interface. Well written.

---

## 4. Efficiency — What's Already Done Right ✅

| Pattern | Where | Benefit |
|---|---|---|
| Lazy model loading | All 3 services | YOLO only in RAM when needed (~500MB saved) |
| Model unloading on tab hide | CCTV + Face API | GPU/RAM freed when user leaves page |
| Frame skipping (every 2nd–3rd frame) | CCTV + Video Processor | 50–67% less YOLO compute |
| Face caching (5s TTL) | CCTV | Recognition runs once, reused for 5s |
| Face scan cooldown (1.5s) | CCTV | Prevents hammering same face |
| Separate AI thread | CCTV | AI never blocks video stream |
| FFmpeg for RTSP | CCTV | Stable, reconnect-capable, low-latency |
| JPEG quality 80 | CCTV streaming | ~20% smaller frames, faster network |
| 1280px max width cap | Video Processor | Prevents 4K from being 4x slower |
| HOG instead of CNN | Face API | 10x faster face detection, runs on any laptop |
| Dual backend (dlib → facenet) | CCTV | Works locally (fast) AND on cloud (no C++ build) |
| `TF_FORCE_GPU_ALLOW_GROWTH` | CCTV | Prevents TensorFlow from locking all VRAM |

**The code is already well-optimized.** No major rewrites needed.

---

## 5. Issues Found (Fix Before Integration)

### Issue 1 — Two Different Face Databases
- `face_api.py` reads from local `employees/` folder.
- `intelligent_cctv.py` fetches from backend API (`/api/workers/face-database`).
- **Risk:** Adding an employee in the backend doesn't update the Face Recognition tab.
- **Fix:** Make `face_api.py` also fetch from the backend API. Local folder becomes dev-only fallback.

### Issue 2 — `best.pt` Path is Relative in `intelligent_cctv.py`
- Line 45: `MODEL_PATH = 'best.pt'` — breaks if run from project root.
- `video_processor.py` correctly uses `os.path.abspath(__file__)`.
- **Fix:** Change to `os.path.join(os.path.dirname(os.path.abspath(__file__)), 'best.pt')`.

### Issue 3 — RTSP Camera Credentials Hardcoded
- Line 55 has a hardcoded RTSP URL with username and password.
- **Fix:** Move to `.env` as `RTSP_CAMERA_URL`.

### Issue 4 — No Graceful Fallback in `face_api.py` if `face_recognition` Not Installed
- Import error is caught, but the routes still run and crash with `NameError`.
- **Fix:** Return a proper `503 Service Unavailable` response if library is missing.

---

## 6. Recommended Subfolder Structure

```
ai_services/                      ← rename from Face_recognition/
│
├── app.py                        ← Master entry point
├── requirements.txt
├── Dockerfile
├── packages.txt
├── best.pt                       ← YOLOv8 model weights
│
├── services/                     ← All 3 AI microservices
│   ├── intelligent_cctv.py
│   ├── face_api.py
│   └── video_processor.py
│
├── employees/                    ← Local face database (dev fallback)
│   └── <worker_id>/photo.jpg
│
├── processed_videos/             ← Already exists
│   ├── uploads/
│   └── outputs/
│
├── tools/                        ← Dev-only scripts (not deployed)
│   ├── register.py
│   ├── recognize.py
│   ├── rename.py
│   ├── cleanup_photos.py
│   ├── check_gpu.py
│   └── test.py
│
├── notebooks/                    ← Training research (not deployed)
│   └── PPE_YOLOv8_Colab.ipynb
│
└── docs/
    ├── api_contract.md
    └── AI_FOLDER_ANALYSIS.md    ← This file
```

> **Note:** Moving services into `services/` requires updating `app.py` imports (`from services.face_api import ...`). Do this when you're ready — not urgent.

---

## 7. Answers to Your Questions

| Question | Answer |
|---|---|
| What name to give this folder? | `ai_services/` |
| Do we need subfolders? | Yes — `services/`, `tools/`, `notebooks/`, `docs/` |
| Is the code efficient? | Yes, already very optimized. 4 minor issues to fix (above). |
| AI files first or connection first? | **AI files first, locally.** Test each service runs correctly in isolation before wiring to backend. |

---

*Phase 2 — AI folder review complete.*
