# Backend Problem & Solution Log

This document records each issue identified in the backend, the root cause, and the exact solution implemented.

---

## Phase 1: Core Backend & Data Integrity

### Task 1.1: Face Attendance Date Formatting & Deduplication Bug
- **File:** `backend/routes/face_attendance.js`
- **The Problem:** 
  In lines 74–77, `new Date()` was passed directly to `db.query()` as a parameter, and `attendance_date` was not saved. SQLite cannot parse raw JavaScript date strings using its `date()` function, causing `DATE(check_in_time)` to return `NULL`. As a result, the duplicate check `DATE(check_in_time) = date('now', 'localtime')` was always false, leading to duplicate check-in entries every second a worker remained in front of the camera.
- **The Solution:**
  1. Converted `new Date()` into two standard ISO-compliant strings: `check_in_time` (`YYYY-MM-DD HH:MM:SS`) and `attendance_date` (`YYYY-MM-DD`).
  2. Changed duplicate check to query `attendance_date = ?` directly, utilizing the existing database index `idx_worker_attendance(worker_id, attendance_date)`.
  3. Included `attendance_date` in the `INSERT INTO attendance` query alongside `check_in_time`.
  4. Standardized late check-in threshold to 8:30 AM (`hour > 8 || (hour === 8 && minute > 30)`).

---

### Task 1.2: Unprotected Ingestion Endpoints
- **Files:** `backend/routes/violations.js`, `backend/routes/health.js`, `backend/routes/attendance.js`, `backend/middleware/auth.js`, `.env`
- **The Problem:** `POST /api/violations`, `POST /api/health`, and `POST /api/attendance/checkin` had no authentication or authorization, allowing anyone on the network to flood the database with fake safety infractions, emergency alerts, or arbitrary check-in records.
- **The Solution:**
  1. Configured `INTERNAL_API_KEY` in `.env` for internal microservice communication.
  2. Implemented `requireApiKeyOrAuth` middleware in `backend/middleware/auth.js` that verifies `x-api-key` matching `INTERNAL_API_KEY` or falls back to standard Bearer JWT authentication.
  3. Applied `requireApiKeyOrAuth` to `POST /api/violations`, `POST /api/health`, `POST /api/attendance/checkin`, and `PUT /api/attendance/checkout/:id`.

---

### Task 1.3: Missing Cameras Route
- **Files:** `backend/routes/cameras.js`, `backend/server.js`
- **The Problem:** The database had a seeded `cameras` table and foreign keys referencing `camera_id`, but there was no Express router mounted to fetch, add, or update camera records. Frontend camera views and AI camera status reporting were completely detached from the database.
- **The Solution:**
  1. Created `backend/routes/cameras.js` with comprehensive endpoints:
     - `GET /api/cameras`: Lists all registered cameras (accessible via Bearer JWT or AI service `x-api-key`).
     - `GET /api/cameras/stats/summary`: Aggregates total, online, and offline camera counts.
     - `GET /api/cameras/:id`: Retrieves individual camera record.
     - `POST /api/cameras`: Registers new camera with validation (admin/supervisor).
     - `PUT /api/cameras/:id/status`: Updates camera online/offline status and updates `last_active` timestamp (AI heartbeat or admin).
     - `DELETE /api/cameras/:id`: Deletes camera (admin only).
  2. Mounted `camerasRoutes` at `/api/cameras` in `backend/server.js`.

---

### Task 1.4: Disconnected Fines Logging
- **Files:** `backend/routes/violations.js`
- **The Problem:** When safety violations were recorded in `POST /api/violations`, the database only created an entry in `violations`. The `fines` table was never populated, disconnecting safety fines from worker payroll and leaving fines unrecorded.
- **The Solution:**
  1. Updated `POST /api/violations`: When `worker_id` is identified and `fine_amount > 0`, an automated pending fine record is inserted into `fines` linked to `violation_id`.
  2. Updated `PUT /api/violations/:id/resolve`: When an admin or safety officer resolves a violation, any pending fine associated with that violation is automatically marked as `'waived'` with audit notes.

---

### Task 1.5: Client-Side Payroll Calculations
- **Files:** `backend/routes/salary.js`
- **The Problem:** The existing `POST /api/salary` route blindly accepted pre-calculated financial figures (`days_worked`, `gross_salary`, `total_fines`, `net_salary`) submitted from client-side JavaScript. This violated backend security (never trust client input) and allowed tampering with financial payroll data.
- **The Solution:**
  1. Built `calculateWorkerPayroll(worker_id, pay_period)` server-side computation engine:
     - Pulls official `wage_type` and `wage_rate` from `workers`.
     - Sums verified `days_worked` and `working_hours` from `attendance` for the target `pay_period`.
     - Aggregates active non-waived fines from `fines`.
     - Computes `gross_salary` (hourly or daily) and deducts `total_fines` to calculate exact `net_salary`.
  2. Added `POST /api/salary/calculate/:worker_id`: Performs server-side calculation for a worker and UPSERTs into the `salary` table.
  3. Added `POST /api/salary/generate-period`: Batch-calculates and persists official payroll records for all active workers for a given month.
