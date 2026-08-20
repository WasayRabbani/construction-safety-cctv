CREATE DATABASE IF NOT EXISTS construction_safety;
USE construction_safety;

-- Drop tables in correct order
DROP TABLE IF EXISTS health_alerts;
DROP TABLE IF EXISTS salary;
DROP TABLE IF EXISTS fines;
DROP TABLE IF EXISTS violations;
DROP TABLE IF EXISTS attendance;
DROP TABLE IF EXISTS cameras;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS workers;

-- ============ WORKERS TABLE ============
CREATE TABLE workers (
    worker_id VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    cnic VARCHAR(20) UNIQUE NOT NULL,
    phone VARCHAR(20),
    department VARCHAR(50),
    wage_type ENUM('hourly', 'daily') NOT NULL,
    wage_rate DECIMAL(10, 2) NOT NULL,
    join_date DATE NOT NULL,
    status ENUM('active', 'inactive') DEFAULT 'active',
    photo_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============ CAMERAS TABLE ============
CREATE TABLE cameras (
    camera_id INT PRIMARY KEY AUTO_INCREMENT,
    camera_name VARCHAR(100) NOT NULL,
    location VARCHAR(100) NOT NULL,
    status ENUM('online', 'offline') DEFAULT 'online',
    resolution VARCHAR(20),
    fps INT DEFAULT 30,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ============ ATTENDANCE TABLE ============
CREATE TABLE attendance (
    attendance_id INT PRIMARY KEY AUTO_INCREMENT,
    worker_id VARCHAR(10),
    check_in_time DATETIME,
    check_out_time DATETIME,
    status ENUM('present', 'absent', 'late', 'leave') NOT NULL,
    location VARCHAR(100),
    working_hours DECIMAL(4, 2),
    attendance_date DATE,
    FOREIGN KEY (worker_id) REFERENCES workers(worker_id) ON DELETE CASCADE
);

-- ============ VIOLATIONS TABLE ============
CREATE TABLE violations (
    violation_id VARCHAR(10) PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    worker_id VARCHAR(10),
    violation_type ENUM('helmet', 'vest', 'gloves', 'boots', 'no-ppe', 'reckless-behavior') NOT NULL,
    severity ENUM('low', 'medium', 'high') NOT NULL,
    camera_id INT,
    fine_amount DECIMAL(10, 2) DEFAULT 0,
    snapshot_path VARCHAR(255),
    status ENUM('pending', 'resolved') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (worker_id) REFERENCES workers(worker_id) ON DELETE SET NULL,
    FOREIGN KEY (camera_id) REFERENCES cameras(camera_id)
);

-- ============ FINES TABLE (Detailed) ============
CREATE TABLE fines (
    fine_id INT PRIMARY KEY AUTO_INCREMENT,
    worker_id VARCHAR(10) NOT NULL,
    violation_id VARCHAR(10),
    fine_type ENUM('violation', 'absence', 'late', 'other') NOT NULL,
    fine_amount DECIMAL(10, 2) NOT NULL,
    description VARCHAR(255),
    fine_date DATE NOT NULL,
    status ENUM('pending', 'deducted', 'waived') DEFAULT 'pending',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (worker_id) REFERENCES workers(worker_id) ON DELETE CASCADE,
    FOREIGN KEY (violation_id) REFERENCES violations(violation_id) ON DELETE SET NULL
);

-- ============ SALARY TABLE ============
CREATE TABLE salary (
    salary_id INT PRIMARY KEY AUTO_INCREMENT,
    worker_id VARCHAR(10) NOT NULL,
    pay_period VARCHAR(7) NOT NULL,
    days_worked INT DEFAULT 0,
    hours_worked DECIMAL(6, 2) DEFAULT 0,
    rate_per_day_hour DECIMAL(10, 2) NOT NULL,
    gross_salary DECIMAL(10, 2) NOT NULL,
    
    -- Fines Breakdown
    violation_fines DECIMAL(10, 2) DEFAULT 0,
    absence_fines DECIMAL(10, 2) DEFAULT 0,
    late_fines DECIMAL(10, 2) DEFAULT 0,
    other_fines DECIMAL(10, 2) DEFAULT 0,
    total_fines DECIMAL(10, 2) DEFAULT 0,
    
    -- Deductions
    tax_deduction DECIMAL(10, 2) DEFAULT 0,
    other_deduction DECIMAL(10, 2) DEFAULT 0,
    
    net_salary DECIMAL(10, 2) NOT NULL,
    status ENUM('pending', 'processing', 'paid') DEFAULT 'pending',
    payment_date DATE,
    payment_method VARCHAR(50),
    remarks TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (worker_id) REFERENCES workers(worker_id) ON DELETE CASCADE,
    UNIQUE KEY unique_salary (worker_id, pay_period)
);

-- ============ HEALTH ALERTS TABLE ============
CREATE TABLE health_alerts (
    alert_id INT PRIMARY KEY AUTO_INCREMENT,
    timestamp DATETIME NOT NULL,
    worker_id VARCHAR(10),
    alert_type VARCHAR(100) NOT NULL,
    severity ENUM('low', 'medium', 'high', 'critical') NOT NULL,
    description TEXT,
    location VARCHAR(100),
    camera_id INT,
    status ENUM('active', 'resolved') DEFAULT 'active',
    response_time INT,
    resolved_at DATETIME,
    FOREIGN KEY (worker_id) REFERENCES workers(worker_id) ON DELETE SET NULL,
    FOREIGN KEY (camera_id) REFERENCES cameras(camera_id)
);

-- ============ USERS TABLE ============
CREATE TABLE users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role ENUM('admin', 'safety officer', 'hr', 'monitor', 'accounts', 'supervisor', 'worker') DEFAULT 'worker',
    status ENUM('active', 'inactive') DEFAULT 'active',
    phone VARCHAR(20),
    department VARCHAR(50),
    last_login DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============ INSERT WORKERS ============
INSERT INTO workers VALUES
('W001', 'Ahmad Ali', '12345-1234567-1', '+92 300 1234567', 'Construction', 'daily', 500, '2024-01-15', 'active', NULL, NOW()),
('W002', 'Hassan Khan', '12345-2345678-2', '+92 301 2345678', 'Electrical', 'hourly', 50, '2024-02-20', 'active', NULL, NOW()),
('W003', 'Bilal Ahmed', '12345-3456789-3', '+92 302 3456789', 'Plumbing', 'daily', 500, '2024-03-10', 'active', NULL, NOW()),
('W004', 'Usman Tariq', '12345-4567890-4', '+92 303 4567890', 'Construction', 'daily', 500, '2024-04-05', 'active', NULL, NOW());

-- ============ INSERT CAMERAS ============
INSERT INTO cameras (camera_name, location, resolution, fps) VALUES
('Camera 1 - Main Entrance', 'Main Gate Entry', '1920x1080', 30),
('Camera 2 - Construction Zone A', 'Zone A - Floor 2', '1920x1080', 30),
('Camera 3 - Equipment Storage', 'Storage Unit B', '1920x1080', 30),
('Camera 4 - Site Perimeter', 'North Perimeter', '1920x1080', 30);

-- ============ INSERT ATTENDANCE ============
INSERT INTO attendance (worker_id, check_in_time, check_out_time, status, location, working_hours, attendance_date) VALUES
('W001', CONCAT(CURDATE(), ' 08:00:00'), CONCAT(CURDATE(), ' 17:00:00'), 'present', 'Main Gate', 9.0, CURDATE()),
('W002', CONCAT(CURDATE(), ' 08:15:00'), CONCAT(CURDATE(), ' 17:15:00'), 'present', 'Main Gate', 9.0, CURDATE()),
('W003', CONCAT(CURDATE(), ' 09:30:00'), NULL, 'late', 'Main Gate', NULL, CURDATE()),
('W004', CONCAT(CURDATE(), ' 08:00:00'), CONCAT(CURDATE(), ' 17:00:00'), 'present', 'Main Gate', 9.0, CURDATE());

-- ============ INSERT VIOLATIONS ============
INSERT INTO violations (violation_id, timestamp, worker_id, violation_type, severity, camera_id, fine_amount, status) VALUES
('V001', CONCAT(CURDATE(), ' 10:30:00'), 'W003', 'helmet', 'high', 2, 500, 'pending'),
('V002', CONCAT(CURDATE(), ' 09:15:00'), 'W002', 'vest', 'medium', 3, 300, 'pending'),
('V003', CONCAT(CURDATE(), ' 11:00:00'), 'W001', 'gloves', 'low', 1, 200, 'pending'),
('V004', CONCAT(DATE_ADD(CURDATE(), INTERVAL -1 DAY), ' 14:20:00'), 'W004', 'helmet', 'high', 2, 500, 'resolved'),
('V005', CONCAT(DATE_ADD(CURDATE(), INTERVAL -2 DAY), ' 15:45:00'), 'W003', 'boots', 'high', 2, 500, 'resolved');

-- ============ INSERT FINES (DETAILED) ============
INSERT INTO fines (worker_id, violation_id, fine_type, fine_amount, description, fine_date, status) VALUES
('W001', 'V003', 'violation', 200, 'Missing gloves - Construction area', CURDATE(), 'pending'),
('W002', 'V002', 'violation', 300, 'Missing safety vest - Zone A', CURDATE(), 'pending'),
('W003', 'V001', 'violation', 500, 'Missing helmet - Construction zone', CURDATE(), 'pending'),
('W003', NULL, 'late', 100, 'Late arrival - 30 minutes', CURDATE(), 'pending'),
('W004', NULL, 'absence', 500, 'Absent on 2024-12-07', DATE_ADD(CURDATE(), INTERVAL -1 DAY), 'deducted');

-- ============ INSERT SALARY RECORDS ============
INSERT INTO salary (worker_id, pay_period, days_worked, hours_worked, rate_per_day_hour, gross_salary, 
                    violation_fines, absence_fines, late_fines, other_fines, total_fines, 
                    tax_deduction, other_deduction, net_salary, status, payment_method) VALUES
('W001', '2024-12', 22, 0, 500, 11000, 200, 0, 0, 0, 200, 500, 0, 10300, 'paid', 'Bank Transfer'),
('W002', '2024-12', 20, 160, 50, 8000, 300, 0, 0, 0, 300, 400, 0, 7300, 'processing', 'Bank Transfer'),
('W003', '2024-12', 20, 0, 500, 10000, 500, 0, 100, 0, 600, 500, 0, 8900, 'pending', 'Cash'),
('W004', '2024-12', 21, 0, 500, 10500, 500, 500, 0, 0, 1000, 500, 0, 8500, 'pending', 'Bank Transfer'),
('W001', '2024-11', 22, 0, 500, 11000, 0, 0, 0, 0, 0, 500, 0, 10500, 'paid', 'Bank Transfer'),
('W002', '2024-11', 22, 176, 50, 8800, 0, 0, 0, 0, 0, 400, 0, 8400, 'paid', 'Bank Transfer'),
('W003', '2024-11', 22, 0, 500, 11000, 300, 0, 0, 0, 300, 500, 0, 10200, 'paid', 'Cash'),
('W004', '2024-11', 22, 0, 500, 11000, 0, 0, 0, 0, 0, 500, 0, 10500, 'paid', 'Bank Transfer');

-- ============ INSERT HEALTH ALERTS ============
INSERT INTO health_alerts (timestamp, worker_id, alert_type, severity, description, location, camera_id, status) VALUES
(CONCAT(CURDATE(), ' 11:30:00'), 'W003', 'Worker Fatigue', 'critical', 'Worker showing signs of fatigue', 'Zone A', 2, 'active'),
(CONCAT(CURDATE(), ' 14:00:00'), 'W001', 'Heat Stress', 'high', 'High temperature exposure detected', 'Construction Zone', 1, 'resolved');

-- ============ INSERT USERS ============
INSERT INTO users (username, password_hash, full_name, role, phone, department) VALUES
('admin', 'hashedpass1', 'Admin User', 'admin', '+92 300 1111111', 'Administration'),
('supervisor', 'hashedpass2', 'Supervisor User', 'supervisor', '+92 300 2222222', 'Operations'),
('worker1', 'hashedpass3', 'Ahmad Ali', 'worker', '+92 300 1234567', 'Construction');

-- ============ CREATE INDEXES FOR PERFORMANCE ============
CREATE INDEX idx_worker_salary ON salary(worker_id, pay_period);
CREATE INDEX idx_worker_violations ON violations(worker_id, timestamp);
CREATE INDEX idx_worker_fines ON fines(worker_id, fine_date);
CREATE INDEX idx_worker_attendance ON attendance(worker_id, attendance_date);
CREATE INDEX idx_username ON users(username);
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS role          VARCHAR(20) NOT NULL DEFAULT 'worker',
  ADD COLUMN IF NOT EXISTS is_active     TINYINT(1)  NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS failed_logins INT         NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS locked_until  DATETIME    DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS refresh_token TEXT        DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS last_login    DATETIME    DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS created_by    INT         DEFAULT NULL;

-- If your column is named 'password' not 'password_hash':
ALTER TABLE users CHANGE password password_hash VARCHAR(255) NOT NULL;