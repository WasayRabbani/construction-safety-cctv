# Backend Completion & System Integration Roadmap

This document outlines all technical issues and tasks required to bring the backend to **100% operational readiness** as a complete system (Frontend ↔ Node.js ↔ SQLite ↔ Python AI).

---

## System Overview

```
[ Frontend Web App ]
         │ (HTTP + Bearer JWT)
         ▼
[ Node.js Express API (Port 4000) ] ◄─── (HTTP + x-api-key) ─── [ Python AI Services ]
         │                                                      ├── intelligent_cctv.py (YOLOv8)
         │                                                      ├── face_api.py (dlib)
         ▼                                                      └── video_processor.py
[ SQLite DB (safety.sqlite) ]
         │
[ Cloudinary (Worker Photos) ]
```

---

## Phase 1: Core Backend & Data Integrity Fixes

### Task 1.1: Fix Face Attendance Date Formatting & Deduplication [COMPLETED]
- **File:** `backend/routes/face_attendance.js`
- **Issue:** `new Date()` is inserted directly into SQLite instead of an ISO string (`YYYY-MM-DD HH:MM:SS`), and `attendance_date` is omitted. SQLite's `DATE()` returns `NULL` when parsing JS dates, causing `DATE(check_in_time) = date('now')` to fail and insert duplicate attendance on every camera frame.
- **Fix:**
  - Format `check_in_time` as `YYYY-MM-DD HH:MM:SS`.
  - Store `attendance_date` as `YYYY-MM-DD`.
  - Use parameterized `attendance_date = date('now', 'localtime')` for duplicate checks.

### Task 1.2: Secure Ingestion Endpoints with Internal API Key [COMPLETED]
- **Files:** `backend/routes/violations.js`, `backend/routes/health.js`, `.env`
- **Issue:** `POST /api/violations` and `POST /api/health` have no authentication. Anyone on the network can inject fake violations.
- **Fix:**
  - Add `INTERNAL_API_KEY` to `.env`.
  - Create a lightweight middleware in `backend/middleware/auth.js` that checks for `x-api-key` header (or valid Bearer token).
  - Apply this middleware to AI ingestion endpoints.

### Task 1.3: Create Missing Cameras Route [COMPLETED]
- **Files:** `backend/routes/cameras.js`, `backend/server.js`
- **Issue:** The `cameras` table exists in SQLite and is seeded, but there is no API controller to fetch, update, or add cameras.
- **Fix:**
  - Create `backend/routes/cameras.js` with `GET /`, `GET /:id`, `POST /`, `PUT /:id`.
  - Mount `/api/cameras` in `backend/server.js`.

### Task 1.4: Automate Fine Logging on Violation Creation [COMPLETED]
- **Files:** `backend/routes/violations.js`
- **Issue:** When a violation is created, it writes to `violations` table but never creates a record in `fines` table, breaking the link to payroll.
- **Fix:**
  - Wrap violation creation in a transaction or insert into both `violations` and `fines` when `fine_amount > 0` and `worker_id` is present.

### Task 1.5: Implement Server-Side Payroll Calculation Engine [COMPLETED]
- **Files:** `backend/routes/salary.js`
- **Issue:** `POST /api/salary` expects the client browser to calculate `days_worked`, `gross_salary`, `total_fines`, and `net_salary`.
- **Fix:**
  - Add `POST /api/salary/calculate/:worker_id` or `POST /api/salary/generate-period` route.
  - Compute hours worked from `attendance` and deduct fines from `fines`/`violations` on the backend.

---

## Phase 2: Python AI to Backend Integration

### Task 2.1: Wire CCTV Detections to Backend Ingestion
- **File:** `Face_recognition/intelligent_cctv.py`
- **Issue:** `BACKEND_URL` is defined on line 50 but never called. YOLO detects missing hardhats, vests, and falls, but never posts them.
- **Fix:**
  - Implement a throttled HTTP client in `intelligent_cctv.py` that posts detected violations to `POST /api/violations` using `x-api-key`.
  - Include worker recognition if matched, or log as unknown.

### Task 2.2: Sync Worker Face Database with Python Recognition Engine
- **Files:** `backend/routes/workers.js`, `Face_recognition/face_api.py`
- **Issue:** Worker registration uploads photos to Cloudinary, but `face_api.py` only reads local disk folder `Face_recognition/employees/`.
- **Fix:**
  - Update `face_api.py` to fetch active face photos from `GET /api/workers/face-database` on startup/refresh, or download Cloudinary photos to the local cache.

---

## Phase 3: Frontend to Backend Integration

### Task 3.1: Centralized Authenticated Fetch Wrapper
- **File:** `frontend/config.js`
- **Issue:** Pages make raw `fetch()` calls without `Authorization: Bearer <token>`, causing `401 Unauthorized` errors.
- **Fix:**
  - Create `authFetch(url, options)` in `frontend/config.js` that automatically attaches the JWT token from `localStorage` and redirects to `login.html` if token is expired (401).

### Task 3.2: Update Frontend Pages to Use Authenticated Fetch
- **Files:** `frontend/dashboard.html`, `frontend/workers.html`, `frontend/violations.html`, `frontend/health.html`, `frontend/salary.html`, `frontend/camera.html`
- **Issue:** Pages fail to load data and try to calculate financial figures client-side.
- **Fix:**
  - Replace raw `fetch()` with `authFetch()`.
  - Connect `camera.html` to `GET /api/cameras`.

---

## Checklist: Compliance with BackendPoints.md

- [x] **Point 1 (Security First):** Ingestion endpoints protected by `x-api-key` and calculations moved server-side.
- [ ] **Point 2 (Authentication):** Frontend sends Bearer token on all protected routes (Phase 3).
- [x] **Point 3 (Authorization):** Roles enforced on cameras, salary, and workers.
- [x] **Point 4 (Validate Inputs):** Dates and types strictly validated before DB queries.
- [x] **Point 10 (Data Integrity):** Attendance deduplication and fines-violation relationships maintained.
- [x] **Point 11 (Code Organization):** Routes separated, payroll calculations moved to backend.
- [ ] **Point 13 (Test Before Deploying):** End-to-end integration verified across UI, API, and AI (Phases 2 & 3).
