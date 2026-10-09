-- SQLite Schema for Construction Safety System
PRAGMA foreign_keys = ON;

-- ============ WORKERS TABLE ============
CREATE TABLE IF NOT EXISTS workers (
    worker_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    cnic TEXT UNIQUE NOT NULL,
    phone TEXT,
    department TEXT,
    wage_type TEXT CHECK(wage_type IN ('hourly', 'daily')) NOT NULL,
    wage_rate REAL NOT NULL,
    join_date TEXT NOT NULL,
    status TEXT CHECK(status IN ('active', 'inactive')) DEFAULT 'active',
    photo_path TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);
-- ============ CAMERAS TABLE ============
CREATE TABLE IF NOT EXISTS cameras (
    camera_id INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_name TEXT NOT NULL,
    location TEXT NOT NULL,
    status TEXT CHECK(status IN ('online', 'offline')) DEFAULT 'online',
    resolution TEXT,
    fps INTEGER DEFAULT 30,
    last_active TEXT DEFAULT (datetime('now', 'localtime'))
);

-- ============ ATTENDANCE TABLE ============
CREATE TABLE IF NOT EXISTS attendance (
    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id TEXT,
    check_in_time TEXT,
    check_out_time TEXT,
    status TEXT CHECK(status IN ('present', 'absent', 'late', 'leave')) NOT NULL,
    location TEXT,
    working_hours REAL,
    attendance_date TEXT,
    FOREIGN KEY (worker_id) REFERENCES workers(worker_id) ON DELETE CASCADE
);

-- ============ VIOLATIONS TABLE ============
CREATE TABLE IF NOT EXISTS violations (
    violation_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    worker_id TEXT,
    violation_type TEXT NOT NULL,
    severity TEXT CHECK(severity IN ('low', 'medium', 'high')) NOT NULL,
    camera_id INTEGER,
    fine_amount REAL DEFAULT 0,
    snapshot_path TEXT,
    status TEXT CHECK(status IN ('pending', 'resolved')) DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (worker_id) REFERENCES workers(worker_id) ON DELETE SET NULL,
    FOREIGN KEY (camera_id) REFERENCES cameras(camera_id)
);

-- ============ FINES TABLE ============
CREATE TABLE IF NOT EXISTS fines (
    fine_id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id TEXT NOT NULL,
    violation_id TEXT,
    fine_type TEXT CHECK(fine_type IN ('violation', 'absence', 'late', 'other')) NOT NULL,
    fine_amount REAL NOT NULL,
    description TEXT,
    fine_date TEXT NOT NULL,
    status TEXT CHECK(status IN ('pending', 'deducted', 'waived')) DEFAULT 'pending',
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (worker_id) REFERENCES workers(worker_id) ON DELETE CASCADE,
    FOREIGN KEY (violation_id) REFERENCES violations(violation_id) ON DELETE SET NULL
);

-- ============ SALARY TABLE ============
CREATE TABLE IF NOT EXISTS salary (
    salary_id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id TEXT NOT NULL,
    pay_period TEXT NOT NULL,
    days_worked INTEGER DEFAULT 0,
    hours_worked REAL DEFAULT 0,
    rate_per_day_hour REAL NOT NULL,
    gross_salary REAL NOT NULL,
    violation_fines REAL DEFAULT 0,
    absence_fines REAL DEFAULT 0,
    late_fines REAL DEFAULT 0,
    other_fines REAL DEFAULT 0,
    total_fines REAL DEFAULT 0,
    tax_deduction REAL DEFAULT 0,
    other_deduction REAL DEFAULT 0,
    net_salary REAL NOT NULL,
    status TEXT CHECK(status IN ('pending', 'processing', 'paid')) DEFAULT 'pending',
    payment_date TEXT,
    payment_method TEXT,
    remarks TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (worker_id) REFERENCES workers(worker_id) ON DELETE CASCADE,
    UNIQUE (worker_id, pay_period)
);

-- ============ HEALTH ALERTS TABLE ============
CREATE TABLE IF NOT EXISTS health_alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    worker_id TEXT,
    alert_type TEXT NOT NULL,
    severity TEXT CHECK(severity IN ('low', 'medium', 'high', 'critical')) NOT NULL,
    description TEXT,
    location TEXT,
    camera_id INTEGER,
    status TEXT CHECK(status IN ('active', 'resolved')) DEFAULT 'active',
    response_time INTEGER,
    resolved_at TEXT,
    FOREIGN KEY (worker_id) REFERENCES workers(worker_id) ON DELETE SET NULL,
    FOREIGN KEY (camera_id) REFERENCES cameras(camera_id)
);

-- ============ FACE PHOTOS TABLE ============
CREATE TABLE IF NOT EXISTS face_photos (
    photo_id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id TEXT NOT NULL,
    photo_url TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (worker_id) REFERENCES workers(worker_id) ON DELETE CASCADE
);

-- ============ USERS TABLE ============
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT DEFAULT 'worker',
    status TEXT CHECK(status IN ('active', 'inactive')) DEFAULT 'active',
    phone TEXT,
    department TEXT,
    last_login TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- ============ PERFORMANCE INDEXES ============
CREATE INDEX IF NOT EXISTS idx_worker_salary ON salary(worker_id, pay_period);
CREATE INDEX IF NOT EXISTS idx_worker_violations ON violations(worker_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_worker_fines ON fines(worker_id, fine_date);
CREATE INDEX IF NOT EXISTS idx_worker_attendance ON attendance(worker_id, attendance_date);
CREATE INDEX IF NOT EXISTS idx_username ON users(username);
