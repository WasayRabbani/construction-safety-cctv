const express = require('express');
const router = express.Router();
const db = require('../config/database');

// Get attendance for a specific date
router.get('/date/:date', async (req, res) => {
    try {
        const [rows] = await db.query(`
            SELECT a.*, w.name, w.photo_path
            FROM attendance a
            JOIN workers w ON a.worker_id = w.worker_id
            WHERE DATE(a.check_in_time) = ?
            ORDER BY a.check_in_time ASC
        `, [req.params.date]);
        res.json(rows);
    } catch (error) {
        console.error('Error fetching attendance:', error);
        res.status(500).json({ error: error.message });
    }
});

// Get today's attendance stats
router.get('/stats/today', async (req, res) => {
    try {
        const [stats] = await db.query(`
            SELECT 
                COUNT(*) as total_records,
                SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present_count,
                SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) as absent_count,
                SUM(CASE WHEN status = 'late' THEN 1 ELSE 0 END) as late_count,
                SUM(CASE WHEN status = 'leave' THEN 1 ELSE 0 END) as leave_count,
                AVG(working_hours) as avg_hours,
                SUM(working_hours) as total_hours
            FROM attendance
            WHERE DATE(check_in_time) = CURDATE()
        `);
        res.json(stats[0]);
    } catch (error) {
        console.error('Error fetching attendance stats:', error);
        res.status(500).json({ error: error.message });
    }
});

// Check in worker
router.post('/checkin', async (req, res) => {
    try {
        const { worker_id, location } = req.body;
        const check_in_time = new Date();
        
        // Determine if late (assuming work starts at 8 AM)
        const hour = check_in_time.getHours();
        const status = (hour > 8 || (hour === 8 && check_in_time.getMinutes() > 30)) ? 'late' : 'present';
        
        const [result] = await db.query(
            'INSERT INTO attendance (worker_id, check_in_time, status, location) VALUES (?, ?, ?, ?)',
            [worker_id, check_in_time, status, location]
        );
        
        res.status(201).json({ 
            message: 'Check-in successful', 
            attendance_id: result.insertId,
            status: status
        });
    } catch (error) {
        console.error('Error checking in:', error);
        res.status(500).json({ error: error.message });
    }
});

// Check out worker
router.put('/checkout/:attendance_id', async (req, res) => {
    try {
        const check_out_time = new Date();
        
        const [result] = await db.query(
            `UPDATE attendance 
             SET check_out_time = ?,
                 working_hours = TIMESTAMPDIFF(HOUR, check_in_time, ?)
             WHERE attendance_id = ?`,
            [check_out_time, check_out_time, req.params.attendance_id]
        );
        
        if (result.affectedRows === 0) {
            return res.status(404).json({ error: 'Attendance record not found' });
        }
        
        res.json({ message: 'Check-out successful' });
    } catch (error) {
        console.error('Error checking out:', error);
        res.status(500).json({ error: error.message });
    }
});

// Get attendance by worker
router.get('/worker/:worker_id', async (req, res) => {
    try {
        const [rows] = await db.query(`
            SELECT * FROM attendance 
            WHERE worker_id = ?
            ORDER BY check_in_time DESC
            LIMIT 30
        `, [req.params.worker_id]);

        
        res.json(rows);
    } catch (error) {
        console.error('Error fetching worker attendance:', error);
        res.status(500).json({ error: error.message });
    }
});

module.exports = router;

// File: backend/routes/auth.js
const express = require('express');
const router = express.Router();
const db = require('../config/database');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');

const JWT_SECRET = process.env.JWT_SECRET || 'your_secret_key_change_this';

const ADMIN_REGISTER_CREDENTIALS = {
    username: 'maliksaad',
    password: 'maliksaad123'
};

const ALLOWED_ROLES = ['admin', 'safety officer', 'hr', 'monitor', 'accounts', 'supervisor', 'worker'];

// Register Route
router.post('/register', async (req, res) => {
    try {
        const {
            username,
            password,
            full_name,
            department,
            phone,
            role = 'worker',
            admin_username,
            admin_password
        } = req.body;

        const normalizedRole = String(role || 'worker').trim().toLowerCase();

        // Validate input
        if (!username || !password || !full_name || !admin_username || !admin_password) {
            return res.status(400).json({
                success: false,
                error: 'Username, password, full name, and admin credentials are required.'
            });
        }

        if (!ALLOWED_ROLES.includes(normalizedRole)) {
            return res.status(400).json({
                success: false,
                error: 'The selected role is not allowed. Please choose a valid role.'
            });
        }

        if (
            admin_username !== ADMIN_REGISTER_CREDENTIALS.username ||
            admin_password !== ADMIN_REGISTER_CREDENTIALS.password
        ) {
            return res.status(401).json({
                success: false,
                error: 'Invalid admin credentials. New account creation requires administration login.'
            });
        }

        // Validate username length
        if (username.length < 3) {
            return res.status(400).json({
                success: false,
                error: 'Username must be at least 3 characters'
            });
        }

        // Validate username length
        if (username.length < 3) {
            return res.status(400).json({
                success: false,
                error: 'Username must be at least 3 characters'
            });
        }

        // Validate password length
        if (password.length < 6) {
            return res.status(400).json({
                success: false,
                error: 'Password must be at least 6 characters'
            });
        }

        // Check if user already exists
        const [existingUsers] = await db.query(
            'SELECT * FROM users WHERE username = ?',
            [username]
        );

        if (existingUsers.length > 0) {
            return res.status(400).json({
                success: false,
                error: 'Username already exists. Please choose a different one.'
            });
        }

        // Hash password
        const hashedPassword = await bcrypt.hash(password, 10);

        // Insert new user
        const [result] = await db.query(
            'INSERT INTO users (username, password_hash, full_name, role, phone, department, status) VALUES (?, ?, ?, ?, ?, ?, ?)',
            [username, hashedPassword, full_name, normalizedRole, phone || null, department || null, 'active']
        );

        res.status(201).json({
            success: true,
            message: 'Account created successfully. You can now login.',
            user_id: result.insertId
        });

    } catch (error) {
        console.error('Register error:', error);
        res.status(500).json({
            success: false,
            error: 'Server error during registration. Please try again.'
        });
    }
});

// Login Route
router.post('/login', async (req, res) => {
    try {
        const { username, password } = req.body;

        // Validate input
        if (!username || !password) {
            return res.status(400).json({
                success: false,
                error: 'Username and password are required'
            });
        }

        // Query user from database
        const [users] = await db.query(
            'SELECT * FROM users WHERE username = ?',
            [username]
        );

        if (users.length === 0) {
            return res.status(401).json({
                success: false,
                error: 'Invalid username or password'
            });
        }

        const user = users[0];

        // Check user status
        if (user.status !== 'active') {
            return res.status(401).json({
                success: false,
                error: 'Your account has been deactivated. Contact administrator.'
            });
        }

        // Compare passwords
        const passwordMatch = await bcrypt.compare(password, user.password_hash);

        if (!passwordMatch) {
            return res.status(401).json({
                success: false,
                error: 'Invalid username or password'
            });
        }

        // Update last login
        await db.query(
            'UPDATE users SET last_login = NOW() WHERE user_id = ?',
            [user.user_id]
        );

        // Create JWT token
        const token = jwt.sign(
            {
                user_id: user.user_id,
                username: user.username,
                role: user.role,
                full_name: user.full_name
            },
            JWT_SECRET,
            { expiresIn: '24h' }
        );

        // Return success response
        res.json({
            success: true,
            message: 'Login successful',
            token: token,
            user: {
                user_id: user.user_id,
                username: user.username,
                full_name: user.full_name,
                role: user.role,
                department: user.department,
                phone: user.phone
            }
        });

    } catch (error) {
        console.error('Login error:', error);
        res.status(500).json({
            success: false,
            error: 'Server error during login. Please try again.'
        });
    }
});

// Verify Token Route
router.post('/verify', (req, res) => {
    try {
        const token = req.headers.authorization?.split(' ')[1];

        if (!token) {
            return res.status(401).json({
                success: false,
                error: 'No token provided'
            });
        }

        const decoded = jwt.verify(token, JWT_SECRET);
        res.json({
            success: true,
            user: decoded
        });

    } catch (error) {
        res.status(401).json({
            success: false,
            error: 'Invalid token'
        });
    }
});

// Get Current User Info
router.get('/user', (req, res) => {
    try {
        const token = req.headers.authorization?.split(' ')[1];

        if (!token) {
            return res.status(401).json({
                success: false,
                error: 'No token provided'
            });
        }

        const decoded = jwt.verify(token, JWT_SECRET);
        res.json({
            success: true,
            user: decoded
        });

    } catch (error) {
        res.status(401).json({
            success: false,
            error: 'Invalid token'
        });
    }
});

// Logout (optional - just clear client-side token)
router.post('/logout', (req, res) => {
    res.json({
        success: true,
        message: 'Logout successful'
    });
});

// IMPORTANT: Export the router
module.exports = router;
const express = require('express');
const router = express.Router();
const db = require('../config/database');

// Proxy to the Python Flask server
router.post('/scan', async (req, res) => {
    try {
        const { image } = req.body;
        
        if (!image) {
            return res.status(400).json({ success: false, error: 'No image provided' });
        }

        // Using native Node 18+ fetch API instead of node-fetch
        // Ensure Python API is running on port 5000
        const pythonResponse = await fetch('http://127.0.0.1:5000/recognize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: image })
        });

        if (!pythonResponse.ok) {
            throw new Error(`Python API responded with status ${pythonResponse.status}`);
        }

        const data = await pythonResponse.json();

        // 2. Handle the result
        if (data.status === 'match') {
            const employeeWorkerId = data.worker_id;
            const confidence = data.confidence;
            
            // 3. Find target employee in the workers table by worker_id OR name
            // (Since we updated the folder creation logic to use Names instead of IDs)
            const [workers] = await db.query(
                'SELECT * FROM workers WHERE worker_id = ? OR name = ? OR REPLACE(name, " ", "") = ?', 
                [employeeWorkerId, employeeWorkerId, employeeWorkerId]
            );
            
            if (workers.length === 0) {
                return res.status(404).json({ 
                    success: false, 
                    message: `Face matched '${employeeWorkerId}', but this could not be found in the database.` 
                });
            }

            const worker = workers[0];
            const checkInTime = new Date();
            
            // Check if already checked in today
            const [existing] = await db.query(
                'SELECT * FROM attendance WHERE worker_id = ? AND DATE(check_in_time) = CURDATE()',
                [worker.worker_id]
            );

            if (existing.length > 0) {
                return res.json({ 
                    success: true, 
                    message: `${worker.name} is already checked in for today!`,
                    worker: worker,
                    confidence: confidence
                });
            }

            // Determine if late (assuming work starts at 8 AM)
            const hour = checkInTime.getHours();
            const status = (hour > 8 || (hour === 8 && checkInTime.getMinutes() > 30)) ? 'late' : 'present';
            
            // Auto check-in
            await db.query(
                'INSERT INTO attendance (worker_id, check_in_time, status, location) VALUES (?, ?, ?, ?)',
                [worker.worker_id, checkInTime, status, 'Front Gate Camera']
            );

            return res.json({
                success: true,
                message: `Attendance marked for ${worker.name}. Status: ${status}.`,
                worker: worker,
                confidence: confidence
            });
            
        } else if (data.status === 'unknown') {
            return res.json({
                success: false,
                message: 'Face recognized as UNKNOWN. Please try again or register the employee.'
            });
        } else if (data.status === 'no_face') {
            return res.json({
                success: false,
                message: 'No face detected. Please ensure you are clearly visible.'
            });
        } else {
            return res.status(500).json({ success: false, error: 'Unexpected response from recognition engine.' });
        }

    } catch (error) {
        console.error('Face Integration error:', error);
        res.status(500).json({ success: false, error: 'Internal Server Error' });
    }
});

module.exports = router;

const express = require('express');
const router = express.Router();
const db = require('../config/database');

// Get all health alerts
router.get('/', async (req, res) => {
    try {
        const { status, severity, worker_id } = req.query;
        
        let query = `
            SELECT h.*, w.name as worker_name, c.camera_name
            FROM health_alerts h
            LEFT JOIN workers w ON h.worker_id = w.worker_id
            LEFT JOIN cameras c ON h.camera_id = c.camera_id
            WHERE 1=1
        `;
        const params = [];
        
        if (status) {
            query += ' AND h.status = ?';
            params.push(status);
        }
        if (severity) {
            query += ' AND h.severity = ?';
            params.push(severity);
        }
        if (worker_id) {
            query += ' AND h.worker_id = ?';
            params.push(worker_id);
        }
        
        query += ' ORDER BY h.timestamp DESC LIMIT 100';
        
        const [rows] = await db.query(query, params);
        res.json(rows);
    } catch (error) {
        console.error('Error fetching health alerts:', error);
        res.status(500).json({ error: error.message });
    }
});

// Get health alerts stats
router.get('/stats/summary', async (req, res) => {
    try {
        const [critical] = await db.query(`
            SELECT COUNT(*) as count FROM health_alerts 
            WHERE severity = 'critical' AND status = 'active'
        `);
        
        const [active] = await db.query(`
            SELECT COUNT(*) as count FROM health_alerts 
            WHERE status = 'active'
        `);
        
        const [resolved] = await db.query(`
            SELECT COUNT(*) as count FROM health_alerts 
            WHERE status = 'resolved' AND DATE(resolved_at) = CURDATE()
        `);
        
        const [avgResponse] = await db.query(`
            SELECT AVG(response_time) as avg_time FROM health_alerts
            WHERE response_time IS NOT NULL AND DATE(timestamp) >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        `);
        
        res.json({
            critical: critical[0].count,
            active: active[0].count,
            resolved: resolved[0].count,
            avg_response_time: avgResponse[0].avg_time ? Math.round(avgResponse[0].avg_time) : 0
        });
    } catch (error) {
        console.error('Error fetching health stats:', error);
        res.status(500).json({ error: error.message });
    }
});

// Create new health alert
router.post('/', async (req, res) => {
    try {
        const { worker_id, alert_type, severity, description, location, camera_id } = req.body;
        
        const [result] = await db.query(
            'INSERT INTO health_alerts (timestamp, worker_id, alert_type, severity, description, location, camera_id) VALUES (NOW(), ?, ?, ?, ?, ?, ?)',
            [worker_id, alert_type, severity, description, location, camera_id]
        );
        
        res.status(201).json({ 
            message: 'Health alert created successfully', 
            alert_id: result.insertId 
        });
    } catch (error) {
        console.error('Error creating health alert:', error);
        res.status(500).json({ error: error.message });
    }
});

// Resolve health alert
router.put('/:id/resolve', async (req, res) => {
    try {
        const { response_time } = req.body;
        
        const [result] = await db.query(
            'UPDATE health_alerts SET status = ?, resolved_at = NOW(), response_time = ? WHERE alert_id = ?',
            ['resolved', response_time, req.params.id]
        );
        
        if (result.affectedRows === 0) {
            return res.status(404).json({ error: 'Health alert not found' });
        }
        
        res.json({ message: 'Health alert resolved successfully' });
    } catch (error) {
        console.error('Error resolving health alert:', error);
        res.status(500).json({ error: error.message });
    }
});

// Get alerts by worker
router.get('/worker/:worker_id', async (req, res) => {
    try {
        const [rows] = await db.query(`
            SELECT h.*, c.camera_name
            FROM health_alerts h
            LEFT JOIN cameras c ON h.camera_id = c.camera_id
            WHERE h.worker_id = ?
            ORDER BY h.timestamp DESC
        `, [req.params.worker_id]);
        res.json(rows);
    } catch (error) {
        console.error('Error fetching worker health alerts:', error);
        res.status(500).json({ error: error.message });
    }
});

module.exports = router;

const express = require('express');
const router = express.Router();
const db = require('../config/database');

// Get salary records
router.get('/', async (req, res) => {
    try {
        const { pay_period, worker_id, status } = req.query;
        
        let query = `
            SELECT s.*, w.name, w.wage_type, w.wage_rate
            FROM salary s
            JOIN workers w ON s.worker_id = w.worker_id
            WHERE 1=1
        `;
        const params = [];
        
        if (pay_period) {
            query += ' AND s.pay_period = ?';
            params.push(pay_period);
        }
        if (worker_id) {
            query += ' AND s.worker_id = ?';
            params.push(worker_id);
        }
        if (status) {
            query += ' AND s.status = ?';
            params.push(status);
        }
        
        query += ' ORDER BY s.worker_id ASC';
        
        const [rows] = await db.query(query, params);
        res.json(rows);
    } catch (error) {
        console.error('Error fetching salary records:', error);
        res.status(500).json({ error: error.message });
    }
});

// Get salary summary
router.get('/stats/summary', async (req, res) => {
    try {
        const { pay_period } = req.query;
        const period = pay_period || new Date().toISOString().slice(0, 7); // YYYY-MM
        
        const [summary] = await db.query(`
            SELECT 
                SUM(gross_salary) as total_gross,
                SUM(total_fines) as total_fines,
                SUM(net_salary) as total_net,
                AVG(net_salary) as avg_salary,
                COUNT(*) as worker_count
            FROM salary
            WHERE pay_period = ?
        `, [period]);
        
        res.json(summary[0]);
    } catch (error) {
        console.error('Error fetching salary summary:', error);
        res.status(500).json({ error: error.message });
    }
});

// Get salary detail for a worker
router.get('/worker/:worker_id', async (req, res) => {
    try {
        const { pay_period } = req.query;
        
        const [salary] = await db.query(`
            SELECT s.*, w.name, w.wage_type, w.wage_rate
            FROM salary s
            JOIN workers w ON s.worker_id = w.worker_id
            WHERE s.worker_id = ? AND s.pay_period = ?
        `, [req.params.worker_id, pay_period]);
        
        // Get violations/fines for this worker
        const [fines] = await db.query(`
            SELECT violation_id, timestamp, violation_type, fine_amount
            FROM violations
            WHERE worker_id = ? 
            AND DATE_FORMAT(timestamp, '%Y-%m') = ?
            ORDER BY timestamp DESC
        `, [req.params.worker_id, pay_period]);
        
        res.json({
            salary: salary[0] || null,
            fines: fines
        });
    } catch (error) {
        console.error('Error fetching worker salary:', error);
        res.status(500).json({ error: error.message });
    }
});

// Create or update salary record
router.post('/', async (req, res) => {
    try {
        const { worker_id, pay_period, days_worked, hours_worked, gross_salary, total_fines, net_salary } = req.body;
        
        const [result] = await db.query(
            `INSERT INTO salary (worker_id, pay_period, days_worked, hours_worked, gross_salary, total_fines, net_salary)
             VALUES (?, ?, ?, ?, ?, ?, ?)
             ON DUPLICATE KEY UPDATE
             days_worked = VALUES(days_worked),
             hours_worked = VALUES(hours_worked),
             gross_salary = VALUES(gross_salary),
             total_fines = VALUES(total_fines),
             net_salary = VALUES(net_salary)`,
            [worker_id, pay_period, days_worked, hours_worked, gross_salary, total_fines, net_salary]
        );
        
        res.status(201).json({ message: 'Salary record saved successfully' });
    } catch (error) {
        console.error('Error saving salary:', error);
        res.status(500).json({ error: error.message });
    }
});

// Update salary status (for payment processing)
router.put('/:salary_id/status', async (req, res) => {
    try {
        const { status } = req.body;
        const payment_date = status === 'paid' ? new Date() : null;
        
        const [result] = await db.query(
            'UPDATE salary SET status = ?, payment_date = ? WHERE salary_id = ?',
            [status, payment_date, req.params.salary_id]
        );
        
        if (result.affectedRows === 0) {
            return res.status(404).json({ error: 'Salary record not found' });
        }
        
        res.json({ message: 'Salary status updated successfully' });
    } catch (error) {
        console.error('Error updating salary status:', error);
        res.status(500).json({ error: error.message });
    }
});

// Process payroll for all pending salaries
router.post('/process-payroll', async (req, res) => {
    try {
        const { pay_period } = req.body;
        
        const [result] = await db.query(
            `UPDATE salary 
             SET status = 'processing'
             WHERE pay_period = ? AND status = 'pending'`,
            [pay_period]
        );
        
        res.json({ 
            message: 'Payroll processing initiated',
            affected_records: result.affectedRows
        });
    } catch (error) {
        console.error('Error processing payroll:', error);
        res.status(500).json({ error: error.message });
    }
});

module.exports = router;
const express = require('express');
const router = express.Router();
const pool = require('../config/database');

// Test DB connection
router.get('/test-db', async (req, res) => {
    try {
        const [rows] = await pool.query('SELECT 1 AS test');
        res.json({
            database: 'connected',
            result: rows
        });
    } catch (error) {
        res.status(500).json({
            database: 'error',
            error: error.message
        });
    }
});

module.exports = router;

const express = require('express');
const router = express.Router();
const db = require('../config/database');

// Get all violations with filters
router.get('/', async (req, res) => {
    try {
        const { date_from, date_to, violation_type, severity, camera_id, worker_id } = req.query;
        
        let query = `
            SELECT v.*, w.name as worker_name, c.camera_name
            FROM violations v
            LEFT JOIN workers w ON v.worker_id = w.worker_id
            LEFT JOIN cameras c ON v.camera_id = c.camera_id
            WHERE 1=1
        `;
        const params = [];
        
        if (date_from && date_to) {
            query += ' AND DATE(v.timestamp) BETWEEN ? AND ?';
            params.push(date_from, date_to);
        }
        if (violation_type) {
            query += ' AND v.violation_type = ?';
            params.push(violation_type);
        }
        if (severity) {
            query += ' AND v.severity = ?';
            params.push(severity);
        }
        if (camera_id) {
            query += ' AND v.camera_id = ?';
            params.push(camera_id);
        }
        if (worker_id) {
            query += ' AND v.worker_id = ?';
            params.push(worker_id);
        }
        
        query += ' ORDER BY v.timestamp DESC LIMIT 100';
        
        const [rows] = await db.query(query, params);
        res.json(rows);
    } catch (error) {
        console.error('Error fetching violations:', error);
        res.status(500).json({ error: error.message });
    }
});

// Get violation stats
router.get('/stats/summary', async (req, res) => {
    try {
        const [today] = await db.query(`
            SELECT COUNT(*) as today_count
            FROM violations
            WHERE DATE(timestamp) = CURDATE()
        `);
        
        const [week] = await db.query(`
            SELECT COUNT(*) as week_count
            FROM violations
            WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        `);
        
        const [pending] = await db.query(`
            SELECT COUNT(*) as pending_count
            FROM violations
            WHERE status = 'pending'
        `);
        
        res.json({
            today: today[0].today_count,
            week: week[0].week_count,
            pending: pending[0].pending_count
        });
    } catch (error) {
        console.error('Error fetching violation stats:', error);
        res.status(500).json({ error: error.message });
    }
});

// Create new violation
router.post('/', async (req, res) => {
    try {
        const { violation_id, worker_id, violation_type, severity, camera_id, fine_amount, snapshot_path } = req.body;
        
        const [result] = await db.query(
            'INSERT INTO violations (violation_id, timestamp, worker_id, violation_type, severity, camera_id, fine_amount, snapshot_path) VALUES (?, NOW(), ?, ?, ?, ?, ?, ?)',
            [violation_id, worker_id, violation_type, severity, camera_id, fine_amount, snapshot_path]
        );
        
        res.status(201).json({ message: 'Violation recorded successfully', violation_id });
    } catch (error) {
        console.error('Error creating violation:', error);
        res.status(500).json({ error: error.message });
    }
});

// Resolve violation
router.put('/:id/resolve', async (req, res) => {
    try {
        const [result] = await db.query(
            'UPDATE violations SET status = ? WHERE violation_id = ?',
            ['resolved', req.params.id]
        );
        
        if (result.affectedRows === 0) {
            return res.status(404).json({ error: 'Violation not found' });
        }
        
        res.json({ message: 'Violation resolved successfully' });
    } catch (error) {
        console.error('Error resolving violation:', error);
        res.status(500).json({ error: error.message });
    }
});

// Get violations by worker
router.get('/worker/:worker_id', async (req, res) => {
    try {
        const [rows] = await db.query(`
            SELECT v.*, c.camera_name
            FROM violations v
            LEFT JOIN cameras c ON v.camera_id = c.camera_id
            WHERE v.worker_id = ?
            ORDER BY v.timestamp DESC
        `, [req.params.worker_id]);
        res.json(rows);
    } catch (error) {
        console.error('Error fetching worker violations:', error);
        res.status(500).json({ error: error.message });
    }
});

module.exports = router;
const express = require('express');
const router = express.Router();
const db = require('../config/database');
const upload = require('../config/upload');
const path = require('path');
const fs = require('fs');

async function saveWorkerPhotosAndInvalidateCache(worker_id, name, photos) {
    if (!photos || photos.length === 0) return null;

    // Use name for Face_recognition employee directory so the AI returns the Name instead of ID
    const safeName = (name || worker_id).toString().replace(/[^a-zA-Z0-9 ]/g, "").trim();
    const dir = path.join(__dirname, '../../Face_recognition/employees', safeName || worker_id);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

    let photoPathToSaveInDB = null;

    // Write all base64 photos to the directory
    for (let i = 0; i < photos.length; i++) {
        const base64Data = photos[i].replace(/^data:image\/\w+;base64,/, "");
        const filePath = path.join(dir, `photo_${i + 1}.jpg`);
        fs.writeFileSync(filePath, base64Data, 'base64');
        
        // Save first photo to uploads so dashboard UI can show it nicely
        if (i === 0) {
            const uploadDir = path.join(__dirname, '../../uploads/workers');
            if (!fs.existsSync(uploadDir)) fs.mkdirSync(uploadDir, { recursive: true });
            
            const dbPhotoName = `${worker_id}_${Date.now()}.jpg`;
            const dbPhotoPath = path.join(uploadDir, dbPhotoName);
            fs.writeFileSync(dbPhotoPath, base64Data, 'base64');
            photoPathToSaveInDB = `/uploads/workers/${dbPhotoName}`;
        }
    }

    // Invalidate DeepFace Cache so next scan automatically reindexes!
    const cacheFile = path.join(__dirname, '../../Face_recognition/employees/representations_facenet512.pkl');
    if (fs.existsSync(cacheFile)) {
        try { fs.unlinkSync(cacheFile); } catch(e) { console.error("Cache clear error:", e); }
    }

    return photoPathToSaveInDB;
}

// Get worker stats — MUST be before :id
router.get('/stats/summary', async (req, res) => {
    try {
        const [stats] = await db.query(`
            SELECT 
                COUNT(*) as total_workers,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_workers,
                SUM(CASE WHEN status = 'inactive' THEN 1 ELSE 0 END) as inactive_workers,
                SUM(CASE WHEN MONTH(join_date) = MONTH(NOW()) AND YEAR(join_date) = YEAR(NOW()) THEN 1 ELSE 0 END) as new_this_month
            FROM workers
        `);
        res.json(stats[0]);
    } catch (error) {
        console.error('Error fetching stats:', error);
        res.status(500).json({ error: error.message });
    }
});

// Get all workers
router.get('/', async (req, res) => {
    try {
        const [rows] = await db.query('SELECT * FROM workers ORDER BY worker_id ASC');
        res.json(rows);
    } catch (error) {
        console.error('Error fetching workers:', error);
        res.status(500).json({ error: error.message });
    }
});

// Get single worker
router.get('/:id', async (req, res) => {
    try {
        const [rows] = await db.query('SELECT * FROM workers WHERE worker_id = ?', [req.params.id]);
        if (rows.length === 0) {
            return res.status(404).json({ error: 'Worker not found' });
        }
        res.json(rows[0]);
    } catch (error) {
        console.error('Error fetching worker:', error);
        res.status(500).json({ error: error.message });
    }
});

// Create new worker with auto photo sync
router.post('/', async (req, res) => {
    try {
        const { worker_id, name, cnic, phone, department, wage_type, wage_rate, join_date, photos } = req.body;
        
        if (!worker_id || !name || !cnic || !wage_type || !wage_rate || !join_date) {
            return res.status(400).json({ error: 'Missing required fields' });
        }
        
        let photo_path = null;
        if (photos && photos.length > 0) {
            photo_path = await saveWorkerPhotosAndInvalidateCache(worker_id, name, photos);
        }
        
        const [result] = await db.query(
            `INSERT INTO workers (worker_id, name, cnic, phone, department, wage_type, wage_rate, join_date, photo_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
            [worker_id, name, cnic, phone, department, wage_type, wage_rate, join_date, photo_path]
        );
        
        res.status(201).json({ message: 'Worker created successfully', worker_id, photo_path });
    } catch (error) {
        console.error('Error creating worker:', error);
        if (error.code === 'ER_DUP_ENTRY') {
            res.status(400).json({ error: 'Worker ID or CNIC already exists' });
        } else {
            res.status(500).json({ error: error.message });
        }
    }
});

// Update worker with optional photo upload
router.put('/:id', async (req, res) => {
    try {
        const { name, cnic, phone, department, wage_type, wage_rate, status, photos, existing_photo_path } = req.body;
        const worker_id = req.params.id;
        
        const [existing] = await db.query('SELECT photo_path FROM workers WHERE worker_id = ?', [worker_id]);
        if (existing.length === 0) return res.status(404).json({ error: 'Worker not found' });
        
        let photo_path = existing_photo_path || existing[0].photo_path;
        
        if (photos && photos.length > 0) {
            photo_path = await saveWorkerPhotosAndInvalidateCache(worker_id, name, photos);
            
            // Delete old photo in uploads if we generated a new one
            if (existing[0].photo_path && photo_path && photo_path !== existing[0].photo_path) {
                const oldPhotoPath = path.join(__dirname, '../../', existing[0].photo_path);
                if(fs.existsSync(oldPhotoPath)) fs.unlinkSync(oldPhotoPath);
            }
        }
        
        const [result] = await db.query(
            `UPDATE workers SET name = ?, cnic = ?, phone = ?, department = ?, wage_type = ?, wage_rate = ?, status = ?, photo_path = ? WHERE worker_id = ?`,
            [name, cnic, phone, department, wage_type, wage_rate, status || 'active', photo_path, worker_id]
        );
        
        if (result.affectedRows === 0) return res.status(404).json({ error: 'Worker not found' });
        res.json({ message: 'Worker updated successfully', photo_path });
    } catch (error) {
        console.error('Error updating worker:', error);
        res.status(500).json({ error: error.message });
    }
});

// Delete worker
router.delete('/:id', async (req, res) => {
    try {
        // Get worker info before deletion
        const [worker] = await db.query('SELECT name, photo_path FROM workers WHERE worker_id = ?', [req.params.id]);
        
        const [result] = await db.query('DELETE FROM workers WHERE worker_id = ?', [req.params.id]);
        
        if (result.affectedRows === 0) {
            return res.status(404).json({ error: 'Worker not found' });
        }
        
        // Delete photo file in uploads if it exists
        if (worker.length > 0 && worker[0].photo_path) {
            const photoPath = path.join(__dirname, '../../', worker[0].photo_path);
            fs.unlink(photoPath, (err) => {
                if (err) console.error('Error deleting upload photo:', err);
            });
        }
        
        // Delete Face_recognition/employees/{name}/ folder so AI stops recognizing them
        if (worker.length > 0 && worker[0].name) {
            const safeName = (worker[0].name).toString().replace(/[^a-zA-Z0-9 ]/g, "").trim();
            const employeeDir = path.join(__dirname, '../../Face_recognition/employees', safeName);
            if (fs.existsSync(employeeDir)) {
                fs.rmSync(employeeDir, { recursive: true, force: true });
                console.log('[CLEANUP] Deleted employee folder: ' + employeeDir);
            }
            
            // Invalidate DeepFace cache so it re-indexes without this worker
            const cacheDir = path.join(__dirname, '../../Face_recognition/employees');
            try {
                const files = fs.readdirSync(cacheDir);
                files.forEach(f => {
                    if (f.endsWith('.pkl')) {
                        fs.unlinkSync(path.join(cacheDir, f));
                        console.log('[CLEANUP] Deleted cache: ' + f);
                    }
                });
            } catch(e) { console.error('Cache cleanup error:', e); }
        }
        
        res.json({ message: 'Worker deleted successfully' });
    } catch (error) {
        console.error('Error deleting worker:', error);
        res.status(500).json({ error: error.message });
    }
});

module.exports = router;
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '../.env') });

const express = require('express');
const cors = require('cors');

const app = express();
const PORT = process.env.API_PORT || 4000;

// Middleware
app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

// Static files
app.use(express.static(path.join(__dirname, '../frontend')));
app.use('/uploads', express.static(path.join(__dirname, '../uploads')));
app.use('/hls', express.static(path.join(__dirname, '../hls')));

// Routes
const authRoutes = require('./routes/auth');
const workersRoutes = require('./routes/workers');
const attendanceRoutes = require('./routes/attendance');
const violationsRoutes = require('./routes/violations');
const salaryRoutes = require('./routes/salary');
const healthRoutes = require('./routes/health');
const testRoutes = require('./routes/test');
const faceAttendanceRoutes = require('./routes/face_attendance');

app.use('/api/auth', authRoutes);
app.use('/api/workers', workersRoutes);
app.use('/api/attendance', attendanceRoutes);
app.use('/api/violations', violationsRoutes);
app.use('/api/salary', salaryRoutes);
app.use('/api/health', healthRoutes);
app.use('/api/test', testRoutes);
app.use('/api/face-attendance', faceAttendanceRoutes);

// =======================
// Pages
// =======================

// Landing Page (Default Home Page)
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/landingpage.html'));
});

// Optional Landing Page Route
app.get('/landingpage', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/landingpage.html'));
});

// Login
app.get('/login', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/login.html'));
});

// Signup
app.get('/signup', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/signup.html'));
});

// Dashboard
app.get('/dashboard', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/dashboard.html'));
});

app.get('/dashboard.html', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/dashboard.html'));
});

// =======================
// Catch-All Route
// =======================
app.use((req, res) => {
    const filePath = path.join(
        __dirname,
        '../frontend',
        req.path.replace(/\/$/, '') + '.html'
    );

    res.sendFile(filePath, (err) => {
        if (err) {
            res.status(404).sendFile(
                path.join(__dirname, '../frontend/landingpage.html')
            );
        }
    });
});

// =======================
// Error Handler
// =======================
app.use((err, req, res, next) => {
    console.error('Server error:', err);
    res.status(500).json({ error: 'Internal server error' });
});

// =======================
// Start Server
// =======================
app.listen(PORT, () => {
    console.log('='.repeat(60));
    console.log('✅ Server running on http://localhost:' + PORT);
    console.log('🏠 Landing Page : http://localhost:' + PORT + '/');
    console.log('🌐 Landing URL  : http://localhost:' + PORT + '/landingpage');
    console.log('🔐 Login Page   : http://localhost:' + PORT + '/login');
    console.log('📝 Signup Page  : http://localhost:' + PORT + '/signup');
    console.log('📊 Dashboard    : http://localhost:' + PORT + '/dashboard');
    console.log('='.repeat(60));
    console.log('\n📋 Demo Credentials:');
    console.log('   Admin      : admin / admin123');
    console.log('   Supervisor : supervisor / super123');
    console.log('   Worker     : worker1 / worker123');
    console.log('='.repeat(60));
});
import os
import time
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from deepface import DeepFace
import torch

# ── DEVICE DETECTION (GPU/CPU) ────────────────────────────────────────────────
print("\n🔍 Checking Hardware...")
gpu_available = torch.cuda.is_available()

if gpu_available:
    DEVICE = 0
    print(f"✅ GPU DETECTED: {torch.cuda.get_device_name(0)}")
    print("🚀 Face Recognition will use GPU acceleration.")
    
    # Force TensorFlow to use GPU
    import tensorflow as tf
    gpus = tf.config.list_physical_devices('GPU')
    if gpus:
        try:
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
            print(f"✅ TENSORFLOW GPU ENABLED: {len(gpus)} device(s) found.")
        except RuntimeError as e:
            print(f"ℹ️ TensorFlow GPU initialization error: {e}")
    else:
        print("ℹ️ TENSORFLOW GPU NOT FOUND. Using CPU for recognition.")
else:
    DEVICE = 'cpu'
    print("ℹ️ NO GPU DETECTED. Face Recognition will use CPU.")
print("────────────────────────────────────────────────\n")

app = Flask(__name__)
CORS(app)

# Silence Flask logging for a cleaner terminal
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Absolute path so it works no matter where the script is launched from
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'employees')
MATCH_THRESHOLD = 0.35

def get_confidence(distance):
    return max(0, round((1 - distance) * 100, 1))

@app.route('/recognize', methods=['POST'])
def recognize_face():
    try:
        data = request.json
        if not data or 'image' not in data:
            return jsonify({"error": "No image data provided"}), 400

        # Decode base64 image
        image_data = data['image']
        # Remove data URI prefix if present
        if ',' in image_data:
            image_data = image_data.split(',')[1]
            
        img_bytes = base64.b64decode(image_data)
        temp_img_path = "temp_auth_image.jpg"
        
        with open(temp_img_path, "wb") as f:
            f.write(img_bytes)

        # Run DeepFace recognition (no explicit detector_backend so cache matches CCTV)
        result = DeepFace.find(
            img_path=temp_img_path,
            db_path=DB_PATH,
            model_name="Facenet512",
            enforce_detection=False,
            silent=True
        )

        # Cleanup temp file
        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)

        if result and len(result[0]) > 0:
            match = result[0].iloc[0]
            distance = match["distance"]
            
          
            full_dir = os.path.dirname(match["identity"])
            worker_id = os.path.basename(full_dir)
            
            confidence = get_confidence(distance)

            # Check threshold
            if distance < MATCH_THRESHOLD:
                return jsonify({
                    "status": "match",
                    "worker_id": worker_id,
                    "confidence": confidence,
                    "distance": distance
                })
            else:
                return jsonify({
                    "status": "unknown",
                    "message": "Face detected, but unverified."
                })
        else:
            return jsonify({"status": "no_face", "message": "No face detected in image"})

    except Exception as e:
        if os.path.exists("temp_auth_image.jpg"):
            os.remove("temp_auth_image.jpg")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # ── FULL DATABASE PRE-BUILD ───────────────────────────────────────────────
    total_images = 0
    for root, dirs, files in os.walk(DB_PATH):
        for f in files:
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                total_images += 1

    print(f"🔄 Initializing Employee Database...")

    start_time = time.time()
    try:
        import numpy as np
        dummy = np.zeros((160, 160, 3), dtype=np.uint8)
        DeepFace.find(img_path=dummy, db_path=DB_PATH, model_name="Facenet512", enforce_detection=False, silent=True)

        elapsed = time.time() - start_time
        print(f"✅ ATTENDANCE READY: Face Database ({total_images} employees) loaded.")
        print(f"🚀 Auth API is now active on http://127.0.0.1:5000")
    except Exception as e:
        print(f"[WARN] Pre-build issue: {e}")

    app.run(host='0.0.0.0', port=5000, debug=False)

import torch
import sys

print("-" * 50)
print(f"Python Version: {sys.version}")
print(f"PyTorch Version: {torch.__version__}")
print("-" * 50)

print(f"Is CUDA (GPU) available? : {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"GPU Name: {torch.cuda.get_device_name(0)}")
    print(f"CUDA Version: {torch.version.cuda}")
    print(f"Number of GPUs: {torch.cuda.device_count()}")
    print("\n✅ YOUR GPU IS READY! If the main script still says 'No GPU', we just need to restart the environment.")
else:
    print("\n❌ GPU NOT DETECTED BY PYTORCH.")
    print("\nPossible solutions:")
    print("1. Run: pip uninstall torch torchvision torchaudio -y")
    print("2. Run: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")
    print("   (Note: Try cu121 if cu118 doesn't work)")
print("-" * 50)
"""
Cleanup script: Keeps only the best 5 photos per employee.
Scores images by face size and clarity using OpenCV face detection.
"""
import os
import cv2
import sys

EMPLOYEES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'employees')
KEEP_COUNT = 5

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def score_image(img_path):
    """Score an image by face size and sharpness. Higher = better."""
    img = cv2.imread(img_path)
    if img is None:
        return -1
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 5)
    
    if len(faces) == 0:
        # No face detected — low score but don't discard completely
        return 0
    
    # Use the largest face found
    areas = [w * h for (x, y, w, h) in faces]
    max_area = max(areas)
    
    # Also factor in image sharpness (Laplacian variance)
    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    # Combined score: face area (most important) + sharpness bonus
    return max_area + (sharpness * 0.1)

def main():
    print(f"\n{'='*60}")
    print(f"  PHOTO CLEANUP — Keeping best {KEEP_COUNT} per employee")
    print(f"{'='*60}\n")
    
    total_deleted = 0
    total_kept = 0
    
    for folder_name in sorted(os.listdir(EMPLOYEES_DIR)):
        folder_path = os.path.join(EMPLOYEES_DIR, folder_name)
        if not os.path.isdir(folder_path):
            continue
        
        # Get all image files
        images = []
        for f in os.listdir(folder_path):
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                full_path = os.path.join(folder_path, f)
                images.append(full_path)
        
        if len(images) <= KEEP_COUNT:
            print(f"  [OK] {folder_name}: {len(images)} images (no cleanup needed)")
            total_kept += len(images)
            continue
        
        # Score each image
        scored = []
        for img_path in images:
            score = score_image(img_path)
            scored.append((img_path, score))
        
        # Sort by score (highest first) and keep top N
        scored.sort(key=lambda x: x[1], reverse=True)
        
        keep = scored[:KEEP_COUNT]
        delete = scored[KEEP_COUNT:]
        
        print(f"\n  [FOLDER] {folder_name} ({len(images)} images -> keeping {KEEP_COUNT}):")
        print(f"     KEEPING:")
        for path, score in keep:
            print(f"       [OK] {os.path.basename(path)} (score: {score:.0f})")
        
        print(f"     DELETING:")
        for path, score in delete:
            print(f"       [DEL] {os.path.basename(path)} (score: {score:.0f})")
            os.remove(path)
            total_deleted += 1
        
        total_kept += KEEP_COUNT
    
    # Delete .pkl cache so it rebuilds fresh with fewer images
    for f in os.listdir(EMPLOYEES_DIR):
        if f.endswith('.pkl'):
            os.remove(os.path.join(EMPLOYEES_DIR, f))
            print(f"\n  [TRASH]  Deleted old cache: {f}")
    
    print(f"\n{'='*60}")
    print(f"  DONE! Kept {total_kept} images, deleted {total_deleted} images.")
    print(f"  Cache cleared — will rebuild on next startup (~20 seconds).")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()

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
from deepface import DeepFace
import torch

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
FFMPEG_PATH = r"C:\Users\Malik Saad Rafiq\Desktop\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"

# Absolute path to employees folder so DeepFace always finds it regardless of where the script is launched from
EMPLOYEES_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'employees')

# IMOU CAMERA CONFIGURATION
# Replace the URL below with your actual camera RTSP link
# Format: rtsp://admin:PASSWORD@IP_ADDRESS:554/cam/realmonitor?channel=1&subtype=0
IMOU_CAMERA_URL = "rtsp://admin:L2C9A3C5@192.168.137.199:554/cam/realmonitor?channel=1&subtype=0"

# --- CAMERA SELECTION --- 
#   0 : Default Built-in Laptop Webcam
#   1 : External USB Webcam
#   'imou' : Imou CCTV Camera (RTSP)
CAMERA_SOURCE = IMOU_CAMERA_URL

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

def run_deepface(crop, cx, cy):
    global face_recognition_active
    try:
        df_result = DeepFace.find(img_path=crop, db_path=EMPLOYEES_DB, model_name="Facenet512",
                                  distance_metric="cosine", detector_backend='opencv', enforce_detection=True, silent=True)
        if df_result and len(df_result[0]) > 0:
            match = df_result[0].iloc[0]
            dist = match["distance"]
            print(
                f"[FACE] Best match distance: {dist:.4f} → {match['identity']}")
            if dist < 0.50:  # Relaxed threshold (from 0.45) for better hat/helmet tolerance
                full_dir = os.path.dirname(match["identity"])
                name = os.path.basename(full_dir)
                update_face_cache(cx, cy, name)
                print(f"[FACE] Recognized: {name}")
            else:
                update_face_cache(cx, cy, "Unknown")
                print(
                    f"[FACE] Match found but distance {dist:.4f} > threshold 0.45 → Unknown")
        else:
            print("[FACE] No match found in employees DB")
    except Exception as e:
        # Ignore common "no face detected" errors to keep terminal clean
        if "Face could not be detected" not in str(e):
            print(f"[FACE ERROR] {e}")
    finally:
        face_recognition_active = False

def background_ai_worker():
    global global_frame, latest_detections, metrics, face_recognition_active, recognized_faces
    print("[INFO] AI Background Thread Started...")

    print(f"[INFO] Employees DB path: {EMPLOYEES_DB}")
    print(f"[INFO] DB exists: {os.path.isdir(EMPLOYEES_DB)}")

    # ── FULL DATABASE PRE-BUILD ───────────────────────────────────────────────
    # Count total images so the user knows what to expect
    total_images = 0
    for root, dirs, files in os.walk(EMPLOYEES_DB):
        for f in files:
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                total_images += 1

    print(f"")
    print(f"╔══════════════════════════════════════════════════════╗")
    print(
        f"║  LOADING FACE DATABASE — {total_images} images to process       ║")
    print(f"║  This may take a few minutes on first run...        ║")
    print(f"║  Please wait. Camera will start after this.         ║")
    print(f"╚══════════════════════════════════════════════════════╝")
    print(f"")

    start_time = time.time()
    try:
        # This single call forces DeepFace to:
        # 1. Load the Facenet512 neural network
        # 2. Scan every image in the employees folder
        # 3. Build and save the .pkl cache file
        import numpy as np
        dummy = np.zeros((160, 160, 3), dtype=np.uint8)
        DeepFace.find(img_path=dummy, db_path=EMPLOYEES_DB,
                      model_name="Facenet512", enforce_detection=False, silent=True)

        elapsed = time.time() - start_time
        print(f"✅ SYSTEM READY: PPE Model and Face Database ({total_images} employees) loaded.")
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
            # imgsz=960 : Larger size helps detect small PPE on distant CCTV people
            # conf=0.15 : Balanced confidence for surveillance
            results = yolo_model(frame_copy, imgsz=960,
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
                                threading.Thread(target=run_deepface, args=(
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
    global global_frame, CAMERA_SOURCE

    current_source = None
    cap = None
    pipe = None

    fail_count = 0
    frame_size = 0
    frame_width = 0
    frame_height = 0
    is_rtsp = False

    while True:
        if current_source != CAMERA_SOURCE or (pipe is None and cap is None):
            # If we have no active stream, wait a bit and try to (re)connect
            if pipe is None and cap is None and current_source is not None:
                print(f"[INFO] No active stream. Retrying connection to {CAMERA_SOURCE} in 2s...")
                time.sleep(2)

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
                    
                    # Wait longer (5s) for RTSP handshake over hotspot
                    time.sleep(5)
                    if frame_queue.empty():
                        if pipe.poll() is not None:
                            print(f"[ERROR] FFmpeg crashed on startup.")
                        else:
                            print(f"[WARN] FFmpeg is running but not receiving video. Retrying...")
                            pipe.kill()
                        pipe = None
                        
                        print(f"[INFO] Attempting OpenCV fallback...")
                        cap = cv2.VideoCapture(current_source)
                        if not cap.isOpened(): cap = None
                except Exception as e:
                    print(f"[WARN] FFmpeg Launch Error: {e}. Falling back to OpenCV...")
                    pipe = None
                    cap = cv2.VideoCapture(current_source)
                    if not cap.isOpened(): cap = None
            else:
                print(f"[INFO] Launching Local Webcam Capture (Device {current_source})...")
                cap = cv2.VideoCapture(current_source, cv2.CAP_DSHOW)
                if not cap or not cap.isOpened():
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

        # Broadcast immediately! JPEG quality 65-70 is plenty for monitoring and saves hotspot bandwidth
        ret, buffer = cv2.imencode(
            '.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
        if ret:
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

        # Control the output stream frame rate slightly so we don't bombard the browser
        time.sleep(1/30.0)



@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

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

import os
from deepface import DeepFace

DB_PATH = "employees/"

# ── PUT YOUR PHOTO PATH HERE ──────────────────────────
IMG_PATH =  "photo.jpg" 
# ─────────────────────────────────────────────────────

MATCH_THRESHOLD     = 0.35
UNCERTAIN_THRESHOLD = 0.50

def get_confidence(distance):
    return max(0, round((1 - distance) * 100, 1))

def recognize(img_path):
    if not os.path.exists(img_path):
        print(f"[ERROR] File not found: {img_path}")
        return

    print(f"[INFO] Checking: {img_path}")

    try:
        result = DeepFace.find(
            img_path=img_path,
            db_path=DB_PATH,
            model_name="Facenet512",
            detector_backend="opencv",
            enforce_detection=False,
            silent=True
        )

        if result and len(result[0]) > 0:
            match      = result[0].iloc[0]
            distance   = match["distance"]
            name       = os.path.splitext(os.path.basename(match["identity"]))[0]
            confidence = get_confidence(distance)

            print(f"[DEBUG] Closest   : {name}")
            print(f"[DEBUG] Distance  : {round(distance, 4)}")
            print(f"[DEBUG] Confidence: {confidence}%")

            if distance < MATCH_THRESHOLD:
                print(f"[MATCH] ✅ {name} ({confidence}% confidence)")
            elif distance < UNCERTAIN_THRESHOLD:
                print(f"[UNCERTAIN] ⚠️  Might be {name} ({confidence}%)")
            else:
                print(f"[UNKNOWN] ❌ Not in database")
        else:
            print("[UNKNOWN] ❌ No face detected")

    except Exception as e:
        print(f"[ERROR] {e}")

recognize(IMG_PATH)
import cv2
import os

def register_employee(name):
    os.makedirs("employees", exist_ok=True)
    cam = cv2.VideoCapture("http://192.168.1.8:8080/video")
    print(f"[INFO] Press SPACE to capture photo for: {name}")

    while True:
        ret, frame = cam.read()
        cv2.imshow("Register - Press SPACE to capture", frame)
        key = cv2.waitKey(1)

        if key == 32:  # SPACE
            path = f"employees/{name}.jpg"
            cv2.imwrite(path, frame)
            print(f"[SAVED] {path}")
            break
        elif key == 27:  # ESC
            print("[CANCELLED]")
            break

    cam.release()
    cv2.destroyAllWindows()

# Usage:
register_employee("Muhammad Ali")
import os
import sys

def rename_photos(folder_path):
    folder_name = os.path.basename(folder_path.rstrip("/\\"))
    
    extensions = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
    files = [f for f in os.listdir(folder_path) 
             if f.lower().endswith(extensions)]
    files.sort()

    for i, file in enumerate(files, start=1):
        ext = os.path.splitext(file)[1].lower()
        new_name = f"{folder_name}_{i}{ext}"
        old_path = os.path.join(folder_path, file)
        new_path = os.path.join(folder_path, new_name)
        os.rename(old_path, new_path)
        print(f"[RENAMED] {file} → {new_name}")

    print(f"\n[DONE] {len(files)} files renamed.")

# ── PUT FOLDER PATH HERE ──────────────────────────────
folder = r"C:\Users\dell\OneDrive\Desktop\FYP Module\employees\Wasay"
# ─────────────────────────────────────────────────────

rename_photos(folder)
import urllib.request
import json
import base64
import glob

imgs = glob.glob('employees/*/*.jpg')
if not imgs:
    print("No images found in employees folder!")
else:
    img = imgs[0]
    print('Using image:', img)
    with open(img, "rb") as f:
        img_data = f.read()
    b64 = base64.b64encode(img_data).decode("utf-8")

    req = urllib.request.Request(
        'http://127.0.0.1:5000/recognize',
        data=json.dumps({'image': f'data:image/jpeg;base64,{b64}'}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    try:
        res = urllib.request.urlopen(req)
        print("Success:", res.read())
    except urllib.error.HTTPError as e:
        print("HTTP Error:", e.code)
        print(e.read())
    except Exception as e:
        print("General Error:", str(e))

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Attendance Management</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #121212;
            color: #F3F4F6;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header {
            background: #1E1E1E;
            padding: 25px 30px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
        }
        .header h1 { color: #FFC107; font-size: 28px; font-weight: 700; margin-bottom: 15px; }
        .date-selector { display: flex; align-items: center; gap: 15px; }
        .date-input {
            padding: 10px 15px;
            border: 1px solid #444;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            background: #2D2D2D;
            color: #F3F4F6;
        }
        .date-input:focus {
            outline: none;
            border-color: #FFC107;
            box-shadow: 0 0 0 2px rgba(255, 193, 7, 0.2);
        }
        .nav-menu {
            background: #1E1E1E;
            padding: 15px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .nav-btn {
            padding: 12px 24px;
            background: transparent;
            color: #D1D5DB;
            border: 1px solid #333;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
        }
        .nav-btn:hover { transform: translateY(-2px); background: #333; }
        .nav-btn.active { background: #FFC107; color: #121212; border-color: #FFC107; font-weight: 700; }
        .stats-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-box {
            background: #1E1E1E;
            padding: 20px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            text-align: center;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        .stat-box::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: #FFC107;
        }
        .stat-box:hover { transform: translateY(-5px); box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5); }
        .stat-icon { font-size: 32px; margin-bottom: 10px; }
        .stat-value { font-size: 36px; font-weight: 700; color: #F3F4F6; margin-bottom: 5px; }
        .stat-label { font-size: 13px; color: #9CA3AF; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }
        .card {
            background: #1E1E1E;
            padding: 25px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid #333;
        }
        .card-title { color: #FFC107; font-size: 20px; font-weight: 700; }
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .btn-primary {
            background: #FFC107;
            color: #121212;
        }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(255, 193, 7, 0.3); background: #F5B301; }
        .filter-tabs { display: flex; gap: 10px; margin-bottom: 20px; }
        .tab {
            padding: 10px 20px;
            background: #2D2D2D;
            color: #D1D5DB;
            border: 1px solid #444;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        .tab.active { background: #FFC107; color: #121212; border-color: #FFC107; }
        .attendance-table { width: 100%; border-collapse: collapse; }
        .attendance-table thead { background: #FFC107; color: #121212; }
        .attendance-table th {
            padding: 15px;
            text-align: left;
            font-weight: 700;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }
        .attendance-table td {
            padding: 15px;
            border-bottom: 1px solid #333;
            color: #D1D5DB;
            font-size: 14px;
        }
        .attendance-table tbody tr {
            background: #1E1E1E;
            transition: all 0.3s ease;
        }
        .attendance-table tbody tr:hover { background: #2D2D2D; transform: scale(1.01); }
        .status-badge {
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            display: inline-block;
        }
        .status-present { background: rgba(72, 187, 120, 0.2); color: #68d391; border: 1px solid #68d391; }
        .status-absent { background: rgba(245, 101, 101, 0.2); color: #fc8181; border: 1px solid #fc8181; }
        .status-late { background: rgba(237, 137, 54, 0.2); color: #f6ad55; border: 1px solid #f6ad55; }
        .status-leave { background: rgba(159, 122, 234, 0.2); color: #b794f4; border: 1px solid #b794f4; }
        .time-cell { display: flex; flex-direction: column; gap: 3px; }
        .time-in { color: #68d391; font-weight: 600; }
        .time-out { color: #fc8181; font-weight: 600; }
        .total-hours {
            background: rgba(49, 151, 149, 0.2);
            color: #4fd1c5;
            padding: 4px 10px;
            border-radius: 12px;
            font-weight: 600;
            font-size: 12px;
            border: 1px solid #4fd1c5;
        }
        .loading { text-align: center; padding: 20px; color: #9CA3AF; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fa-solid fa-clipboard-list"></i> Attendance Management</h1>
            <div class="date-selector">
                <label style="color: #4a5568; font-weight: 600;">Select Date:</label>
                <input type="date" class="date-input" id="attendanceDate">
                <button class="btn btn-primary" onclick="loadAttendanceData()"><i class="fa-solid fa-chart-bar"></i> Load Data</button>
            </div>
        </div>

        <nav class="nav-menu">
            <a href="dashboard.html" class="nav-btn">Dashboard</a>
            <a href="cctv.html" class="nav-btn">CCTV Feeds</a>
            <a href="violations.html" class="nav-btn">Violations</a>
            <a href="attendance.html" class="nav-btn active">Attendance</a>
            <a href="salary.html" class="nav-btn">Salary & Fines</a>
            <a href="workers.html" class="nav-btn">Workers</a>
            <a href="health.html" class="nav-btn">Health Alerts</a>
            <a href="face-recognition.html" class="nav-btn">Face Recognition</a>
        </nav>

        <div class="stats-row">
            <div class="stat-box">
                <div class="stat-icon"><i class="fa-solid fa-clipboard-check"></i></div>
                <div class="stat-value" id="presentCount">...</div>
                <div class="stat-label">Present</div>
            </div>
            <div class="stat-box">
                <div class="stat-icon"><i class="fa-solid fa-xmark"></i></div>
                <div class="stat-value" id="absentCount">...</div>
                <div class="stat-label">Absent</div>
            </div>
            <div class="stat-box">
                <div class="stat-icon"><i class="fa-solid fa-clock"></i></div>
                <div class="stat-value" id="lateCount">...</div>
                <div class="stat-label">Late Arrivals</div>
            </div>
            <div class="stat-box">
                <div class="stat-icon"><i class="fa-solid fa-umbrella-beach"></i></div>
                <div class="stat-value" id="leaveCount">...</div>
                <div class="stat-label">On Leave</div>
            </div>
            <div class="stat-box">
                <div class="stat-icon"><i class="fa-solid fa-stopwatch"></i></div>
                <div class="stat-value" id="avgHours">...</div>
                <div class="stat-label">Avg Hours</div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h2 class="card-title">Daily Attendance Record</h2>
            </div>

            <div style="overflow-x: auto;">
                <table class="attendance-table">
                    <thead>
                        <tr>
                            <th>Worker ID</th>
                            <th>Name</th>
                            <th>Check-In</th>
                            <th>Check-Out</th>
                            <th>Working Hours</th>
                            <th>Status</th>
                            <th>Location</th>
                        </tr>
                    </thead>
                    <tbody id="attendanceTableBody">
                        <tr><td colspan="7" class="loading">Loading attendance data...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        const API_BASE = 'http://localhost:4000/api';

        // Set today's date by default
        document.getElementById('attendanceDate').value = new Date().toISOString().split('T')[0];

        // Load attendance statistics
        async function loadStats() {
            try {
                const response = await fetch(`${API_BASE}/attendance/stats/today`);
                const stats = await response.json();
                
                document.getElementById('presentCount').textContent = stats.present_count || 0;
                document.getElementById('absentCount').textContent = stats.absent_count || 0;
                document.getElementById('lateCount').textContent = stats.late_count || 0;
                document.getElementById('leaveCount').textContent = stats.leave_count || 0;
                document.getElementById('avgHours').textContent = stats.avg_hours ? stats.avg_hours.toFixed(1) + 'h' : '0h';
            } catch (error) {
                console.error('Error loading stats:', error);
            }
        }

        // Load attendance data
        async function loadAttendanceData() {
            try {
                const selectedDate = document.getElementById('attendanceDate').value;
                const response = await fetch(`${API_BASE}/attendance/date/${selectedDate}`);
                const attendance = await response.json();
                
                const tbody = document.getElementById('attendanceTableBody');
                
                if (attendance.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 30px;">No attendance records found for this date</td></tr>';
                    return;
                }
                
                tbody.innerHTML = attendance.map(a => {
                    const checkIn = a.check_in_time ? new Date(a.check_in_time).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) : '-';
                    const checkOut = a.check_out_time ? new Date(a.check_out_time).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) : 'In Progress';
                    const hours = a.working_hours || 0;
                    
                    return `
                        <tr>
                            <td><strong>${a.worker_id}</strong></td>
                            <td>${a.name}</td>
                            <td>
                                <div class="time-cell">
                                    <span class="time-in">↓ ${checkIn}</span>
                                </div>
                            </td>
                            <td>
                                <div class="time-cell">
                                    <span class="time-out">↑ ${checkOut}</span>
                                </div>
                            </td>
                            <td><span class="total-hours">${hours} hrs</span></td>
                            <td><span class="status-badge status-${a.status}">${a.status.toUpperCase()}</span></td>
                            <td>${a.location || 'N/A'}</td>
                        </tr>
                    `;
                }).join('');
            } catch (error) {
                console.error('Error loading attendance:', error);
                document.getElementById('attendanceTableBody').innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 30px;">Error loading attendance data</td></tr>';
            }
        }

        // Initialize
        loadStats();
        loadAttendanceData();

        // Refresh every 30 seconds
        setInterval(() => {
            loadStats();
            loadAttendanceData();
        }, 30000);
    </script>

    <script>
    // ========== ADD THIS TO EVERY PAGE ==========
    // Authentication check
    window.addEventListener('load', () => {
        const token = localStorage.getItem('token');
        const user = JSON.parse(localStorage.getItem('user') || '{}');
        
        if (!token) {
            // Not logged in, redirect to login
            window.location.href = 'login.html';
            return;
        }
        
        // User is logged in, display their name if there's a user display element
        const userDisplay = document.getElementById('userDisplay');
        if (userDisplay) {
            userDisplay.textContent = user.full_name || 'User';
        }
    });
    
    // Logout function
    function handleLogout() {
        if (confirm('Are you sure you want to logout?')) {
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            window.location.href = 'login.html';
        }
    }
    // ========== END OF AUTH CODE ==========
    </script>

    <script src="auth.js"></script>
</body>
</html>
const API_BASE = 'http://localhost:4000/api';

const PAGE_ROLE_PERMISSIONS = {
    'dashboard.html': ['admin', 'safety officer', 'hr', 'monitor', 'accounts', 'supervisor', 'worker'],
    'attendance.html': ['admin', 'safety officer', 'hr', 'supervisor'],
    'health.html': ['admin', 'safety officer', 'hr', 'supervisor'],
    'violations.html': ['admin', 'safety officer', 'supervisor'],
    'salary.html': ['admin', 'hr', 'accounts'],
    'workers.html': ['admin', 'hr', 'supervisor'],
    'cctv.html': ['admin', 'monitor', 'supervisor'],
    'face-recognition.html': ['admin', 'monitor', 'supervisor'],
};

function getPageName() {
    let page = window.location.pathname.split('/').pop();
    if (!page) {
        return 'dashboard.html';
    }
    if (!page.endsWith('.html')) {
        page = page + '.html';
    }
    return page;
}

function getStoredUser() {
    try {
        return JSON.parse(localStorage.getItem('user') || 'null');
    } catch (error) {
        return null;
    }
}

function redirectToLogin() {
    window.location.href = 'login.html';
}

function redirectToDashboard() {
    window.location.href = 'dashboard.html';
}

function applyNavPermissions(user) {
    if (!user) {
        return;
    }

    document.querySelectorAll('.nav-menu .nav-btn').forEach((btn) => {
        const href = btn.getAttribute('href');
        const allowed = PAGE_ROLE_PERMISSIONS[href];
        if (allowed && !allowed.includes(user.role)) {
            btn.style.display = 'none';
        }
    });
}

function protectPageAccess() {
    const page = getPageName();
    const token = localStorage.getItem('token');
    const user = getStoredUser();

    if (page === 'login.html' || page === 'signup.html') {
        if (token && user) {
            redirectToDashboard();
        }
        return;
    }

    if (!token || !user) {
        redirectToLogin();
        return;
    }

    const allowedRoles = PAGE_ROLE_PERMISSIONS[page];
    if (allowedRoles && !allowedRoles.includes(user.role)) {
        alert('Access denied: your role does not have permission to view this page.');
        redirectToDashboard();
        return;
    }

    applyNavPermissions(user);
}

window.addEventListener('load', protectPageAccess);

if (!window.handleLogout) {
    window.handleLogout = function () {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = 'login.html';
    };
}

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CCTV Live Feed</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #121212;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            padding: 20px;
        }

        .header {
            background: #1E1E1E;
            padding: 20px 30px;
            border: 1px solid #333;
            border-radius: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }

        .header-left {
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .logo {
            font-size: 24px;
            font-weight: 700;
            color: #FFC107;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .camera-title {
            color: #9CA3AF;
            font-size: 14px;
            font-weight: 400;
        }

        .status-badge {
            background: rgba(239, 68, 68, 0.2);
            border: 1px solid #ef4444;
            color: #ef4444;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .status-badge.live {
            background: rgba(34, 197, 94, 0.2);
            border-color: #22c55e;
            color: #22c55e;
        }

        .recording-dot {
            width: 8px;
            height: 8px;
            background: currentColor;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .main-content {
            flex: 1;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 500px;
        }

        .video-container {
            width: 100%;
            max-width: 900px;
            background: #1E1E1E;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            border: 1px solid #333;
        }

        .camera-feed {
            position: relative;
            background: #000;
            aspect-ratio: 16/9;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }

        .feed-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(to bottom, rgba(0,0,0,0.6) 0%, transparent 20%, transparent 80%, rgba(0,0,0,0.6) 100%);
            pointer-events: none;
            z-index: 1;
        }

        #videoPlayer {
            width: 100%;
            height: 100%;
            object-fit: contain;
        }

        .feed-placeholder {
            position: absolute;
            color: #9CA3AF;
            font-size: 18px;
            text-align: center;
            z-index: 2;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            background: #1E1E1E !important;
            width: 100%;
            height: 100%;
        }

        .feed-placeholder.hidden {
            display: none;
        }

        .feed-placeholder .icon {
            font-size: 64px;
            margin-bottom: 20px;
            opacity: 0.5;
        }

        .live-indicator {
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(239, 68, 68, 0.95);
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
            z-index: 3;
        }

        .timestamp {
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(0, 0, 0, 0.8);
            color: #FFC107;
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            font-family: 'Courier New', monospace;
            z-index: 3;
            border: 1px solid #333;
        }

        .camera-info-bar {
            background: #1E1E1E;
            padding: 20px 30px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 30px;
            border-top: 1px solid #333;
        }

        .info-item {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .info-label {
            color: #9CA3AF;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .info-value {
            color: #F3F4F6;
            font-size: 14px;
            font-weight: 600;
        }

        .ai-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(255, 193, 7, 0.2);
            color: #FFC107;
            border: 1px solid #FFC107;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            width: fit-content;
        }

        .error-message {
            color: #ef4444;
            font-size: 13px;
            margin-top: 10px;
            padding: 10px;
            background: rgba(239, 68, 68, 0.1);
            border-left: 3px solid #ef4444;
            border-radius: 4px;
        }

        @media (max-width: 768px) {
            .main-content {
                min-height: 300px;
            }

            .video-container {
                max-width: 100%;
            }

            .camera-info-bar {
                grid-template-columns: repeat(2, 1fr);
                gap: 15px;
                padding: 15px 20px;
            }

            .header {
                flex-direction: column;
                gap: 15px;
                align-items: flex-start;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-left">
            <div class="logo">
                <i class="fa-solid fa-video"></i> CCTV Live
            </div>
            <div class="camera-title">Camera 1 - Main Entrance</div>
        </div>
        <div style="display: flex; align-items: center; gap: 15px;">
            <select id="cameraSelect" style="padding: 8px 14px; background: rgba(30,41,59,0.8); color: #f1f5f9; border: 1px solid rgba(255,255,255,0.2); border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer;">
                <option value="0">Laptop Webcam</option>
                <option value="1">External USB Camera</option>
                <option value="imou">Imou CCTV Camera</option>
            </select>
            <div class="status-badge" id="statusBadge">
                <span class="recording-dot"></span>
                CONNECTING
            </div>
        </div>
    </div>

    <div class="main-content">
        <div class="video-container">
            <div class="camera-feed" style="background:#000;">
                <div class="live-indicator" style="z-index: 10;">
                    <span class="recording-dot" style="animation: pulse 1s infinite;"></span>
                    AI OVERLAY ACTIVE
                </div>
                <div class="timestamp" id="timestamp" style="z-index: 10;">00:00:00</div>
                
                <!-- MJPEG Native Stream injected directly from Python -->
                <img id="videoPlayer" src="http://127.0.0.1:5001/video_feed" style="width: 100%; height: 100%; object-fit: contain; position: absolute; top: 0; left: 0;" onerror="handleStreamError()" />
                
                <div class="feed-placeholder" id="loadingPlaceholder">
                    <div class="icon"><i class="fa-solid fa-robot"></i></div>
                    <div id="statusText" style="color: #FFC107; font-weight:bold;">Initializing Dual AI Stream...</div>
                    <div style="font-size: 14px; color: #9CA3AF; margin-top: 10px;">Please ensure `intelligent_cctv.py` is running</div>
                </div>
            </div>
            
            <div class="camera-info-bar">
                <div class="info-item">
                    <div class="info-label">Location</div>
                    <div class="info-value">Main Gate Entry</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Resolution</div>
                    <div class="info-value">1920×1080 HD</div>
                </div>
                <div class="info-item">
                    <div class="info-label">YOLO Tracking</div>
                    <div class="info-value">Smooth Sync</div>
                </div>
                <div class="info-item">
                    <div class="info-label">AI Status</div>
                    <div class="info-value">
                        <span class="ai-badge" id="aiStatusBadge"><i class="fa-solid fa-bolt"></i> ONLINE</span>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
    // ========== AUTH CHECK ==========
    window.addEventListener('load', () => {
        const token = localStorage.getItem('token');
        if (!token) {
            window.location.href = 'login.html';
            return;
        }
    });
    function handleLogout() {
        if (confirm('Are you sure you want to logout?')) {
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            window.location.href = 'login.html';
        }
    }
    // ========== END AUTH ==========
    </script>

    <script>
        function updateTimestamp() {
            const now = new Date();
            const timeString = now.toLocaleTimeString('en-US', { 
                hour12: false,
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            document.getElementById('timestamp').textContent = timeString;
        }

        updateTimestamp();
        setInterval(updateTimestamp, 1000);

        const img = document.getElementById('videoPlayer');
        const placeholder = document.getElementById('loadingPlaceholder');
        const statusBadge = document.getElementById('statusBadge');
        const cameraSelect = document.getElementById('cameraSelect');
        
        // Load current camera setting from Python backend
        fetch('http://127.0.0.1:5001/get_camera')
            .then(r => r.json())
            .then(data => { cameraSelect.value = data.camera; })
            .catch(() => {});

        // Camera switch handler
        cameraSelect.addEventListener('change', async () => {
            const source = cameraSelect.value;
            statusBadge.className = 'status-badge';
            statusBadge.innerHTML = '<span class="recording-dot"></span> SWITCHING...';
            
            try {
                await fetch('http://127.0.0.1:5001/set_camera', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ source: source })
                });
                // Reload the MJPEG stream with a cache-busting param
                img.src = 'http://127.0.0.1:5001/video_feed?' + new Date().getTime();
            } catch(e) {
                console.error('Camera switch failed:', e);
            }
        });

        // Hide placeholder once stream successfully loads a frame
        img.onload = function() {
            placeholder.classList.add('hidden');
            statusBadge.className = 'status-badge live';
            statusBadge.innerHTML = '<span class="recording-dot"></span> LIVE AI FEED';
        };

        function handleStreamError() {
            img.style.display = 'none';
            placeholder.classList.remove('hidden');
            document.getElementById('statusText').innerHTML = "Cannot connect to Stream.<br>Run <code>python intelligent_cctv.py</code>";
            document.getElementById('statusText').style.color = '#ef4444';
            statusBadge.className = 'status-badge';
            statusBadge.innerHTML = '<span class="recording-dot" style="background:#ef4444;"></span> OFFLINE';
            
            // Try to reconnect every 3 seconds
            setTimeout(() => {
                img.style.display = 'block';
                img.src = "http://127.0.0.1:5001/video_feed?" + new Date().getTime();
            }, 3000);
        }
    </script>
    <script src="auth.js"></script>
</body>
</html>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Construction Site Safety</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #121212;
            color: #F3F4F6;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header {
            background: #1E1E1E;
            padding: 25px 30px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { 
            color: #FFC107; 
            font-size: 28px; 
            font-weight: 700; 
            margin: 0;
        }
        .logout-btn {
            padding: 12px 24px;
            background: transparent;
            color: #D1D5DB;
            border: 1px solid #444;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        .logout-btn:hover { 
            background: #f56565;
            color: #121212;
            border-color: #f56565;
            transform: translateY(-2px); 
        }
        .time-display { 
            font-size: 16px; 
            color: #9CA3AF; 
            font-weight: 500; 
        }
        .nav-menu {
            background: #1E1E1E;
            padding: 15px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .nav-btn {
            padding: 12px 24px;
            background: transparent;
            color: #D1D5DB;
            border: 1px solid #333;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
        }
        .nav-btn:hover { 
            background: #333;
            transform: translateY(-2px); 
        }
        .nav-btn.active { 
            background: #FFC107; 
            color: #121212;
            border-color: #FFC107;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: #1E1E1E;
            padding: 25px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        .stat-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: #FFC107;
        }
        .stat-card:hover { 
            transform: translateY(-5px); 
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5); 
        }
        .stat-icon { font-size: 36px; margin-bottom: 10px; }
        .stat-title { 
            color: #9CA3AF; 
            font-size: 14px; 
            font-weight: 600; 
            text-transform: uppercase; 
            letter-spacing: 0.5px; 
            margin-bottom: 8px; 
        }
        .stat-value { 
            color: #F3F4F6; 
            font-size: 32px; 
            font-weight: 700; 
            margin-bottom: 5px; 
        }
        .stat-subtitle { 
            color: #6B7280; 
            font-size: 12px; 
        }
        .content-grid { 
            display: grid; 
            grid-template-columns: 2fr 1fr; 
            gap: 20px; 
            margin-bottom: 30px; 
        }
        .chart-card {
            background: #1E1E1E;
            padding: 25px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }
        .chart-card h2 { 
            color: #FFC107; 
            font-size: 20px; 
            font-weight: 700; 
            margin-bottom: 20px; 
            padding-bottom: 15px; 
            border-bottom: 1px solid #333; 
        }
        .activity-list { 
            list-style: none; 
        }
        .activity-item { 
            padding: 15px; 
            border-bottom: 1px solid #333; 
            transition: background 0.3s ease; 
        }
        .activity-item:hover { 
            background: #2D2D2D; 
        }
        .activity-item:last-child { 
            border-bottom: none; 
        }
        .activity-time { 
            color: #9CA3AF; 
            font-size: 12px; 
            display: block; 
            margin-bottom: 5px; 
        }
        .activity-text { 
            color: #D1D5DB; 
            font-size: 14px; 
        }
        .alert-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            margin-left: 8px;
        }
        .alert-badge.danger { 
            background: rgba(245, 101, 101, 0.2); 
            color: #fc8181; 
            border: 1px solid #fc8181;
        }
        .alert-badge.warning { 
            background: rgba(237, 137, 54, 0.2); 
            color: #f6ad55; 
            border: 1px solid #f6ad55;
        }
        .alert-badge.success { 
            background: rgba(72, 187, 120, 0.2); 
            color: #68d391; 
            border: 1px solid #68d391;
        }
        .full-width-card { 
            grid-column: 1 / -1; 
        }
        .workers-table { 
            width: 100%; 
            border-collapse: collapse; 
            margin-top: 15px; 
        }
        .workers-table th {
            background: #FFC107;
            color: #121212;
            padding: 15px;
            text-align: left;
            font-weight: 700;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }
        .workers-table td { 
            padding: 15px; 
            border-bottom: 1px solid #333; 
            color: #D1D5DB; 
            font-size: 14px; 
        }
        .workers-table tr:hover { 
            background: #2D2D2D; 
        }
        .status-badge {
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            display: inline-block;
        }
        .status-present { 
            background: rgba(72, 187, 120, 0.2); 
            color: #68d391; 
            border: 1px solid #68d391;
        }
        .status-absent { 
            background: rgba(245, 101, 101, 0.2); 
            color: #fc8181; 
            border: 1px solid #fc8181;
        }
        .status-late { 
            background: rgba(237, 137, 54, 0.2); 
            color: #f6ad55; 
            border: 1px solid #f6ad55;
        }
        .loading { 
            text-align: center; 
            padding: 20px; 
            color: #9CA3AF; 
        }
        @media (max-width: 768px) {
            .content-grid { 
                grid-template-columns: 1fr; 
            }
            .header { 
                flex-direction: column; 
                gap: 15px; 
            }
            .stats-grid { 
                grid-template-columns: 1fr; 
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fa-solid fa-helmet-safety"></i> Intelligent Surveillance System</h1>
            <button class="logout-btn" onclick="handleLogout()"><i class="fa-solid fa-arrow-right-from-bracket"></i> Logout</button>
        </div>

        <nav class="nav-menu">
            <a href="dashboard.html" class="nav-btn active"><i class="fa-solid fa-chart-line"></i> Dashboard</a>
            <a href="cctv.html" class="nav-btn"><i class="fa-solid fa-video"></i> CCTV Feeds</a>
            <a href="violations.html" class="nav-btn"><i class="fa-solid fa-triangle-exclamation"></i> Violations</a>
            <a href="attendance.html" class="nav-btn"><i class="fa-solid fa-clipboard-check"></i> Attendance</a>
            <a href="face-recognition.html" class="nav-btn"><i class="fa-solid fa-camera"></i> Webcam Attendance</a>
            <a href="salary.html" class="nav-btn"><i class="fa-solid fa-money-bill"></i> Salary & Fines</a>
            <a href="workers.html" class="nav-btn"><i class="fa-solid fa-hard-hat"></i> Workers</a>
            <a href="health.html" class="nav-btn"><i class="fa-solid fa-truck-medical"></i> Health Alerts</a>
        </nav>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon"><i class="fa-solid fa-users"></i></div>
                <div class="stat-title">Total Workers</div>
                <div class="stat-value" id="totalWorkers">...</div>
                <div class="stat-subtitle">Registered on site</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="fa-solid fa-clipboard-check"></i></div>
                <div class="stat-title">Present Today</div>
                <div class="stat-value" id="presentToday">...</div>
                <div class="stat-subtitle">Active workers</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="fa-solid fa-triangle-exclamation"></i></div>
                <div class="stat-title">PPE Violations</div>
                <div class="stat-value" id="ppeViolations">...</div>
                <div class="stat-subtitle">Today's violations</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="fa-solid fa-bell"></i></div>
                <div class="stat-title">Health Alerts</div>
                <div class="stat-value" id="healthAlerts">...</div>
                <div class="stat-subtitle">Active emergencies</div>
            </div>
        </div>

        <div class="content-grid">
            <div class="chart-card">
                <h2>Recent Violations</h2>
                <ul class="activity-list" id="violationsList">
                    <li class="activity-item loading">Loading violations...</li>
                </ul>
            </div>
            <div class="chart-card">
                <h2>Recent Activity</h2>
                <ul class="activity-list" id="activityList">
                    <li class="activity-item loading">Loading activities...</li>
                </ul>
            </div>
        </div>

        <div class="chart-card full-width-card">
            <h2>Today's Worker Attendance</h2>
            <table class="workers-table">
                <thead>
                    <tr>
                        <th>Worker ID</th>
                        <th>Name</th>
                        <th>Check-In Time</th>
                        <th>Check-Out Time</th>
                        <th>Status</th>
                        <th>Working Hours</th>
                    </tr>
                </thead>
                <tbody id="workersTableBody">
                    <tr><td colspan="6" class="loading">Loading attendance data...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        // Authentication check
        window.addEventListener('load', () => {
            const token = localStorage.getItem('token');
            if (!token) {
                window.location.href = 'login.html';
                return;
            }
        });

        // Logout function
        function handleLogout() {
            if (confirm('Are you sure you want to logout?')) {
                localStorage.removeItem('token');
                localStorage.removeItem('user');
                window.location.href = 'login.html';
            }
        }

        const API_BASE = 'http://localhost:4000/api';

        async function loadWorkerStats() {
            try {
                const response = await fetch(`${API_BASE}/workers/stats/summary`);
                const stats = await response.json();
                document.getElementById('totalWorkers').textContent = stats.total_workers || 0;
            } catch (error) {
                console.error('Error loading worker stats:', error);
                document.getElementById('totalWorkers').textContent = 'Error';
            }
        }

        async function loadAttendanceStats() {
            try {
                const response = await fetch(`${API_BASE}/attendance/stats/today`);
                const stats = await response.json();
                document.getElementById('presentToday').textContent = stats.present_count || 0;
            } catch (error) {
                console.error('Error loading attendance stats:', error);
            }
        }

        async function loadViolationStats() {
            try {
                const response = await fetch(`${API_BASE}/violations/stats/summary`);
                const stats = await response.json();
                document.getElementById('ppeViolations').textContent = stats.today || 0;
            } catch (error) {
                console.error('Error loading violation stats:', error);
                document.getElementById('ppeViolations').textContent = 'Error';
            }
        }

        async function loadHealthStats() {
            try {
                const response = await fetch(`${API_BASE}/health/stats/summary`);
                const stats = await response.json();
                document.getElementById('healthAlerts').textContent = stats.critical || 0;
            } catch (error) {
                console.error('Error loading health stats:', error);
                document.getElementById('healthAlerts').textContent = 'Error';
            }
        }

        async function loadRecentViolations() {
            try {
                const today = new Date().toISOString().split('T')[0];
                const response = await fetch(`${API_BASE}/violations?date_from=${today}&date_to=${today}`);
                const violations = await response.json();
                const violationsList = document.getElementById('violationsList');
                
                if (violations.length === 0) {
                    violationsList.innerHTML = '<li class="activity-item"><span class="activity-text">No violations today</span></li>';
                    return;
                }
                
                violationsList.innerHTML = violations.slice(0, 5).map(v => {
                    const time = new Date(v.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
                    const badgeClass = v.severity === 'high' ? 'danger' : v.severity === 'medium' ? 'warning' : 'success';
                    return `
                        <li class="activity-item">
                            <span class="activity-time">${time}</span>
                            <span class="activity-text">${v.worker_name} - ${v.violation_type} violation <span class="alert-badge ${badgeClass}">${v.severity.toUpperCase()}</span></span>
                        </li>
                    `;
                }).join('');
            } catch (error) {
                console.error('Error loading violations:', error);
                document.getElementById('violationsList').innerHTML = '<li class="activity-item"><span class="activity-text">Error loading violations</span></li>';
            }
        }

        async function loadTodayAttendance() {
            try {
                const today = new Date().toISOString().split('T')[0];
                const response = await fetch(`${API_BASE}/attendance/date/${today}`);
                const attendance = await response.json();
                const tbody = document.getElementById('workersTableBody');
                
                if (attendance.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 30px;">No attendance records for today</td></tr>';
                    return;
                }
                
                tbody.innerHTML = attendance.map(a => {
                    const checkIn = a.check_in_time ? new Date(a.check_in_time).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) : '-';
                    const checkOut = a.check_out_time ? new Date(a.check_out_time).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) : 'In Progress';
                    const hours = a.working_hours || '-';
                    return `
                        <tr>
                            <td><strong>${a.worker_id}</strong></td>
                            <td>${a.name}</td>
                            <td>${checkIn}</td>
                            <td>${checkOut}</td>
                            <td><span class="status-badge status-${a.status}">${a.status.toUpperCase()}</span></td>
                            <td>${hours} hrs</td>
                        </tr>
                    `;
                }).join('');
            } catch (error) {
                console.error('Error loading attendance:', error);
                document.getElementById('workersTableBody').innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 30px;">Error loading attendance data</td></tr>';
            }
        }

        async function loadRecentActivity() {
            try {
                const today = new Date().toISOString().split('T')[0];
                const response = await fetch(`${API_BASE}/attendance/date/${today}`);
                const attendance = await response.json();
                const activityList = document.getElementById('activityList');
                const recentAttendance = attendance.slice(0, 5);
                
                if (recentAttendance.length === 0) {
                    activityList.innerHTML = '<li class="activity-item"><span class="activity-text">No recent activity</span></li>';
                    return;
                }
                
                activityList.innerHTML = recentAttendance.map(a => {
                    const time = new Date(a.check_in_time).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
                    const badgeClass = a.status === 'present' ? 'success' : a.status === 'late' ? 'warning' : 'danger';
                    return `
                        <li class="activity-item">
                            <span class="activity-time">${time}</span>
                            <span class="activity-text">${a.name} checked in <span class="alert-badge ${badgeClass}">${a.status.toUpperCase()}</span></span>
                        </li>
                    `;
                }).join('');
            } catch (error) {
                console.error('Error loading activity:', error);
                document.getElementById('activityList').innerHTML = '<li class="activity-item"><span class="activity-text">Error loading activity</span></li>';
            }
        }

        async function loadDashboardData() {
            await Promise.all([
                loadWorkerStats(),
                loadAttendanceStats(),
                loadViolationStats(),
                loadHealthStats(),
                loadRecentViolations(),
                loadRecentActivity(),
                loadTodayAttendance()
            ]);
        }

        loadDashboardData();
        setInterval(loadDashboardData, 30000);
    </script>
    <script src="auth.js"></script>
</body>
</html>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Webcam Face Recognition Attendance</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #121212;
            color: #F3F4F6;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header {
            background: #1E1E1E;
            padding: 25px 30px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
        }
        .header h1 { color: #FFC107; font-size: 28px; font-weight: 700; }
        .nav-menu {
            background: #1E1E1E;
            padding: 15px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .nav-btn {
            padding: 12px 24px;
            background: transparent;
            color: #D1D5DB;
            border: 1px solid #333;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
        }
        .nav-btn:hover { transform: translateY(-2px); background: #333; }
        .nav-btn.active { background: #FFC107; color: #121212; border-color: #FFC107; font-weight: 700; }
        .content-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; }
        .card {
            background: #1E1E1E;
            padding: 25px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }
        .card h2 {
            color: #FFC107;
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid #333;
        }
        .video-container {
            position: relative;
            background: #000;
            border-radius: 12px;
            overflow: hidden;
            margin-bottom: 20px;
            aspect-ratio: 16/9;
            border: 1px solid #333;
        }
        #webcamVideo {
            width: 100%;
            height: 100%;
            object-fit: cover;
            transform: scaleX(-1); /* Mirror effect */
        }
        .live-badge {
            position: absolute;
            top: 15px;
            left: 15px;
            background: rgba(239, 68, 68, 0.9);
            color: white;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
            border: 1px solid #ef4444;
        }
        .recording-dot {
            width: 10px;
            height: 10px;
            background: white;
            border-radius: 50%;
            animation: blink 1s infinite;
        }
        @keyframes blink {
            0%, 50% { opacity: 1; }
            51%, 100% { opacity: 0; }
        }
        .controls {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 20px;
        }
        .btn {
            padding: 15px 30px;
            border: none;
            border-radius: 8px;
            font-size: 18px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }
        .btn-scan { background: #FFC107; color: #121212; }
        .btn:hover { transform: translateY(-2px); background: #F5B301; }
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        .result-box {
            padding: 20px;
            border-radius: 10px;
            margin-top: 15px;
            text-align: center;
            font-size: 18px;
            font-weight: 600;
            display: none;
        }
        .result-success { background: rgba(72, 187, 120, 0.2); color: #68d391; border: 1px solid #68d391; }
        .result-error { background: rgba(245, 101, 101, 0.2); color: #fc8181; border: 1px solid #fc8181; }
        
        .log-container {
            max-height: 400px;
            overflow-y: auto;
        }
        .log-item {
            padding: 12px;
            background: #2D2D2D;
            border-left: 4px solid #FFC107;
            border-radius: 6px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .log-time {
            font-size: 11px;
            color: #9CA3AF;
            margin-bottom: 5px;
        }
        .log-text {
            font-size: 14px;
            color: #F3F4F6;
            font-weight: bold;
        }
        .log-success { border-left-color: #68d391; }
        .log-error { border-left-color: #fc8181; }
        
        select.btn {
            background: #2D2D2D;
            color: #F3F4F6;
            border: 1px solid #444;
        }
        select.btn:hover {
            background: #333;
            transform: none;
        }

        @media (max-width: 768px) {
            .content-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fa-solid fa-bullseye"></i> Smart Webcam Attendance</h1>
        </div>

        <nav class="nav-menu">
            <a href="dashboard.html" class="nav-btn">Dashboard</a>
            <a href="cctv.html" class="nav-btn">CCTV Feeds</a>
            <a href="face_registration.html" class="nav-btn">Register Faces</a>
            <a href="attendance.html" class="nav-btn">Attendance</a>
            <a href="workers.html" class="nav-btn">Workers</a>
            <a href="face-recognition.html" class="nav-btn active">Webcam Attendance</a>
        </nav>

        <div class="content-grid">
            <div class="card">
                <h2><i class="fa-solid fa-camera"></i> Step In Front of the Camera</h2>
                
                <div class="video-container">
                    <video id="webcamVideo" autoplay muted playsinline></video>
                    <div class="live-badge">
                        <div class="recording-dot"></div>
                        STANDBY
                    </div>
                </div>
                
                <canvas id="snapshotCanvas" style="display: none;"></canvas>

                <div class="controls" style="flex-direction: column; align-items: center;">
                    <div id="cameraControls" style="margin-bottom: 15px; width: 100%; max-width: 400px;">
                        <label for="videoSource" style="display: block; color: #9CA3AF; font-weight: 600; margin-bottom: 8px; font-size: 14px;"><i class="fa-solid fa-video"></i> Select Camera Source:</label>
                        <select id="videoSource" class="btn" style="width: 100%; background: #2D2D2D; color: #F3F4F6; border: 1px solid #444; font-size: 14px; padding: 10px; text-align: left;">
                            <option value="">Loading cameras...</option>
                        </select>
                    </div>

                    <button id="scanBtn" class="btn btn-scan" onclick="scanFace()">
                        <i class="fa-solid fa-circle-check" style="color: #68d391;"></i> Mark Attendance (Scan Face)
                    </button>
                </div>

                <div id="resultBox" class="result-box"></div>
            </div>

            <div class="card">
                <h2><i class="fa-solid fa-clipboard-list"></i> Today's Logs</h2>
                <div class="log-container" id="activityLog">
                    <p style="text-align: center; color: #a0aec0; padding: 20px;">
                        No check-ins yet. Step up to scan!
                    </p>
                </div>
            </div>
        </div>
    </div>

    <script>
    // ========== AUTH CHECK ==========
    window.addEventListener('load', () => {
        const token = localStorage.getItem('token');
        if (!token) {
            window.location.href = 'login.html';
            return;
        }
    });
    function handleLogout() {
        if (confirm('Are you sure you want to logout?')) {
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            window.location.href = 'login.html';
        }
    }
    // ========== END AUTH ==========
    </script>

    <script>
        const video = document.getElementById('webcamVideo');
        const canvas = document.getElementById('snapshotCanvas');
        const scanBtn = document.getElementById('scanBtn');
        const resultBox = document.getElementById('resultBox');
        
        const videoSource = document.getElementById('videoSource');
        let currentStream = null;
        
        // List cameras and start default
        async function getCameras() {
            try {
                // Request initial permission to get labels
                await navigator.mediaDevices.getUserMedia({ video: true });
                const devices = await navigator.mediaDevices.enumerateDevices();
                const videoDevices = devices.filter(device => device.kind === 'videoinput');
                
                videoSource.innerHTML = '';
                videoDevices.forEach(device => {
                    const option = document.createElement('option');
                    option.value = device.deviceId;
                    option.text = device.label || `Camera ${videoSource.length + 1}`;
                    videoSource.appendChild(option);
                });

                // Start with first camera
                if (videoDevices.length > 0) {
                    startWebcam(videoDevices[0].deviceId);
                }
            } catch (err) {
                console.error("Error listing cameras: ", err);
                videoSource.innerHTML = '<option value="">No cameras found</option>';
            }
        }

        async function startWebcam(deviceId) {
            if (currentStream) {
                currentStream.getTracks().forEach(track => track.stop());
            }

            const constraints = {
                video: { deviceId: deviceId ? { exact: deviceId } : undefined }
            };

            try {
                const stream = await navigator.mediaDevices.getUserMedia(constraints);
                currentStream = stream;
                video.srcObject = stream;
            } catch (err) {
                console.error("Error accessing webcam: ", err);
                showResult("Failed to access selected camera. Please try another.", "error");
            }
        }

        videoSource.onchange = () => startWebcam(videoSource.value);
        getCameras();

        // Scan the face and send to backend
        async function scanFace() {
            // Setup canvas context to draw image
            const context = canvas.getContext('2d');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            
            // Draw current video frame to canvas
            context.drawImage(video, 0, 0, canvas.width, canvas.height);
            
            // Get base64 string
            const base64Image = canvas.toDataURL('image/jpeg', 0.8);

            // Change button state
            scanBtn.disabled = true;
            scanBtn.textContent = '⏳ Processing...';
            hideResult();

            try {
                // Send to our Node backend face-attendance route
                const response = await fetch('/api/face-attendance/scan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image: base64Image })
                });

                const data = await response.json();
                
                if (data.success) {
                    showResult(data.message, "success");
                    addLog(data.worker.name, data.message, "success");
                } else {
                    showResult(data.message || data.error, "error");
                    addLog("Unknown", data.message || data.error, "error");
                }
            } catch (error) {
                console.error("Error sending image: ", error);
                showResult("Server error. Make sure the Node server and Python API are running.", "error");
            } finally {
                // Reset button
                setTimeout(() => {
                    scanBtn.disabled = false;
                    scanBtn.textContent = '🟢 Mark Attendance (Scan Face)';
                }, 3000); // 3 seconds cooldown
            }
        }

        function showResult(message, type) {
            resultBox.textContent = message;
            resultBox.className = `result-box result-${type}`;
            resultBox.style.display = 'block';
        }

        function hideResult() {
            resultBox.style.display = 'none';
        }

        function addLog(name, message, type) {
            const container = document.getElementById('activityLog');
            const time = new Date().toLocaleTimeString();
            
            const logItem = document.createElement('div');
            logItem.className = `log-item log-${type}`;
            logItem.innerHTML = `
                <div>
                    <div class="log-text">${name}</div>
                    <div class="log-time" style="margin-top:4px;">${message}</div>
                </div>
                <div class="log-time">${time}</div>
            `;
            
            // Remove the empty message if it exists
            if (container.firstChild && container.firstChild.tagName === 'P') {
                container.innerHTML = '';
            }
            
            container.insertBefore(logItem, container.firstChild);
        }
    </script>
    <script src="auth.js"></script>
</body>
</html>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Health Alerts Management</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #121212;
            color: #F3F4F6;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header {
            background: #1E1E1E;
            padding: 25px 30px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
        }
        .header h1 { color: #FFC107; font-size: 28px; font-weight: 700; margin-bottom: 10px; }
        .nav-menu {
            background: #1E1E1E;
            padding: 15px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .nav-btn {
            padding: 12px 24px;
            background: transparent;
            color: #D1D5DB;
            border: 1px solid #333;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
        }
        .nav-btn:hover { transform: translateY(-2px); background: #333; }
        .nav-btn.active { background: #FFC107; color: #121212; border-color: #FFC107; font-weight: 700; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: #1E1E1E;
            padding: 20px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            transition: all 0.3s ease;
            text-align: center;
            position: relative;
            overflow: hidden;
        }
        .stat-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: #FFC107;
        }
        .stat-card.critical::before { background: #fc8181; }
        .stat-card.active::before { background: #f6ad55; }
        .stat-card.resolved::before { background: #68d391; }
        .stat-card:hover { transform: translateY(-5px); box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5); }
        .stat-icon { font-size: 32px; margin-bottom: 10px; }
        .stat-value { font-size: 36px; font-weight: 700; color: #F3F4F6; margin-bottom: 5px; }
        .stat-label { font-size: 13px; color: #9CA3AF; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }
        .card {
            background: #1E1E1E;
            padding: 25px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid #333;
        }
        .card-title { color: #FFC107; font-size: 20px; font-weight: 700; }
        .filter-tabs { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
        .tab {
            padding: 10px 20px;
            background: #2D2D2D;
            color: #D1D5DB;
            border: 1px solid #444;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        .tab.active { background: #FFC107; color: #121212; border-color: #FFC107; }
        .alerts-list { display: flex; flex-direction: column; gap: 15px; }
        .alert-item {
            background: #1E1E1E;
            border: 1px solid #333;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            transition: all 0.3s ease;
            border-left: 4px solid #FFC107;
            position: relative;
        }
        .alert-item:hover { transform: translateX(5px); box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4); }
        .alert-item.critical { border-left-color: #fc8181; }
        .alert-item.high { border-left-color: #ed8936; }
        .alert-item.medium { border-left-color: #ecc94b; }
        .alert-item.low { border-left-color: #48bb78; }
        .alert-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 12px;
        }
        .alert-title { font-size: 16px; font-weight: 700; color: #F3F4F6; margin-bottom: 5px; }
        .alert-meta { display: flex; gap: 15px; color: #9CA3AF; font-size: 13px; margin-bottom: 10px; }
        .alert-description { color: #D1D5DB; font-size: 14px; line-height: 1.6; margin-bottom: 15px; }
        .severity-badge {
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            display: inline-block;
        }
        .severity-critical { background: rgba(245, 101, 101, 0.2); color: #fc8181; border: 1px solid #fc8181; }
        .severity-high { background: rgba(237, 137, 54, 0.2); color: #f6ad55; border: 1px solid #f6ad55; }
        .severity-medium { background: rgba(236, 201, 75, 0.2); color: #ecc94b; border: 1px solid #ecc94b; }
        .severity-low { background: rgba(72, 187, 120, 0.2); color: #68d391; border: 1px solid #68d391; }
        .status-badge {
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            display: inline-block;
        }
        .status-active { background: rgba(245, 101, 101, 0.2); color: #fc8181; border: 1px solid #fc8181; }
        .status-resolved { background: rgba(72, 187, 120, 0.2); color: #68d391; border: 1px solid #68d391; }
        .alert-actions {
            display: flex;
            gap: 10px;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #333;
        }
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .btn-resolve {
            background: #FFC107;
            color: #121212;
        }
        .btn-resolve:hover { background: #F5B301; }
        .btn-view {
            background: #2D2D2D;
            color: #D1D5DB;
            border: 1px solid #444;
        }
        .btn-view:hover { background: #333; }
        .btn:hover { transform: translateY(-2px); }
        .loading { text-align: center; padding: 20px; color: #9CA3AF; }
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #9CA3AF;
        }
        .empty-icon { font-size: 48px; margin-bottom: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fa-solid fa-truck-medical"></i> Health Alerts Management</h1>
            <p style="color: #718096; margin-top: 8px;">Monitor and respond to worker health incidents</p>
        </div>

        <nav class="nav-menu">
            <a href="dashboard.html" class="nav-btn">Dashboard</a>
            <a href="cctv.html" class="nav-btn">CCTV Feeds</a>
            <a href="violations.html" class="nav-btn">Violations</a>
            <a href="attendance.html" class="nav-btn">Attendance</a>
            <a href="salary.html" class="nav-btn">Salary & Fines</a>
            <a href="workers.html" class="nav-btn">Workers</a>
            <a href="health.html" class="nav-btn active">Health Alerts</a>
            <a href="face-recognition.html" class="nav-btn">Face Recognition</a>
        </nav>

        <div class="stats-grid">
            <div class="stat-card critical">
                <div class="stat-icon"><i class="fa-solid fa-bell"></i></div>
                <div class="stat-value" id="criticalCount">...</div>
                <div class="stat-label">Critical Alerts</div>
            </div>
            <div class="stat-card active">
                <div class="stat-icon"><i class="fa-solid fa-triangle-exclamation"></i></div>
                <div class="stat-value" id="activeCount">...</div>
                <div class="stat-label">Active Alerts</div>
            </div>
            <div class="stat-card resolved">
                <div class="stat-icon"><i class="fa-solid fa-clipboard-check"></i></div>
                <div class="stat-value" id="resolvedCount">...</div>
                <div class="stat-label">Resolved Today</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="fa-solid fa-stopwatch"></i></div>
                <div class="stat-value" id="avgResponse">...</div>
                <div class="stat-label">Avg Response (min)</div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h2 class="card-title">Health Alerts Feed</h2>
            </div>

            <div class="filter-tabs">
                <button class="tab active" onclick="filterAlerts('all')">All Alerts</button>
                <button class="tab" onclick="filterAlerts('critical')">Critical</button>
                <button class="tab" onclick="filterAlerts('high')">High</button>
                <button class="tab" onclick="filterAlerts('active')">Active Only</button>
                <button class="tab" onclick="filterAlerts('resolved')">Resolved</button>
            </div>

            <div class="alerts-list" id="alertsList">
                <div class="loading">Loading health alerts...</div>
            </div>
        </div>
    </div>

    <script>
        const API_BASE = 'http://localhost:4000/api';
        let allAlerts = [];
        let currentFilter = 'all';

        // Load statistics
        async function loadStats() {
            try {
                const response = await fetch(`${API_BASE}/health/stats/summary`);
                const stats = await response.json();
                
                document.getElementById('criticalCount').textContent = stats.critical || 0;
                document.getElementById('activeCount').textContent = stats.active || 0;
                document.getElementById('resolvedCount').textContent = stats.resolved || 0;
                document.getElementById('avgResponse').textContent = stats.avg_response_time || 0;
            } catch (error) {
                console.error('Error loading stats:', error);
            }
        }

        // Load all alerts
        async function loadAlerts() {
            try {
                const response = await fetch(`${API_BASE}/health`);
                allAlerts = await response.json();
                displayAlerts(allAlerts);
            } catch (error) {
                console.error('Error loading alerts:', error);
                document.getElementById('alertsList').innerHTML = '<div class="loading">Error loading health alerts</div>';
            }
        }

        // Display alerts
        function displayAlerts(alerts) {
            const container = document.getElementById('alertsList');
            
            if (alerts.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon"><i class="fa-solid fa-thumbs-up"></i></div>
                        <h3 style="color: #4a5568; margin-bottom: 8px;">No Health Alerts</h3>
                        <p>All workers are safe and healthy!</p>
                    </div>
                `;
                return;
            }
            
            container.innerHTML = alerts.map(alert => {
                const timestamp = new Date(alert.timestamp).toLocaleString('en-US', { 
                    month: 'short', 
                    day: 'numeric', 
                    hour: '2-digit', 
                    minute: '2-digit' 
                });
                
                const resolveBtn = alert.status === 'active' ? 
                    `<button class="btn btn-resolve" onclick="resolveAlert(${alert.alert_id})">✓ Mark Resolved</button>` : 
                    '<span class="status-badge status-resolved">RESOLVED</span>';
                
                return `
                    <div class="alert-item ${alert.severity}">
                        <div class="alert-header">
                            <div>
                                <div class="alert-title">${alert.alert_type}</div>
                                <div class="alert-meta">
                                    <span><i class="fa-solid fa-location-dot"></i> ${alert.location || 'Unknown location'}</span>
                                    <span><i class="fa-solid fa-hard-hat"></i> ${alert.worker_name || 'Worker ' + (alert.worker_id || 'Unknown')}</span>
                                    <span><i class="fa-regular fa-clock"></i> ${timestamp}</span>
                                </div>
                            </div>
                            <span class="severity-badge severity-${alert.severity}">${alert.severity.toUpperCase()}</span>
                        </div>
                        <div class="alert-description">
                            ${alert.description || 'No additional details available.'}
                        </div>
                        <div style="display: flex; gap: 10px; align-items: center;">
                            <span style="font-size: 12px; color: #a0aec0;">
                                Camera: ${alert.camera_name || alert.camera_id || 'N/A'}
                            </span>
                        </div>
                        <div class="alert-actions">
                            ${resolveBtn}
                            <button class="btn btn-view" onclick="viewAlertDetails(${alert.alert_id})"><i class="fa-solid fa-eye"></i> View Details</button>
                        </div>
                    </div>
                `;
            }).join('');
        }

        // Filter alerts
        function filterAlerts(filter) {
            currentFilter = filter;
            
            // Update active tab
            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
            event.target.classList.add('active');
            
            let filtered = allAlerts;
            
            switch(filter) {
                case 'critical':
                    filtered = allAlerts.filter(a => a.severity === 'critical');
                    break;
                case 'high':
                    filtered = allAlerts.filter(a => a.severity === 'high');
                    break;
                case 'active':
                    filtered = allAlerts.filter(a => a.status === 'active');
                    break;
                case 'resolved':
                    filtered = allAlerts.filter(a => a.status === 'resolved');
                    break;
            }
            
            displayAlerts(filtered);
        }

        // Resolve alert
        async function resolveAlert(alertId) {
            if (!confirm('Mark this health alert as resolved?')) return;
            
            try {
                const responseTime = Math.floor(Math.random() * 30) + 5; // Simulated response time
                
                const response = await fetch(`${API_BASE}/health/${alertId}/resolve`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ response_time: responseTime })
                });
                
                if (response.ok) {
                    alert('✅ Health alert marked as resolved!');
                    loadStats();
                    loadAlerts();
                } else {
                    alert('❌ Failed to resolve alert');
                }
            } catch (error) {
                console.error('Error resolving alert:', error);
                alert('❌ Error resolving alert');
            }
        }

        // View alert details
        function viewAlertDetails(alertId) {
            const alert = allAlerts.find(a => a.alert_id === alertId);
            if (!alert) return;
            
            const details = `
Health Alert Details
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Alert ID: ${alert.alert_id}
Type: ${alert.alert_type}
Severity: ${alert.severity.toUpperCase()}
Status: ${alert.status.toUpperCase()}

Worker Information:
- Name: ${alert.worker_name || 'Unknown'}
- ID: ${alert.worker_id || 'N/A'}

Incident Details:
- Time: ${new Date(alert.timestamp).toLocaleString()}
- Location: ${alert.location || 'Unknown'}
- Camera: ${alert.camera_name || alert.camera_id || 'N/A'}

Description:
${alert.description || 'No additional details'}

${alert.status === 'resolved' ? `
Resolution:
- Resolved at: ${new Date(alert.resolved_at).toLocaleString()}
- Response time: ${alert.response_time} minutes
` : 'Status: ACTIVE - Awaiting response'}
            `.trim();
            
            alert(details);
        }

        // Initialize
        loadStats();
        loadAlerts();

        // Auto-refresh every 15 seconds
        setInterval(() => {
            loadStats();
            loadAlerts();
        }, 15000);
    </script>

    <script>
    // ========== ADD THIS TO EVERY PAGE ==========
    // Authentication check
    window.addEventListener('load', () => {
        const token = localStorage.getItem('token');
        const user = JSON.parse(localStorage.getItem('user') || '{}');
        
        if (!token) {
            // Not logged in, redirect to login
            window.location.href = 'login.html';
            return;
        }
        
        // User is logged in, display their name if there's a user display element
        const userDisplay = document.getElementById('userDisplay');
        if (userDisplay) {
            userDisplay.textContent = user.full_name || 'User';
        }
    });
    
    // Logout function
    function handleLogout() {
        if (confirm('Are you sure you want to logout?')) {
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            window.location.href = 'login.html';
        }
    }
    // ========== END OF AUTH CODE ==========
    </script>

    <script src="auth.js"></script>
</body>
</html>
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Intelligent Surveillance System</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #121212;
            color: #F3F4F6;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .login-container {
            width: 100%;
            max-width: 400px;
        }

        .login-box {
            background: #1E1E1E;
            border: 1px solid #333;
            border-radius: 12px;
            padding: 50px 40px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            animation: slideIn 0.5s ease-out;
        }

        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(30px);
            }

            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .logo-section {
            text-align: center;
            margin-bottom: 40px;
        }

        .logo {
            font-size: 48px;
            margin-bottom: 15px;
        }

        .logo-title {
            color: #FFC107;
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 8px;
        }

        .logo-subtitle {
            color: #9CA3AF;
            font-size: 14px;
            font-weight: 500;
        }

        .form-group {
            margin-bottom: 25px;
        }

        .form-label {
            display: block;
            color: #D1D5DB;
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .form-input {
            width: 100%;
            padding: 15px 18px;
            border: 1px solid #444;
            border-radius: 8px;
            font-size: 15px;
            transition: all 0.3s ease;
            background: #2D2D2D;
            color: #F3F4F6;
        }

        .form-input:focus {
            outline: none;
            border-color: #FFC107;
            background: #222;
            box-shadow: 0 0 0 2px rgba(255, 193, 7, 0.2);
        }

        .form-input::placeholder {
            color: #6B7280;
        }

        .login-btn {
            width: 100%;
            padding: 16px;
            background: #FFC107;
            color: #121212;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 20px;
        }

        .login-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 30px rgba(255, 193, 7, 0.3);
            background: #F5B301;
        }

        .login-btn:active {
            transform: translateY(-1px);
        }

        .login-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }

        .error-message {
            background: rgba(245, 101, 101, 0.1);
            border-left: 4px solid #f56565;
            color: #fc8181;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
            animation: shake 0.3s ease-out;
        }

        .error-message.show {
            display: block;
        }

        @keyframes shake {

            0%,
            100% {
                transform: translateX(0);
            }

            25% {
                transform: translateX(-10px);
            }

            75% {
                transform: translateX(10px);
            }
        }

        .signup-link {
            text-align: center;
            color: #9CA3AF;
            font-size: 14px;
        }

        .signup-link a {
            color: #FFC107;
            text-decoration: none;
            font-weight: 700;
            transition: color 0.3s ease;
        }

        .signup-link a:hover {
            color: #F5B301;
            text-decoration: underline;
        }

        .demo-credentials {
            background: #2D2D2D;
            border-left: 4px solid #FFC107;
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
            font-size: 12px;
            color: #D1D5DB;
        }

        .demo-title {
            font-weight: 700;
            margin-bottom: 8px;
            color: #F3F4F6;
        }

        .demo-item {
            padding: 5px 0;
            border-bottom: 1px solid #444;
        }

        .demo-item:last-child {
            border-bottom: none;
        }

        .demo-value {
            color: #FFC107;
            font-weight: 700;
            cursor: pointer;
        }

        .demo-value:hover {
            background: #333;
            padding: 2px 4px;
            border-radius: 3px;
        }

        .loading-spinner {
            display: none;
            width: 16px;
            height: 16px;
            border: 2px solid rgba(18, 18, 18, 0.3);
            border-radius: 50%;
            border-top-color: #121212;
            animation: spin 0.8s linear infinite;
            margin-right: 8px;
        }

        @keyframes spin {
            to {
                transform: rotate(360deg);
            }
        }

        .btn-content {
            display: flex;
            align-items: center;
            justify-content: center;
        }

        @media (max-width: 480px) {
            .login-box {
                padding: 35px 25px;
            }

            .logo-title {
                font-size: 24px;
            }

            .logo {
                font-size: 40px;
            }
        }
    </style>
</head>

<body>
    <div class="login-container">
        <div class="login-box">
            <div class="logo-section">
                <div class="logo"><i class="fa-solid fa-helmet-safety"></i></div>
                <div class="logo-title">Intelligent Surveillance System</div>

            </div>

            <div class="error-message" id="errorMessage"></div>

            <form id="loginForm" onsubmit="handleLogin(event)">
                <div class="form-group">
                    <label class="form-label" for="username">Username</label>
                    <input type="text" id="username" name="username" class="form-input"
                        placeholder="Enter your username" required autocomplete="username">
                </div>

                <div class="form-group">
                    <label class="form-label" for="password">Password</label>
                    <input type="password" id="password" name="password" class="form-input"
                        placeholder="Enter your password" required autocomplete="current-password">
                </div>

                <button type="submit" class="login-btn" id="loginBtn">
                    <div class="btn-content">
                        <div class="loading-spinner" id="spinner"></div>
                        <span id="btnText">Sign In</span>
                    </div>
                </button>
            </form>

            <div class="signup-link" style="margin-top: 25px;">
                Don't have an account? <a href="signup.html">Create one now</a>
            </div>
        </div>
    </div>

    <script>
        const API_BASE = 'http://localhost:4000/api';

        function setCredentials(username, password) {
            document.getElementById('username').value = username;
            document.getElementById('password').value = password;
            document.getElementById('username').focus();
        }

        async function handleLogin(event) {
            event.preventDefault();

            const username = document.getElementById('username').value.trim();
            const password = document.getElementById('password').value.trim();
            const errorMessage = document.getElementById('errorMessage');
            const loginBtn = document.getElementById('loginBtn');
            const spinner = document.getElementById('spinner');
            const btnText = document.getElementById('btnText');

            errorMessage.classList.remove('show');

            if (!username || !password) {
                showError('Please enter username and password');
                return;
            }

            loginBtn.disabled = true;
            spinner.style.display = 'inline-block';
            btnText.textContent = 'Signing in...';

            try {
                const response = await fetch(`${API_BASE}/auth/login`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ username, password })
                });

                const data = await response.json();

                if (response.ok && data.success) {
                    localStorage.setItem('token', data.token);
                    localStorage.setItem('user', JSON.stringify(data.user));

                    showSuccess(`Welcome, ${data.user.full_name}!`);

                    setTimeout(() => {
                        window.location.href = 'dashboard.html';
                    }, 800);
                } else {
                    showError(data.error || 'Invalid username or password');
                }
            } catch (error) {
                console.error('Login error:', error);
                showError('Connection error. Please try again.');
            } finally {
                loginBtn.disabled = false;
                spinner.style.display = 'none';
                btnText.textContent = 'Sign In';
            }
        }

        function showError(message) {
            const errorMessage = document.getElementById('errorMessage');
            errorMessage.textContent = '❌ ' + message;
            errorMessage.classList.add('show');
            setTimeout(() => {
                errorMessage.classList.remove('show');
            }, 5000);
        }

        function showSuccess(message) {
            const errorMessage = document.getElementById('errorMessage');
            errorMessage.textContent = '✅ ' + message;
            errorMessage.style.borderLeftColor = '#48bb78';
            errorMessage.style.backgroundColor = '#c6f6d5';
            errorMessage.style.color = '#22543d';
            errorMessage.classList.add('show');
        }

        window.addEventListener('load', () => {
            const token = localStorage.getItem('token');
            if (token) {
                window.location.href = 'dashboard.html';
            }
        });

        document.getElementById('loginForm').addEventListener('keypress', (event) => {
            if (event.key === 'Enter') {
                handleLogin(event);
            }
        });
    </script>
</body>

</html>
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Intelligent Surveillance System</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #121212;
            color: #F3F4F6;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .login-container {
            width: 100%;
            max-width: 400px;
        }

        .login-box {
            background: #1E1E1E;
            border: 1px solid #333;
            border-radius: 12px;
            padding: 50px 40px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            animation: slideIn 0.5s ease-out;
        }

        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(30px);
            }

            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .logo-section {
            text-align: center;
            margin-bottom: 40px;
        }

        .logo {
            font-size: 48px;
            margin-bottom: 15px;
        }

        .logo-title {
            color: #FFC107;
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 8px;
        }

        .logo-subtitle {
            color: #9CA3AF;
            font-size: 14px;
            font-weight: 500;
        }

        .form-group {
            margin-bottom: 25px;
        }

        .form-label {
            display: block;
            color: #D1D5DB;
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .form-input {
            width: 100%;
            padding: 15px 18px;
            border: 1px solid #444;
            border-radius: 8px;
            font-size: 15px;
            transition: all 0.3s ease;
            background: #2D2D2D;
            color: #F3F4F6;
        }

        .form-input:focus {
            outline: none;
            border-color: #FFC107;
            background: #222;
            box-shadow: 0 0 0 2px rgba(255, 193, 7, 0.2);
        }

        .form-input::placeholder {
            color: #6B7280;
        }

        .login-btn {
            width: 100%;
            padding: 16px;
            background: #FFC107;
            color: #121212;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 20px;
        }

        .login-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 30px rgba(255, 193, 7, 0.3);
            background: #F5B301;
        }

        .login-btn:active {
            transform: translateY(-1px);
        }

        .login-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }

        .error-message {
            background: rgba(245, 101, 101, 0.1);
            border-left: 4px solid #f56565;
            color: #fc8181;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
            animation: shake 0.3s ease-out;
        }

        .error-message.show {
            display: block;
        }

        @keyframes shake {

            0%,
            100% {
                transform: translateX(0);
            }

            25% {
                transform: translateX(-10px);
            }

            75% {
                transform: translateX(10px);
            }
        }

        .signup-link {
            text-align: center;
            color: #9CA3AF;
            font-size: 14px;
        }

        .signup-link a {
            color: #FFC107;
            text-decoration: none;
            font-weight: 700;
            transition: color 0.3s ease;
        }

        .signup-link a:hover {
            color: #F5B301;
            text-decoration: underline;
        }

        .demo-credentials {
            background: #2D2D2D;
            border-left: 4px solid #FFC107;
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
            font-size: 12px;
            color: #D1D5DB;
        }

        .demo-title {
            font-weight: 700;
            margin-bottom: 8px;
            color: #F3F4F6;
        }

        .demo-item {
            padding: 5px 0;
            border-bottom: 1px solid #444;
        }

        .demo-item:last-child {
            border-bottom: none;
        }

        .demo-value {
            color: #FFC107;
            font-weight: 700;
            cursor: pointer;
        }

        .demo-value:hover {
            background: #333;
            padding: 2px 4px;
            border-radius: 3px;
        }

        .loading-spinner {
            display: none;
            width: 16px;
            height: 16px;
            border: 2px solid rgba(18, 18, 18, 0.3);
            border-radius: 50%;
            border-top-color: #121212;
            animation: spin 0.8s linear infinite;
            margin-right: 8px;
        }

        @keyframes spin {
            to {
                transform: rotate(360deg);
            }
        }

        .btn-content {
            display: flex;
            align-items: center;
            justify-content: center;
        }

        @media (max-width: 480px) {
            .login-box {
                padding: 35px 25px;
            }

            .logo-title {
                font-size: 24px;
            }

            .logo {
                font-size: 40px;
            }
        }
    </style>
</head>

<body>
    <div class="login-container">
        <div class="login-box">
            <div class="logo-section">
                <div class="logo"><i class="fa-solid fa-helmet-safety"></i></div>
                <div class="logo-title">Intelligent Surveillance System</div>

            </div>

            <div class="error-message" id="errorMessage"></div>

            <form id="loginForm" onsubmit="handleLogin(event)">
                <div class="form-group">
                    <label class="form-label" for="username">Username</label>
                    <input type="text" id="username" name="username" class="form-input"
                        placeholder="Enter your username" required autocomplete="username">
                </div>

                <div class="form-group">
                    <label class="form-label" for="password">Password</label>
                    <input type="password" id="password" name="password" class="form-input"
                        placeholder="Enter your password" required autocomplete="current-password">
                </div>

                <button type="submit" class="login-btn" id="loginBtn">
                    <div class="btn-content">
                        <div class="loading-spinner" id="spinner"></div>
                        <span id="btnText">Sign In</span>
                    </div>
                </button>
            </form>

            <div class="signup-link" style="margin-top: 25px;">
                Don't have an account? <a href="signup.html">Create one now</a>
            </div>
        </div>
    </div>

    <script>
        const API_BASE = 'http://localhost:4000/api';

        function setCredentials(username, password) {
            document.getElementById('username').value = username;
            document.getElementById('password').value = password;
            document.getElementById('username').focus();
        }

        async function handleLogin(event) {
            event.preventDefault();

            const username = document.getElementById('username').value.trim();
            const password = document.getElementById('password').value.trim();
            const errorMessage = document.getElementById('errorMessage');
            const loginBtn = document.getElementById('loginBtn');
            const spinner = document.getElementById('spinner');
            const btnText = document.getElementById('btnText');

            errorMessage.classList.remove('show');

            if (!username || !password) {
                showError('Please enter username and password');
                return;
            }

            loginBtn.disabled = true;
            spinner.style.display = 'inline-block';
            btnText.textContent = 'Signing in...';

            try {
                const response = await fetch(`${API_BASE}/auth/login`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ username, password })
                });

                const data = await response.json();

                if (response.ok && data.success) {
                    localStorage.setItem('token', data.token);
                    localStorage.setItem('user', JSON.stringify(data.user));

                    showSuccess(`Welcome, ${data.user.full_name}!`);

                    setTimeout(() => {
                        window.location.href = 'dashboard.html';
                    }, 800);
                } else {
                    showError(data.error || 'Invalid username or password');
                }
            } catch (error) {
                console.error('Login error:', error);
                showError('Connection error. Please try again.');
            } finally {
                loginBtn.disabled = false;
                spinner.style.display = 'none';
                btnText.textContent = 'Sign In';
            }
        }

        function showError(message) {
            const errorMessage = document.getElementById('errorMessage');
            errorMessage.textContent = '❌ ' + message;
            errorMessage.classList.add('show');
            setTimeout(() => {
                errorMessage.classList.remove('show');
            }, 5000);
        }

        function showSuccess(message) {
            const errorMessage = document.getElementById('errorMessage');
            errorMessage.textContent = '✅ ' + message;
            errorMessage.style.borderLeftColor = '#48bb78';
            errorMessage.style.backgroundColor = '#c6f6d5';
            errorMessage.style.color = '#22543d';
            errorMessage.classList.add('show');
        }

        window.addEventListener('load', () => {
            const token = localStorage.getItem('token');
            if (token) {
                window.location.href = 'dashboard.html';
            }
        });

        document.getElementById('loginForm').addEventListener('keypress', (event) => {
            if (event.key === 'Enter') {
                handleLogin(event);
            }
        });
    </script>
</body>

</html>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Salary & Fines Management</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #121212;
            color: #F3F4F6;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1600px; margin: 0 auto; }
        .header {
            background: #1E1E1E;
            padding: 25px 30px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
        }
        .header h1 { color: #FFC107; font-size: 28px; font-weight: 700; margin-bottom: 15px; }
        .header-controls {
            display: flex;
            gap: 15px;
            align-items: center;
            flex-wrap: wrap;
        }
        .nav-menu {
            background: #1E1E1E;
            padding: 15px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .nav-btn {
            padding: 12px 24px;
            background: transparent;
            color: #D1D5DB;
            border: 1px solid #333;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
        }
        .nav-btn:hover { transform: translateY(-2px); background: #333; }
        .nav-btn.active { background: #FFC107; color: #121212; border-color: #FFC107; font-weight: 700; }
        
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 2px solid #333;
        }
        .tab-btn {
            padding: 12px 20px;
            background: transparent;
            border: none;
            color: #9CA3AF;
            cursor: pointer;
            font-weight: 600;
            border-bottom: 3px solid transparent;
            transition: all 0.3s ease;
        }
        .tab-btn.active {
            color: #FFC107;
            border-bottom-color: #FFC107;
        }
        
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .summary-card {
            background: #1E1E1E;
            padding: 20px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            position: relative;
            overflow: hidden;
        }
        .summary-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 3px;
        }
        .summary-card.gross::before { background: #4fd1c5; }
        .summary-card.fines::before { background: #fc8181; }
        .summary-card.net::before { background: #68d391; }
        .summary-label { color: #9CA3AF; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 5px; }
        .summary-value { color: #F3F4F6; font-size: 24px; font-weight: 700; }
        
        .card {
            background: #1E1E1E;
            padding: 25px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 15px;
        }
        .card-title { color: #FFC107; font-size: 20px; font-weight: 700; }
        
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .btn-primary { background: #FFC107; color: #121212; }
        .btn-primary:hover { transform: translateY(-2px); background: #F5B301; }
        .btn-secondary { background: #2D2D2D; color: #D1D5DB; border: 1px solid #444; }
        .btn-secondary:hover { background: #333; }
        .btn-small { padding: 8px 16px; font-size: 12px; }
        
        .filter-group {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            align-items: center;
        }
        .input-field {
            padding: 10px 15px;
            border: 1px solid #444;
            border-radius: 8px;
            font-size: 14px;
            background: #2D2D2D;
            color: #F3F4F6;
        }
        .input-field:focus {
            outline: none;
            border-color: #FFC107;
            box-shadow: 0 0 0 2px rgba(255, 193, 7, 0.2);
        }
        
        .table-wrapper { overflow-x: auto; }
        .data-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        .data-table thead {
            background: #FFC107;
            color: #121212;
        }
        .data-table th {
            padding: 12px;
            text-align: left;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }
        .data-table td {
            padding: 12px;
            border-bottom: 1px solid #333;
            color: #D1D5DB;
        }
        .data-table tbody tr:hover { background: #2D2D2D; }
        
        .amount-positive { color: #68d391; font-weight: 700; }
        .amount-negative { color: #fc8181; font-weight: 700; }
        .badge {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            display: inline-block;
        }
        .badge-paid { background: rgba(72, 187, 120, 0.2); color: #68d391; border: 1px solid #68d391; }
        .badge-pending { background: rgba(237, 137, 54, 0.2); color: #f6ad55; border: 1px solid #f6ad55; }
        .badge-processing { background: rgba(66, 153, 225, 0.2); color: #63b3ed; border: 1px solid #63b3ed; }
        .badge-violation { background: rgba(245, 101, 101, 0.2); color: #fc8181; border: 1px solid #fc8181; }
        .badge-absence { background: rgba(221, 107, 32, 0.2); color: #ed8936; border: 1px solid #ed8936; }
        
        .action-buttons {
            display: flex;
            gap: 5px;
        }
        .action-btn {
            padding: 4px 8px;
            border: none;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            background: #2D2D2D;
            color: #D1D5DB;
            border: 1px solid #444;
            transition: all 0.3s ease;
        }
        .action-btn:hover { background: #333; color: #FFC107; border-color: #FFC107; }
        
        .hidden { display: none; }
        .loading { text-align: center; padding: 30px; color: #9CA3AF; }
        
        @media (max-width: 768px) {
            .header-controls { flex-direction: column; }
            .filter-group { flex-direction: column; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fa-solid fa-money-bill"></i> Salary & Fines Management</h1>
            <div class="header-controls">
                <label style="color: #4a5568; font-weight: 600;">Select Month:</label>
                <input type="month" id="payPeriod" class="input-field">
                <button class="btn btn-primary" onclick="loadData()"><i class="fa-solid fa-chart-bar"></i> Load</button>
                <button class="btn btn-secondary" onclick="generatePayroll()"><i class="fa-solid fa-rotate"></i> Generate Payroll</button>
            </div>
        </div>

        <nav class="nav-menu">
            <a href="dashboard.html" class="nav-btn">Dashboard</a>
            <a href="cctv.html" class="nav-btn"><i class="fa-solid fa-video"></i> CCTV</a>
            <a href="violations.html" class="nav-btn"><i class="fa-solid fa-triangle-exclamation"></i> Violations</a>
            <a href="attendance.html" class="nav-btn"><i class="fa-solid fa-clipboard-check"></i> Attendance</a>
            <a href="salary.html" class="nav-btn active"><i class="fa-solid fa-money-bill"></i> Salary</a>
            <a href="workers.html" class="nav-btn"><i class="fa-solid fa-hard-hat"></i> Workers</a>
            <a href="health.html" class="nav-btn"><i class="fa-solid fa-truck-medical"></i> Health</a>
        </nav>

        <!-- Tabs -->
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('salary')"><i class="fa-solid fa-money-bill-wave"></i> Salary Breakdown</button>
            <button class="tab-btn" onclick="switchTab('fines')"><i class="fa-solid fa-triangle-exclamation"></i> Fines Details</button>
            <button class="tab-btn" onclick="switchTab('summary')"><i class="fa-solid fa-chart-bar"></i> Summary</button>
        </div>

        <!-- Summary Cards -->
        <div class="summary-grid" id="summaryCards"></div>

        <!-- SALARY TAB -->
        <div id="salary-tab" class="card">
            <div class="card-header">
                <h2 class="card-title">Salary Records</h2>
                <div class="filter-group">
                    <select id="statusFilter" class="input-field" onchange="loadData()">
                        <option value="">All Status</option>
                        <option value="pending">Pending</option>
                        <option value="processing">Processing</option>
                        <option value="paid">Paid</option>
                    </select>
                    <button class="btn btn-secondary btn-small" onclick="markAllPaid()">✓ Mark All Paid</button>
                    <button class="btn btn-secondary btn-small" onclick="exportCSV()"><i class="fa-solid fa-download"></i> Export</button>
                </div>
            </div>
            <div class="table-wrapper">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Worker</th>
                            <th>Days/Hrs</th>
                            <th>Gross</th>
                            <th>Violations</th>
                            <th>Absence</th>
                            <th>Late</th>
                            <th>Total Fines</th>
                            <th>Tax</th>
                            <th>Net</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="salaryTableBody" class="loading">Loading...</tbody>
                </table>
            </div>
        </div>

        <!-- FINES TAB -->
        <div id="fines-tab" class="card hidden">
            <div class="card-header">
                <h2 class="card-title">Fines Breakdown</h2>
                <div class="filter-group">
                    <select id="fineTypeFilter" class="input-field" onchange="loadFines()">
                        <option value="">All Types</option>
                        <option value="violation">Violation</option>
                        <option value="absence">Absence</option>
                        <option value="late">Late Arrival</option>
                    </select>
                    <select id="fineStatusFilter" class="input-field" onchange="loadFines()">
                        <option value="">All Status</option>
                        <option value="pending">Pending</option>
                        <option value="deducted">Deducted</option>
                        <option value="waived">Waived</option>
                    </select>
                </div>
            </div>
            <div class="table-wrapper">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Worker</th>
                            <th>Fine Type</th>
                            <th>Amount (PKR)</th>
                            <th>Description</th>
                            <th>Date</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="finesTableBody" class="loading">Loading...</tbody>
                </table>
            </div>
        </div>

        <!-- SUMMARY TAB -->
        <div id="summary-tab" class="card hidden">
            <h2 class="card-title" style="margin-bottom: 20px;">Monthly Summary</h2>
            <div class="table-wrapper">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Month</th>
                            <th>Workers</th>
                            <th>Total Gross</th>
                            <th>Total Fines</th>
                            <th>Total Net</th>
                            <th>Paid</th>
                            <th>Pending</th>
                        </tr>
                    </thead>
                    <tbody id="summaryTableBody" class="loading">Loading...</tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        const API_BASE = 'http://localhost:4000/api';
        
        // Auth check
        window.addEventListener('load', () => {
            const token = localStorage.getItem('token');
            if (!token) window.location.href = 'login.html';
            
            const today = new Date();
            document.getElementById('payPeriod').value = today.toISOString().slice(0, 7);
            loadData();
        });

        function switchTab(tab) {
            document.querySelectorAll('[id$="-tab"]').forEach(el => el.classList.add('hidden'));
            document.getElementById(tab + '-tab').classList.remove('hidden');
            
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            if (tab === 'fines') loadFines();
            else if (tab === 'summary') loadSummary();
        }

        async function loadData() {
            try {
                const period = document.getElementById('payPeriod').value;
                const status = document.getElementById('statusFilter').value;
                
                let url = `${API_BASE}/salary?pay_period=${period}`;
                if (status) url += `&status=${status}`;
                
                const response = await fetch(url);
                const salaries = await response.json();
                
                displaySalaries(salaries);
                updateSummary(salaries);
            } catch (error) {
                console.error('Error loading data:', error);
                document.getElementById('salaryTableBody').innerHTML = '<tr><td colspan="11" class="loading">Error loading data</td></tr>';
            }
        }

        function displaySalaries(salaries) {
            const tbody = document.getElementById('salaryTableBody');
            
            if (!salaries || salaries.length === 0) {
                tbody.innerHTML = '<tr><td colspan="11" class="loading">No records found</td></tr>';
                return;
            }
            
            tbody.innerHTML = salaries.map(s => `
                <tr>
                    <td><strong>${s.worker_id}</strong><br><small>${s.name}</small></td>
                    <td>${s.wage_type === 'daily' ? s.days_worked + ' d' : s.hours_worked + ' h'}</td>
                    <td class="amount-positive">PKR ${s.gross_salary.toLocaleString()}</td>
                    <td class="amount-negative">-${(s.violation_fines || 0).toLocaleString()}</td>
                    <td class="amount-negative">-${(s.absence_fines || 0).toLocaleString()}</td>
                    <td class="amount-negative">-${(s.late_fines || 0).toLocaleString()}</td>
                    <td class="amount-negative"><strong>-${(s.total_fines || 0).toLocaleString()}</strong></td>
                    <td>-${(s.tax_deduction || 0).toLocaleString()}</td>
                    <td class="amount-positive"><strong>PKR ${s.net_salary.toLocaleString()}</strong></td>
                    <td><span class="badge badge-${s.status}">${s.status.toUpperCase()}</span></td>
                    <td>
                        <div class="action-buttons">
                            <button class="action-btn" onclick="viewDetails('${s.worker_id}', '${s.name}', ${s.gross_salary}, ${s.total_fines}, ${s.net_salary})">👁️</button>
                            ${s.status !== 'paid' ? `<button class="action-btn" onclick="markPaid(${s.salary_id})">✓</button>` : ''}
                        </div>
                    </td>
                </tr>
            `).join('');
        }

        async function loadFines() {
            try {
                const type = document.getElementById('fineTypeFilter').value;
                const status = document.getElementById('fineStatusFilter').value;
                
                // Mock data - Replace with actual API when backend ready
                const fines = [
                    { fine_id: 1, worker_id: 'W001', name: 'Ahmad Ali', fine_type: 'violation', fine_amount: 200, description: 'Missing gloves', fine_date: new Date().toISOString().split('T')[0], status: 'pending' },
                    { fine_id: 2, worker_id: 'W002', name: 'Hassan Khan', fine_type: 'violation', fine_amount: 300, description: 'Missing vest', fine_date: new Date().toISOString().split('T')[0], status: 'pending' },
                    { fine_id: 3, worker_id: 'W003', name: 'Bilal Ahmed', fine_type: 'violation', fine_amount: 500, description: 'Missing helmet', fine_date: new Date().toISOString().split('T')[0], status: 'pending' },
                    { fine_id: 4, worker_id: 'W003', name: 'Bilal Ahmed', fine_type: 'late', fine_amount: 100, description: 'Late arrival - 30 min', fine_date: new Date().toISOString().split('T')[0], status: 'pending' },
                    { fine_id: 5, worker_id: 'W004', name: 'Usman Tariq', fine_type: 'absence', fine_amount: 500, description: 'Absent on duty', fine_date: new Date(Date.now() - 86400000).toISOString().split('T')[0], status: 'deducted' }
                ];
                
                const tbody = document.getElementById('finesTableBody');
                tbody.innerHTML = fines.map(f => `
                    <tr>
                        <td><strong>${f.worker_id}</strong><br><small>${f.name}</small></td>
                        <td><span class="badge badge-${f.fine_type}">${f.fine_type.toUpperCase()}</span></td>
                        <td class="amount-negative">PKR ${f.fine_amount.toLocaleString()}</td>
                        <td>${f.description}</td>
                        <td>${f.fine_date}</td>
                        <td><span class="badge badge-${f.status}">${f.status.toUpperCase()}</span></td>
                        <td>
                            <div class="action-buttons">
                                ${f.status !== 'deducted' ? `<button class="action-btn" onclick="deductFine(${f.fine_id})">Deduct</button>` : ''}
                                <button class="action-btn" onclick="waiveFine(${f.fine_id})">Waive</button>
                            </div>
                        </td>
                    </tr>
                `).join('');
            } catch (error) {
                console.error('Error loading fines:', error);
            }
        }

        async function loadSummary() {
            try {
                // Mock data - Replace with API
                const summary = [
                    { month: '2024-12', workers: 4, gross: 39500, fines: 1600, net: 37900, paid: 1, pending: 3 },
                    { month: '2024-11', workers: 4, gross: 41800, fines: 300, net: 41500, paid: 4, pending: 0 }
                ];
                
                const tbody = document.getElementById('summaryTableBody');
                tbody.innerHTML = summary.map(s => `
                    <tr>
                        <td><strong>${s.month}</strong></td>
                        <td>${s.workers}</td>
                        <td>PKR ${s.gross.toLocaleString()}</td>
                        <td class="amount-negative">-PKR ${s.fines.toLocaleString()}</td>
                        <td class="amount-positive"><strong>PKR ${s.net.toLocaleString()}</strong></td>
                        <td><span class="badge badge-paid">${s.paid}</span></td>
                        <td><span class="badge badge-pending">${s.pending}</span></td>
                    </tr>
                `).join('');
            } catch (error) {
                console.error('Error loading summary:', error);
            }
        }

        function updateSummary(salaries) {
            if (!salaries || salaries.length === 0) return;
            
            const totalGross = salaries.reduce((sum, s) => sum + (s.gross_salary || 0), 0);
            const totalFines = salaries.reduce((sum, s) => sum + (s.total_fines || 0), 0);
            const totalNet = salaries.reduce((sum, s) => sum + (s.net_salary || 0), 0);
            
            const html = `
                <div class="summary-card gross">
                    <div class="summary-label">Total Gross Salary</div>
                    <div class="summary-value">PKR ${totalGross.toLocaleString()}</div>
                </div>
                <div class="summary-card fines">
                    <div class="summary-label">Total Fines</div>
                    <div class="summary-value">PKR ${totalFines.toLocaleString()}</div>
                </div>
                <div class="summary-card net">
                    <div class="summary-label">Net Payable</div>
                    <div class="summary-value">PKR ${totalNet.toLocaleString()}</div>
                </div>
                <div class="summary-card gross">
                    <div class="summary-label">Average per Worker</div>
                    <div class="summary-value">PKR ${(totalNet / salaries.length).toLocaleString()}</div>
                </div>
            `;
            document.getElementById('summaryCards').innerHTML = html;
        }

        function viewDetails(id, name, gross, fines, net) {
            alert(`${id} - ${name}\n\nGross: PKR ${gross.toLocaleString()}\nFines: PKR ${fines.toLocaleString()}\nNet: PKR ${net.toLocaleString()}`);
        }

        async function markPaid(salaryId) {
            if (!confirm('Mark as paid?')) return;
            try {
                const response = await fetch(`${API_BASE}/salary/${salaryId}/status`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: 'paid' })
                });
                if (response.ok) loadData();
            } catch (error) {
                console.error('Error:', error);
            }
        }

        function markAllPaid() {
            if (confirm('Mark all as paid?')) {
                alert('Mark all as paid - Backend implementation needed');
                loadData();
            }
        }

        function deductFine(fineId) {
            if (confirm('Deduct this fine?')) {
                alert('Fine deducted - Backend implementation needed');
                loadFines();
            }
        }

        function waiveFine(fineId) {
            if (confirm('Waive this fine?')) {
                alert('Fine waived - Backend implementation needed');
                loadFines();
            }
        }

        function generatePayroll() {
            alert('Generate payroll for: ' + document.getElementById('payPeriod').value);
        }

        function exportCSV() {
            alert('Exporting salary data...');
        }
    </script>
    <script src="auth.js"></script>
</body>
</html>
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign Up - Construction Safety</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #121212;
            color: #F3F4F6;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .signup-container {
            width: 100%;
            max-width: 450px;
        }

        .signup-box {
            background: #1E1E1E;
            border: 1px solid #333;
            border-radius: 12px;
            padding: 50px 40px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            animation: slideIn 0.5s ease-out;
        }

        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(30px);
            }

            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .logo-section {
            text-align: center;
            margin-bottom: 40px;
        }

        .logo {
            font-size: 48px;
            margin-bottom: 15px;
        }

        .logo-title {
            color: #FFC107;
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 8px;
        }

        .logo-subtitle {
            color: #9CA3AF;
            font-size: 14px;
            font-weight: 500;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-label {
            display: block;
            color: #D1D5DB;
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .form-input {
            width: 100%;
            padding: 12px 15px;
            border: 1px solid #444;
            border-radius: 8px;
            font-size: 15px;
            transition: all 0.3s ease;
            background: #2D2D2D;
            color: #F3F4F6;
        }

        .form-input:focus {
            outline: none;
            border-color: #FFC107;
            background: #222;
            box-shadow: 0 0 0 2px rgba(255, 193, 7, 0.2);
        }

        .form-input::placeholder {
            color: #6B7280;
        }

        .signup-btn {
            width: 100%;
            padding: 16px;
            background: #FFC107;
            color: #121212;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin: 30px 0 20px 0;
        }

        .signup-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 30px rgba(255, 193, 7, 0.3);
            background: #F5B301;
        }

        .signup-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }

        .error-message {
            background: rgba(245, 101, 101, 0.1);
            border-left: 4px solid #f56565;
            color: #fc8181;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
            animation: shake 0.3s ease-out;
        }

        .error-message.show {
            display: block;
        }

        .success-message {
            background: rgba(72, 187, 120, 0.1);
            border-left: 4px solid #48bb78;
            color: #68d391;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
        }

        .success-message.show {
            display: block;
        }

        @keyframes shake {

            0%,
            100% {
                transform: translateX(0);
            }

            25% {
                transform: translateX(-10px);
            }

            75% {
                transform: translateX(10px);
            }
        }

        .login-link {
            text-align: center;
            color: #9CA3AF;
            font-size: 14px;
        }

        .login-link a {
            color: #FFC107;
            text-decoration: none;
            font-weight: 700;
            transition: color 0.3s ease;
        }

        .login-link a:hover {
            color: #F5B301;
            text-decoration: underline;
        }

        .requirements {
            background: #2D2D2D;
            border-left: 4px solid #FFC107;
            padding: 12px;
            border-radius: 8px;
            margin-top: 15px;
            font-size: 12px;
            color: #D1D5DB;
        }

        .requirements-title {
            font-weight: 700;
            margin-bottom: 8px;
            color: #F3F4F6;
        }

        .requirement-item {
            padding: 3px 0;
        }

        .requirement-item.met {
            color: #48bb78;
        }

        .loading-spinner {
            display: none;
            width: 16px;
            height: 16px;
            border: 2px solid rgba(18, 18, 18, 0.3);
            border-radius: 50%;
            border-top-color: #121212;
            animation: spin 0.8s linear infinite;
            margin-right: 8px;
        }

        @keyframes spin {
            to {
                transform: rotate(360deg);
            }
        }

        .btn-content {
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }

        @media (max-width: 480px) {
            .signup-box {
                padding: 35px 25px;
            }

            .logo-title {
                font-size: 24px;
            }

            .logo {
                font-size: 40px;
            }

            .form-row {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>

<body>
    <div class="signup-container">
        <div class="signup-box">
            <div class="logo-section">
                <div class="logo"><i class="fa-solid fa-helmet-safety"></i></div>
                <div class="logo-title">Create Account</div>
                <div class="logo-subtitle">Join Construction Safety System</div>
            </div>

            <div class="error-message" id="errorMessage"></div>
            <div class="success-message" id="successMessage"></div>

            <form id="signupForm" onsubmit="handleSignup(event)">
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label" for="fullname">Full Name</label>
                        <input type="text" id="fullname" name="full_name" class="form-input" placeholder="Your name"
                            required>
                    </div>

                    <div class="form-group">
                        <label class="form-label" for="username">Username</label>
                        <input type="text" id="username" name="username" class="form-input"
                            placeholder="Choose username" required minlength="3">
                    </div>
                </div>

                <div class="form-group">
                    <label class="form-label" for="password">Password</label>
                    <input type="password" id="password" name="password" class="form-input"
                        placeholder="At least 6 characters" required minlength="6"
                        oninput="checkPasswordRequirements()">
                </div>

                <div class="form-group">
                    <label class="form-label" for="confirmPassword">Confirm Password</label>
                    <input type="password" id="confirmPassword" name="confirm_password" class="form-input"
                        placeholder="Confirm password" required>
                </div>

                <div class="form-group">
                    <label class="form-label" for="department">Department</label>
                    <select id="department" name="department" class="form-input" required>
                        <option value="">Select Department</option>
                        <option value="Construction">Construction</option>
                        <option value="Electrical">Electrical</option>
                        <option value="Plumbing">Plumbing</option>
                        <option value="Carpentry">Carpentry</option>
                    </select>
                </div>

                <div class="form-group">
                    <label class="form-label" for="role">User Role</label>
                    <select id="role" name="role" class="form-input" required>
                        <option value="">Select Role</option>
                        <option value="admin">Admin</option>
                        <option value="safety officer">Safety Officer</option>
                        <option value="hr">HR</option>
                        <option value="monitor">Monitor</option>
                        <option value="accounts">Accounts</option>
                        <option value="supervisor">Supervisor</option>
                        <option value="worker">Worker</option>
                    </select>
                </div>

                <div class="form-group">
                    <label class="form-label" for="adminUsername">Admin Username</label>
                    <input type="text" id="adminUsername" class="form-input" placeholder="Administrator username" required>
                </div>

                <div class="form-group">
                    <label class="form-label" for="adminPassword">Admin Password</label>
                    <input type="password" id="adminPassword" class="form-input" placeholder="Administrator password" required>
                </div>

                <div class="form-group">
                    <label class="form-label" for="phone">Phone Number</label>
                    <input type="tel" id="phone" name="phone" class="form-input" placeholder="+92 300 1234567">
                </div>

                <button type="submit" class="signup-btn" id="signupBtn">
                    <div class="btn-content">
                        <div class="loading-spinner" id="spinner"></div>
                        <span id="btnText">Create Account</span>
                    </div>
                </button>
            </form>

            <div class="requirements">
                <div class="requirements-title">📋 Password Requirements:</div>
                <div class="requirement-item" id="req-length">✗ At least 6 characters</div>
                <div class="requirement-item" id="req-match">✗ Passwords match</div>
                <div class="requirement-item">Admin login is required to create any new account.</div>
            </div>

            <div class="login-link" style="margin-top: 25px;">
                Already have an account? <a href="login.html">Sign in here</a>
            </div>
        </div>
    </div>

    <script>
        const API_BASE = 'http://localhost:4000/api';

        function checkPasswordRequirements() {
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirmPassword').value;

            const reqLength = document.getElementById('req-length');
            const reqMatch = document.getElementById('req-match');

            if (password.length >= 6) {
                reqLength.classList.add('met');
                reqLength.textContent = '✓ At least 6 characters';
            } else {
                reqLength.classList.remove('met');
                reqLength.textContent = '✗ At least 6 characters';
            }

            if (password && confirmPassword && password === confirmPassword) {
                reqMatch.classList.add('met');
                reqMatch.textContent = '✓ Passwords match';
            } else if (password || confirmPassword) {
                reqMatch.classList.remove('met');
                reqMatch.textContent = '✗ Passwords match';
            }
        }

        document.getElementById('confirmPassword').addEventListener('input', checkPasswordRequirements);

        async function handleSignup(event) {
            event.preventDefault();

            const fullname = document.getElementById('fullname').value.trim();
            const username = document.getElementById('username').value.trim();
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirmPassword').value;
            const department = document.getElementById('department').value;
            const phone = document.getElementById('phone').value.trim();

            const errorMessage = document.getElementById('errorMessage');
            const successMessage = document.getElementById('successMessage');
            const signupBtn = document.getElementById('signupBtn');
            const spinner = document.getElementById('spinner');
            const btnText = document.getElementById('btnText');

            errorMessage.classList.remove('show');
            successMessage.classList.remove('show');

            // Validation
const role = document.getElementById('role').value;
                const adminUsername = document.getElementById('adminUsername').value.trim();
                const adminPassword = document.getElementById('adminPassword').value;

                if (!fullname || !username || !password || !department || !role || !adminUsername || !adminPassword) {
                    showError('Please fill in all required fields, including admin credentials.');
                    return;
                }

                if (username.length < 3) {
                    showError('Username must be at least 3 characters');
                    return;
                }

            if (password.length < 6) {
                showError('Password must be at least 6 characters');
                return;
            }

            if (password !== confirmPassword) {
                showError('Passwords do not match');
                return;
            }

            signupBtn.disabled = true;
            spinner.style.display = 'inline-block';
            btnText.textContent = 'Creating Account...';

            try {
                const response = await fetch(`${API_BASE}/auth/register`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        username,
                        password,
                        full_name: fullname,
                        department,
                        phone,
                        role,
                        admin_username: adminUsername,
                        admin_password: adminPassword
                    })
                });

                const data = await response.json();

                if (response.ok && data.success) {
                    showSuccess('Account created successfully! Redirecting to login...');

                    setTimeout(() => {
                        window.location.href = 'login.html';
                    }, 2000);
                } else {
                    showError(data.error || 'Failed to create account');
                }
            } catch (error) {
                console.error('Signup error:', error);
                showError('Connection error. Please try again.');
            } finally {
                signupBtn.disabled = false;
                spinner.style.display = 'none';
                btnText.textContent = 'Create Account';
            }
        }

        function showError(message) {
            const errorMessage = document.getElementById('errorMessage');
            errorMessage.textContent = '❌ ' + message;
            errorMessage.classList.add('show');
        }

        function showSuccess(message) {
            const successMessage = document.getElementById('successMessage');
            successMessage.textContent = '✅ ' + message;
            successMessage.classList.add('show');
        }

        window.addEventListener('load', () => {
            const token = localStorage.getItem('token');
            if (token) {
                window.location.href = 'dashboard.html';
            }
        });

        document.getElementById('signupForm').addEventListener('keypress', (event) => {
            if (event.key === 'Enter') {
                handleSignup(event);
            }
        });
    </script>
</body>

</html>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PPE Violations Log</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #121212;
            color: #F3F4F6;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header {
            background: #1E1E1E;
            padding: 25px 30px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
        }
        .header h1 { color: #FFC107; font-size: 28px; font-weight: 700; }
        .header-stats { display: flex; gap: 30px; margin-top: 15px; }
        .stat-chip {
            padding: 8px 16px;
            background: rgba(245, 101, 101, 0.1);
            border-left: 4px solid #f56565;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            color: #fc8181;
        }
        .nav-menu {
            background: #1E1E1E;
            padding: 15px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .nav-btn {
            padding: 12px 24px;
            background: transparent;
            color: #D1D5DB;
            border: 1px solid #333;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
        }
        .nav-btn:hover { transform: translateY(-2px); background: #333; }
        .nav-btn.active { background: #FFC107; color: #121212; border-color: #FFC107; font-weight: 700; }
        .filters-panel {
            background: #1E1E1E;
            padding: 25px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
        }
        .filters-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .filter-group { display: flex; flex-direction: column; gap: 8px; }
        .filter-label { color: #9CA3AF; font-size: 14px; font-weight: 600; }
        .filter-input, .filter-select {
            padding: 12px;
            border: 1px solid #444;
            border-radius: 8px;
            font-size: 14px;
            background: #2D2D2D;
            color: #F3F4F6;
            transition: all 0.3s ease;
        }
        .filter-input:focus, .filter-select:focus {
            outline: none;
            border-color: #FFC107;
            box-shadow: 0 0 0 2px rgba(255, 193, 7, 0.2);
        }
        .filter-actions { display: flex; gap: 10px; }
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .btn-primary {
            background: #FFC107;
            color: #121212;
        }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(255, 193, 7, 0.3); background: #F5B301; }
        .btn-secondary { background: #2D2D2D; color: #D1D5DB; border: 1px solid #444; }
        .btn-secondary:hover { background: #333; }
        .violations-table-container {
            background: #1E1E1E;
            padding: 25px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            overflow-x: auto;
        }
        .table-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .table-header h2 { color: #FFC107; font-size: 20px; font-weight: 700; }
        .violations-table { width: 100%; border-collapse: collapse; min-width: 800px; }
        .violations-table thead {
            background: #FFC107;
            color: #121212;
        }
        .violations-table th {
            padding: 15px;
            text-align: left;
            font-weight: 700;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }
        .violations-table td {
            padding: 15px;
            border-bottom: 1px solid #333;
            color: #D1D5DB;
            font-size: 14px;
        }
        .violations-table tbody tr {
            background: #1E1E1E;
            transition: all 0.3s ease;
        }
        .violations-table tbody tr:hover {
            background: #2D2D2D;
            transform: scale(1.01);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
        }
        .violation-badge {
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            display: inline-block;
        }
        .violation-helmet { background: rgba(245, 101, 101, 0.2); color: #fc8181; border: 1px solid #fc8181; }
        .violation-vest { background: rgba(237, 137, 54, 0.2); color: #f6ad55; border: 1px solid #f6ad55; }
        .violation-gloves { background: rgba(236, 201, 75, 0.2); color: #ecc94b; border: 1px solid #ecc94b; }
        .violation-boots { background: rgba(159, 122, 234, 0.2); color: #b794f4; border: 1px solid #b794f4; }
        .severity-badge {
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            display: inline-block;
        }
        .severity-high { background: rgba(245, 101, 101, 0.2); color: #fc8181; border: 1px solid #fc8181; }
        .severity-medium { background: rgba(237, 137, 54, 0.2); color: #f6ad55; border: 1px solid #f6ad55; }
        .severity-low { background: rgba(72, 187, 120, 0.2); color: #68d391; border: 1px solid #68d391; }
        .action-btns { display: flex; gap: 8px; }
        .action-btn {
            padding: 6px 12px;
            border: none;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .action-view { background: #2D2D2D; color: #D1D5DB; border: 1px solid #444; }
        .action-view:hover { background: #333; }
        .action-resolve { background: rgba(72, 187, 120, 0.2); color: #68d391; border: 1px solid #68d391; }
        .action-resolve:hover { background: rgba(72, 187, 120, 0.4); }
        .loading { text-align: center; padding: 20px; color: #9CA3AF; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fa-solid fa-triangle-exclamation"></i> PPE Violations Log</h1>
            <div class="header-stats">
                <div class="stat-chip">Today: <span id="todayCount">...</span> Violations</div>
                <div class="stat-chip">This Week: <span id="weekCount">...</span> Violations</div>
                <div class="stat-chip">Pending: <span id="pendingCount">...</span></div>
            </div>
        </div>

        <nav class="nav-menu">
            <a href="dashboard.html" class="nav-btn">Dashboard</a>
            <a href="cctv.html" class="nav-btn">CCTV Feeds</a>
            <a href="violations.html" class="nav-btn active">Violations</a>
            <a href="attendance.html" class="nav-btn">Attendance</a>
            <a href="salary.html" class="nav-btn">Salary & Fines</a>
            <a href="workers.html" class="nav-btn">Workers</a>
            <a href="health.html" class="nav-btn">Health Alerts</a>
            <a href="face-recognition.html" class="nav-btn">Face Recognition</a>
        </nav>

        <div class="filters-panel">
            <div class="filters-grid">
                <div class="filter-group">
                    <label class="filter-label">Date From</label>
                    <input type="date" class="filter-input" id="dateFrom">
                </div>
                <div class="filter-group">
                    <label class="filter-label">Date To</label>
                    <input type="date" class="filter-input" id="dateTo">
                </div>
                <div class="filter-group">
                    <label class="filter-label">Violation Type</label>
                    <select class="filter-select" id="violationType">
                        <option value="">All Types</option>
                        <option value="helmet">Missing Helmet</option>
                        <option value="vest">Missing Vest</option>
                        <option value="gloves">Missing Gloves</option>
                        <option value="boots">Missing Boots</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label class="filter-label">Severity</label>
                    <select class="filter-select" id="severity">
                        <option value="">All Severities</option>
                        <option value="high">High</option>
                        <option value="medium">Medium</option>
                        <option value="low">Low</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label class="filter-label">Worker ID</label>
                    <input type="text" class="filter-input" id="workerId" placeholder="Search Worker ID">
                </div>
            </div>
            <div class="filter-actions">
                <button class="btn btn-primary" onclick="applyFilters()"><i class="fa-solid fa-magnifying-glass"></i> Apply Filters</button>
                <button class="btn btn-secondary" onclick="resetFilters()"><i class="fa-solid fa-arrow-rotate-left"></i> Reset</button>
            </div>
        </div>

        <div class="violations-table-container">
            <div class="table-header">
                <h2>Violation Records</h2>
            </div>

            <table class="violations-table">
                <thead>
                    <tr>
                        <th>Violation ID</th>
                        <th>Date & Time</th>
                        <th>Worker ID</th>
                        <th>Worker Name</th>
                        <th>Violation Type</th>
                        <th>Severity</th>
                        <th>Camera</th>
                        <th>Fine Amount</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="violationsTableBody">
                    <tr><td colspan="9" class="loading">Loading violations data...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const API_BASE = 'http://localhost:4000/api';

        // Set default dates
        function setDefaultDates() {
            const today = new Date();
            const weekAgo = new Date(today);
            weekAgo.setDate(weekAgo.getDate() - 7);
            
            document.getElementById('dateTo').value = today.toISOString().split('T')[0];
            document.getElementById('dateFrom').value = weekAgo.toISOString().split('T')[0];
        }

        // Load statistics
        async function loadStats() {
            try {
                const response = await fetch(`${API_BASE}/violations/stats/summary`);
                const stats = await response.json();
                
                document.getElementById('todayCount').textContent = stats.today || 0;
                document.getElementById('weekCount').textContent = stats.week || 0;
                document.getElementById('pendingCount').textContent = stats.pending || 0;
            } catch (error) {
                console.error('Error loading stats:', error);
            }
        }

        // Load violations with filters
        async function loadViolations() {
            try {
                const dateFrom = document.getElementById('dateFrom').value;
                const dateTo = document.getElementById('dateTo').value;
                const violationType = document.getElementById('violationType').value;
                const severity = document.getElementById('severity').value;
                const workerId = document.getElementById('workerId').value;

                let url = `${API_BASE}/violations?`;
                if (dateFrom && dateTo) url += `date_from=${dateFrom}&date_to=${dateTo}&`;
                if (violationType) url += `violation_type=${violationType}&`;
                if (severity) url += `severity=${severity}&`;
                if (workerId) url += `worker_id=${workerId}&`;

                const response = await fetch(url);
                const violations = await response.json();
                
                const tbody = document.getElementById('violationsTableBody');
                
                if (violations.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; padding: 30px;">No violations found</td></tr>';
                    return;
                }
                
                tbody.innerHTML = violations.map(v => {
                    const timestamp = new Date(v.timestamp).toLocaleString('en-US', { 
                        month: 'short', 
                        day: 'numeric', 
                        year: 'numeric',
                        hour: '2-digit', 
                        minute: '2-digit' 
                    });
                    
                    return `
                        <tr>
                            <td><strong>${v.violation_id}</strong></td>
                            <td>${timestamp}</td>
                            <td>${v.worker_id || 'N/A'}</td>
                            <td>${v.worker_name || 'Unknown'}</td>
                            <td><span class="violation-badge violation-${v.violation_type}">${v.violation_type.toUpperCase()}</span></td>
                            <td><span class="severity-badge severity-${v.severity}">${v.severity.toUpperCase()}</span></td>
                            <td>Camera ${v.camera_id || 'N/A'}</td>
                            <td>PKR ${v.fine_amount || 0}</td>
                            <td>
                                <div class="action-btns">
                                    <button class="action-btn action-resolve" onclick="resolveViolation('${v.violation_id}')">✓ Resolve</button>
                                </div>
                            </td>
                        </tr>
                    `;
                }).join('');
            } catch (error) {
                console.error('Error loading violations:', error);
                document.getElementById('violationsTableBody').innerHTML = '<tr><td colspan="9" style="text-align: center; padding: 30px;">Error loading data</td></tr>';
            }
        }

        // Apply filters
        function applyFilters() {
            loadViolations();
        }

        // Reset filters
        function resetFilters() {
            setDefaultDates();
            document.getElementById('violationType').value = '';
            document.getElementById('severity').value = '';
            document.getElementById('workerId').value = '';
            loadViolations();
        }

        // Resolve violation
        async function resolveViolation(violationId) {
            try {
                const response = await fetch(`${API_BASE}/violations/${violationId}/resolve`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                if (response.ok) {
                    alert('Violation resolved successfully!');
                    loadViolations();
                    loadStats();
                } else {
                    alert('Error resolving violation');
                }
            } catch (error) {
                console.error('Error resolving violation:', error);
                alert('Error resolving violation');
            }
        }

        // Initialize
        setDefaultDates();
        loadStats();
        loadViolations();

        // Refresh every 30 seconds
        setInterval(() => {
            loadStats();
            loadViolations();
        }, 30000);
    </script>

    <script>
    // ========== ADD THIS TO EVERY PAGE ==========
    // Authentication check
    window.addEventListener('load', () => {
        const token = localStorage.getItem('token');
        const user = JSON.parse(localStorage.getItem('user') || '{}');
        
        if (!token) {
            // Not logged in, redirect to login
            window.location.href = 'login.html';
            return;
        }
        
        // User is logged in, display their name if there's a user display element
        const userDisplay = document.getElementById('userDisplay');
        if (userDisplay) {
            userDisplay.textContent = user.full_name || 'User';
        }
    });
    
    // Logout function
    function handleLogout() {
        if (confirm('Are you sure you want to logout?')) {
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            window.location.href = 'login.html';
        }
    }
    // ========== END OF AUTH CODE ==========
    </script>
    <script src="auth.js"></script>
</body>
</html>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Workers Management</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #121212;
            color: #F3F4F6;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header {
            background: #1E1E1E;
            padding: 25px 30px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { color: #FFC107; font-size: 28px; font-weight: 700; }
        .nav-menu {
            background: #1E1E1E;
            padding: 15px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .nav-btn {
            padding: 12px 24px;
            background: transparent;
            color: #D1D5DB;
            border: 1px solid #333;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
        }
        .nav-btn:hover { transform: translateY(-2px); background: #333; }
        .nav-btn.active { background: #FFC107; color: #121212; border-color: #FFC107; font-weight: 700; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: #1E1E1E;
            padding: 20px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            transition: all 0.3s ease;
            text-align: center;
            position: relative;
            overflow: hidden;
        }
        .stat-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: #FFC107;
        }
        .stat-card:hover { transform: translateY(-5px); box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5); }
        .stat-icon { font-size: 32px; margin-bottom: 10px; }
        .stat-value { font-size: 32px; font-weight: 700; color: #F3F4F6; margin-bottom: 5px; }
        .stat-label { font-size: 13px; color: #9CA3AF; text-transform: uppercase; letter-spacing: 0.5px; }
        .card {
            background: #1E1E1E;
            padding: 25px;
            border-radius: 12px;
            border: 1px solid #333;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            margin-bottom: 30px;
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid #333;
        }
        .card-title { color: #FFC107; font-size: 20px; font-weight: 700; }
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .btn-primary { background: #FFC107; color: #121212; }
        .btn-success { background: #48bb78; color: #121212; }
        .btn:hover { transform: translateY(-2px); filter: brightness(1.1); box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3); }
        .search-filter { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
        .search-input {
            flex: 1;
            min-width: 200px;
            padding: 12px 15px;
            border: 1px solid #444;
            border-radius: 8px;
            font-size: 14px;
            background: #2D2D2D;
            color: #F3F4F6;
        }
        .search-input:focus { outline: none; border-color: #FFC107; box-shadow: 0 0 0 2px rgba(255, 193, 7, 0.2); }
        .filter-select {
            padding: 12px 15px;
            border: 1px solid #444;
            border-radius: 8px;
            font-size: 14px;
            background: #2D2D2D;
            color: #F3F4F6;
        }
        .filter-select:focus { outline: none; border-color: #FFC107; box-shadow: 0 0 0 2px rgba(255, 193, 7, 0.2); }
        .workers-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }
        .worker-card {
            background: #1E1E1E;
            border-radius: 12px;
            border: 1px solid #333;
            padding: 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            transition: all 0.3s ease;
            position: relative;
        }
        .worker-card:hover { transform: translateY(-5px); box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4); }
        .worker-header {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 1px solid #333;
        }
        .worker-photo {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: #FFC107;
            color: #121212;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            font-weight: 700;
        }
        .worker-info { flex: 1; }
        .worker-name { font-size: 16px; font-weight: 700; color: #F3F4F6; margin-bottom: 3px; }
        .worker-id { font-size: 13px; color: #9CA3AF; font-weight: 600; }
        .worker-details {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-bottom: 15px;
        }
        .detail-item { display: flex; flex-direction: column; gap: 3px; }
        .detail-label { font-size: 11px; color: #9CA3AF; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }
        .detail-value { font-size: 13px; color: #D1D5DB; font-weight: 600; }
        .worker-actions { display: flex; gap: 8px; margin-top: 15px; }
        .action-btn {
            flex: 1;
            padding: 8px 12px;
            border: none;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .action-edit { background: #2D2D2D; color: #D1D5DB; border: 1px solid #444; }
        .action-edit:hover { background: #333; }
        .action-delete { background: rgba(245, 101, 101, 0.2); color: #fc8181; border: 1px solid #fc8181; }
        .action-delete:hover { background: rgba(245, 101, 101, 0.4); }
        .status-indicator {
            position: absolute;
            top: 15px;
            right: 15px;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            border: 2px solid #1E1E1E;
        }
        .status-active { background: #48bb78; }
        .status-inactive { background: #9CA3AF; }
        
        /* Photo Upload Styles */
        .photo-upload-container {
            text-align: center;
            margin-bottom: 25px;
        }
        .photo-preview-large {
            width: 150px;
            height: 150px;
            border-radius: 50%;
            object-fit: cover;
            border: 4px solid #FFC107;
            margin: 0 auto 15px;
            display: none;
        }
        .photo-placeholder-large {
            width: 150px;
            height: 150px;
            border-radius: 50%;
            background: #2D2D2D;
            color: #9CA3AF;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 48px;
            margin: 0 auto 15px;
            border: 4px dashed #444;
        }
        .file-input-wrapper {
            position: relative;
            overflow: hidden;
            display: inline-block;
        }
        .file-input-wrapper input[type=file] {
            position: absolute;
            left: -9999px;
        }
        .file-input-label {
            padding: 10px 20px;
            background: #FFC107;
            color: #121212;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            font-size: 14px;
            transition: all 0.3s;
        }
        .file-input-label:hover {
            background: #F5B301;
            transform: translateY(-2px);
        }
        .worker-photo-img {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            object-fit: cover;
            border: 3px solid #FFC107;
        }
        
        /* Modal Styles */
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(5px);
        }
        .modal.active { display: flex; align-items: center; justify-content: center; }
        .modal-content {
            background: #1E1E1E;
            border: 1px solid #333;
            border-radius: 12px;
            padding: 30px;
            max-width: 600px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            color: #F3F4F6;
        }
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 25px;
            padding-bottom: 15px;
            border-bottom: 1px solid #333;
        }
        .modal-title { font-size: 24px; font-weight: 700; color: #FFC107; }
        .close-btn {
            font-size: 28px;
            color: #9CA3AF;
            cursor: pointer;
            border: none;
            background: none;
            padding: 0;
            width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .close-btn:hover { color: #F3F4F6; }
        .form-group {
            margin-bottom: 20px;
        }
        .form-label {
            display: block;
            font-size: 14px;
            font-weight: 600;
            color: #D1D5DB;
            margin-bottom: 8px;
        }
        .form-input, .form-select {
            width: 100%;
            padding: 12px 15px;
            border: 1px solid #444;
            border-radius: 8px;
            font-size: 14px;
            background: #2D2D2D;
            color: #F3F4F6;
            transition: all 0.3s ease;
        }
        .form-input:focus, .form-select:focus {
            outline: none;
            border-color: #FFC107;
            box-shadow: 0 0 0 2px rgba(255, 193, 7, 0.2);
        }
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        .modal-actions {
            display: flex;
            gap: 10px;
            margin-top: 25px;
        }
        .btn-cancel {
            background: #2D2D2D;
            color: #D1D5DB;
            border: 1px solid #444;
        }
        .btn-cancel:hover { background: #333; }
        .loading { text-align: center; padding: 20px; color: #9CA3AF; }
        
        @media (max-width: 768px) {
            .form-row { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fa-solid fa-hard-hat"></i> Workers Management</h1>
            <button class="btn btn-success" onclick="openAddModal()"><i class="fa-solid fa-plus"></i> Add Worker</button>
        </div>

        <nav class="nav-menu">
            <a href="dashboard.html" class="nav-btn">Dashboard</a>
            <a href="cctv.html" class="nav-btn">CCTV Feeds</a>
            <a href="violations.html" class="nav-btn">Violations</a>
            <a href="attendance.html" class="nav-btn">Attendance</a>
            <a href="salary.html" class="nav-btn">Salary & Fines</a>
            <a href="workers.html" class="nav-btn active">Workers</a>
            <a href="health.html" class="nav-btn">Health Alerts</a>
        </nav>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon"><i class="fa-solid fa-users"></i></div>
                <div class="stat-value" id="totalWorkers">...</div>
                <div class="stat-label">Total Workers</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="fa-solid fa-clipboard-check"></i></div>
                <div class="stat-value" id="activeWorkers">...</div>
                <div class="stat-label">Active</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="fa-solid fa-pause"></i></div>
                <div class="stat-value" id="inactiveWorkers">...</div>
                <div class="stat-label">Inactive</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="fa-regular fa-calendar"></i></div>
                <div class="stat-value" id="newWorkers">...</div>
                <div class="stat-label">New This Month</div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h2 class="card-title">Worker Directory</h2>
            </div>

            <div class="search-filter">
                <input type="text" class="search-input" placeholder="Search by ID, name, or phone..." id="searchWorkers" onkeyup="applyFilters()">
                <select class="filter-select" id="departmentFilter" onchange="applyFilters()">
                    <option value="">All Departments</option>
                    <option value="Construction">Construction</option>
                    <option value="Electrical">Electrical</option>
                    <option value="Plumbing">Plumbing</option>
                    <option value="Carpentry">Carpentry</option>
                </select>
                <select class="filter-select" id="statusFilter" onchange="applyFilters()">
                    <option value="">All Status</option>
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                </select>
            </div>

            <div class="workers-grid" id="workersGrid">
                <div class="loading">Loading workers data...</div>
            </div>
        </div>
    </div>

    <!-- Add/Edit Worker Modal -->
    <div id="workerModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 class="modal-title" id="modalTitle">Add New Worker</h2>
                <button class="close-btn" onclick="closeModal()">&times;</button>
            </div>
            <form id="workerForm" onsubmit="saveWorker(event)" enctype="multipart/form-data">
                <input type="hidden" id="editMode" value="false">
                <input type="hidden" id="originalWorkerId">
                <input type="hidden" id="existingPhotoPath">
                
                <div class="webcam-capture-container" style="text-align: center; margin-bottom: 25px;">
                    <video id="webcam" autoplay playsinline style="width: 250px; height: 250px; border-radius: 15px; border: 4px solid #667eea; object-fit: cover; margin-bottom: 15px; background: #e2e8f0; display: none; margin-left: auto; margin-right: auto;"></video>
                    <img id="photoPreview" class="photo-preview-large" alt="Photo Preview" style="display:none; width: 250px; height: 250px; border-radius: 15px;">
                    <div id="photoPlaceholder" class="photo-placeholder-large" style="width: 250px; height: 250px; border-radius: 15px; margin-left: auto; margin-right: auto;">📷</div>
                    
                    <div class="capture-controls" style="margin-bottom: 15px;">
                        <button type="button" id="startCamBtn" class="btn btn-primary" onclick="startWebcam()">Start Camera</button>
                        <button type="button" id="captureBtn" class="btn btn-success" style="display: none;" onclick="captureBurst()">📸 Capture Face (5 Photos)</button>
                        <button type="button" id="retakeBtn" class="btn btn-cancel" style="display: none;" onclick="retakePhotos()">↻ Retake</button>
                    </div>
                    
                    <div id="capturedThumbnails" style="display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;"></div>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Worker ID *</label>
                        <input type="text" class="form-input" id="workerId" name="worker_id" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Full Name *</label>
                        <input type="text" class="form-input" id="workerName" name="name" required>
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">CNIC *</label>
                        <input type="text" class="form-input" id="workerCnic" name="cnic" placeholder="12345-1234567-1" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Phone</label>
                        <input type="tel" class="form-input" id="workerPhone" name="phone" placeholder="+92 300 1234567">
                    </div>
                </div>

                <div class="form-group">
                    <label class="form-label">Department</label>
                    <select class="form-select" id="workerDept" name="department">
                        <option value="">Select Department</option>
                        <option value="Construction">Construction</option>
                        <option value="Electrical">Electrical</option>
                        <option value="Plumbing">Plumbing</option>
                        <option value="Carpentry">Carpentry</option>
                    </select>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Wage Type *</label>
                        <select class="form-select" id="wageType" name="wage_type" required>
                            <option value="daily">Daily</option>
                            <option value="hourly">Hourly</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Wage Rate (PKR) *</label>
                        <input type="number" class="form-input" id="wageRate" name="wage_rate" step="0.01" required>
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Join Date *</label>
                        <input type="date" class="form-input" id="joinDate" name="join_date" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Status</label>
                        <select class="form-select" id="workerStatus" name="status">
                            <option value="active">Active</option>
                            <option value="inactive">Inactive</option>
                        </select>
                    </div>
                </div>

                <div class="modal-actions">
                    <button type="button" class="btn btn-cancel" onclick="closeModal()">Cancel</button>
                    <button type="submit" class="btn btn-success" style="flex: 1;">Save Worker</button>
                </div>
            </form>
        </div>
    </div>

    <script>
    // ========== ADD THIS TO EVERY PAGE ==========
    // Authentication check
    window.addEventListener('load', () => {
        const token = localStorage.getItem('token');
        const user = JSON.parse(localStorage.getItem('user') || '{}');
        
        if (!token) {
            // Not logged in, redirect to login
            window.location.href = 'login.html';
            return;
        }
        
        // User is logged in, display their name if there's a user display element
        const userDisplay = document.getElementById('userDisplay');
        if (userDisplay) {
            userDisplay.textContent = user.full_name || 'User';
        }
    });
    
    // Logout function
    function handleLogout() {
        if (confirm('Are you sure you want to logout?')) {
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            window.location.href = 'login.html';
        }
    }
    // ========== END OF AUTH CODE ==========
    </script>

    <script>
        const API_BASE = 'http://localhost:4000/api';
        let allWorkers = [];

        async function loadStats() {
            try {
                const response = await fetch(`${API_BASE}/workers/stats/summary`);
                const stats = await response.json();
                
                document.getElementById('totalWorkers').textContent = stats.total_workers || 0;
                document.getElementById('activeWorkers').textContent = stats.active_workers || 0;
                document.getElementById('inactiveWorkers').textContent = stats.inactive_workers || 0;
                document.getElementById('newWorkers').textContent = stats.new_this_month || 0;
            } catch (error) {
                console.error('Error loading stats:', error);
            }
        }

        async function loadWorkers() {
            try {
                const response = await fetch(`${API_BASE}/workers`);
                allWorkers = await response.json();
                displayWorkers(allWorkers);
            } catch (error) {
                console.error('Error loading workers:', error);
                document.getElementById('workersGrid').innerHTML = '<div class="loading">Error loading workers data</div>';
            }
        }

        function displayWorkers(workers) {
            const grid = document.getElementById('workersGrid');
            
            if (workers.length === 0) {
                grid.innerHTML = '<div class="loading">No workers found</div>';
                return;
            }
            
            grid.innerHTML = workers.map(w => {
                const initial = w.name.charAt(0).toUpperCase();
                const joinDate = new Date(w.join_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                
                // Display photo or placeholder
                const photoElement = w.photo_path 
                    ? `<img src="http://localhost:4000${w.photo_path}" class="worker-photo-img" alt="${w.name}">`
                    : `<div class="worker-photo">${initial}</div>`;
                
                return `
                    <div class="worker-card">
                        <div class="status-indicator status-${w.status}" title="${w.status}"></div>
                        <div class="worker-header">
                            ${photoElement}
                            <div class="worker-info">
                                <div class="worker-name">${w.name}</div>
                                <div class="worker-id">${w.worker_id}</div>
                            </div>
                        </div>
                        <div class="worker-details">
                            <div class="detail-item">
                                <span class="detail-label">Phone</span>
                                <span class="detail-value">${w.phone || 'N/A'}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">CNIC</span>
                                <span class="detail-value">${w.cnic}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Wage Type</span>
                                <span class="detail-value">${w.wage_type}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Wage Rate</span>
                                <span class="detail-value">PKR ${w.wage_rate}/${w.wage_type === 'hourly' ? 'hr' : 'day'}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Join Date</span>
                                <span class="detail-value">${joinDate}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">Department</span>
                                <span class="detail-value">${w.department || 'N/A'}</span>
                            </div>
                        </div>
                        <div class="worker-actions">
                            <button class="action-btn action-edit" onclick='editWorker(${JSON.stringify(w)})'>✏️ Edit</button>
                            <button class="action-btn action-delete" onclick="deleteWorker('${w.worker_id}', '${w.name}')">🗑️ Delete</button>
                        </div>
                    </div>
                `;
            }).join('');
        }

        function applyFilters() {
            const searchTerm = document.getElementById('searchWorkers').value.toLowerCase();
            const department = document.getElementById('departmentFilter').value;
            const status = document.getElementById('statusFilter').value;
            
            const filtered = allWorkers.filter(w => {
                const matchesSearch = !searchTerm || 
                    w.name.toLowerCase().includes(searchTerm) || 
                    w.worker_id.toLowerCase().includes(searchTerm) ||
                    (w.phone && w.phone.includes(searchTerm));
                
                const matchesDepartment = !department || w.department === department;
                const matchesStatus = !status || w.status === status;
                
                return matchesSearch && matchesDepartment && matchesStatus;
            });
            
            displayWorkers(filtered);
        }

        function openAddModal() {
            document.getElementById('modalTitle').textContent = 'Add New Worker';
            document.getElementById('editMode').value = 'false';
            document.getElementById('workerForm').reset();
            document.getElementById('workerId').disabled = false;
            document.getElementById('joinDate').value = new Date().toISOString().split('T')[0];
            
            // Reset photo preview and camera
            stopWebcam();
            retakePhotos();
            document.getElementById('photoPreview').style.display = 'none';
            document.getElementById('photoPlaceholder').style.display = 'flex';
            document.getElementById('startCamBtn').style.display = 'inline-block';
            document.getElementById('existingPhotoPath').value = '';
            
            document.getElementById('workerModal').classList.add('active');
        }

        function editWorker(worker) {
            document.getElementById('modalTitle').textContent = 'Edit Worker';
            document.getElementById('editMode').value = 'true';
            document.getElementById('originalWorkerId').value = worker.worker_id;
            
            document.getElementById('workerId').value = worker.worker_id;
            document.getElementById('workerId').disabled = true;
            document.getElementById('workerName').value = worker.name;
            document.getElementById('workerCnic').value = worker.cnic;
            document.getElementById('workerPhone').value = worker.phone || '';
            document.getElementById('workerDept').value = worker.department || '';
            document.getElementById('wageType').value = worker.wage_type;
            document.getElementById('wageRate').value = worker.wage_rate;
            document.getElementById('joinDate').value = worker.join_date.split('T')[0];
            document.getElementById('workerStatus').value = worker.status;
            
            // Handle existing photo
            stopWebcam();
            retakePhotos();
            if (worker.photo_path) {
                const preview = document.getElementById('photoPreview');
                preview.src = `http://localhost:4000${worker.photo_path}`;
                preview.style.display = 'block';
                document.getElementById('photoPlaceholder').style.display = 'none';
                document.getElementById('startCamBtn').textContent = 'Replace Face Scan';
                document.getElementById('startCamBtn').style.display = 'inline-block';
                document.getElementById('existingPhotoPath').value = worker.photo_path;
            } else {
                document.getElementById('photoPreview').style.display = 'none';
                document.getElementById('photoPlaceholder').style.display = 'flex';
                document.getElementById('startCamBtn').textContent = 'Start Camera';
                document.getElementById('startCamBtn').style.display = 'inline-block';
                document.getElementById('existingPhotoPath').value = '';
            }
            
            document.getElementById('workerModal').classList.add('active');
        }

        function closeModal() {
            document.getElementById('workerModal').classList.remove('active');
            document.getElementById('workerForm').reset();
            document.getElementById('photoPreview').style.display = 'none';
            document.getElementById('photoPlaceholder').style.display = 'flex';
            stopWebcam();
        }

        let capturedPhotos = [];
        let stream = null;

        async function startWebcam() {
            try {
                stream = await navigator.mediaDevices.getUserMedia({ video: true });
                const video = document.getElementById('webcam');
                video.srcObject = stream;
                video.style.display = 'block';
                document.getElementById('photoPlaceholder').style.display = 'none';
                document.getElementById('photoPreview').style.display = 'none';
                document.getElementById('startCamBtn').style.display = 'none';
                document.getElementById('captureBtn').style.display = 'inline-block';
                document.getElementById('retakeBtn').style.display = 'inline-block';
                retakePhotos();
            } catch (err) {
                console.error("Error accessing camera:", err);
                alert("Could not access camera. Please allow permissions.");
            }
        }

        function stopWebcam() {
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
                stream = null;
            }
            document.getElementById('webcam').style.display = 'none';
            document.getElementById('captureBtn').style.display = 'none';
            document.getElementById('retakeBtn').style.display = 'none';
        }

        async function captureBurst() {
            const video = document.getElementById('webcam');
            const btn = document.getElementById('captureBtn');
            btn.disabled = true;
            btn.textContent = "Capturing...";
            capturedPhotos = [];
            document.getElementById('capturedThumbnails').innerHTML = '';

            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth || 640;
            canvas.height = video.videoHeight || 480;
            const ctx = canvas.getContext('2d');

            for(let i=0; i<5; i++) {
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
                capturedPhotos.push(dataUrl);
                
                // Show thumbnail
                const img = document.createElement('img');
                img.src = dataUrl;
                img.style.width = '60px';
                img.style.height = '60px';
                img.style.objectFit = 'cover';
                img.style.borderRadius = '8px';
                img.style.border = '2px solid #fff';
                document.getElementById('capturedThumbnails').appendChild(img);
                
                // Wait 400ms between captures to get slight variations
                await new Promise(r => setTimeout(r, 400)); 
            }
            
            btn.textContent = "✅ Captured 5 Photos";
        }

        function retakePhotos() {
            capturedPhotos = [];
            document.getElementById('capturedThumbnails').innerHTML = '';
            const btn = document.getElementById('captureBtn');
            btn.disabled = false;
            btn.textContent = "📸 Capture Face (5 Photos)";
        }

        function previewPhoto(event) {
            const file = event.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const preview = document.getElementById('photoPreview');
                    const placeholder = document.getElementById('photoPlaceholder');
                    preview.src = e.target.result;
                    preview.style.display = 'block';
                    placeholder.style.display = 'none';
                }
                reader.readAsDataURL(file);
            }
        }

        async function saveWorker(event) {
            event.preventDefault();
            
            const isEditMode = document.getElementById('editMode').value === 'true';
            const workerId = document.getElementById('workerId').value;
            
            if (!isEditMode && capturedPhotos.length === 0) {
                alert("Please capture faces for the new worker via Webcam!");
                return;
            }

            const payload = {
                worker_id: workerId,
                name: document.getElementById('workerName').value,
                cnic: document.getElementById('workerCnic').value,
                phone: document.getElementById('workerPhone').value,
                department: document.getElementById('workerDept').value,
                wage_type: document.getElementById('wageType').value,
                wage_rate: document.getElementById('wageRate').value,
                join_date: document.getElementById('joinDate').value,
                status: document.getElementById('workerStatus').value,
                photos: capturedPhotos,
                existing_photo_path: document.getElementById('existingPhotoPath').value
            };

            try {
                let response;
                if (isEditMode) {
                    const originalId = document.getElementById('originalWorkerId').value;
                    response = await fetch(`${API_BASE}/workers/${originalId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                } else {
                    response = await fetch(`${API_BASE}/workers`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                }

                const result = await response.json();

                if (response.ok) {
                    alert(isEditMode ? 'Worker updated successfully!' : 'Worker added successfully!');
                    closeModal();
                    loadWorkers();
                    loadStats();
                } else {
                    alert('Error: ' + result.error);
                }
            } catch (error) {
                console.error('Error saving worker:', error);
                alert('Failed to save worker. Please try again.');
            }
        }

        async function deleteWorker(workerId, workerName) {
            if (!confirm(`Are you sure you want to delete ${workerName} (${workerId})?\n\nThis action cannot be undone.`)) {
                return;
            }

            try {
                const response = await fetch(`${API_BASE}/workers/${workerId}`, {
                    method: 'DELETE'
                });

                const result = await response.json();

                if (response.ok) {
                    alert('Worker deleted successfully!');
                    loadWorkers();
                    loadStats();
                } else {
                    alert('Error: ' + result.error);
                }
            } catch (error) {
                console.error('Error deleting worker:', error);
                alert('Failed to delete worker. Please try again.');
            }
        }

        // Close modal when clicking outside
        window.onclick = function(event) {
            const modal = document.getElementById('workerModal');
            if (event.target === modal) {
                closeModal();
            }
        }

        // Initialize
        loadStats();
        loadWorkers();

        // Refresh every 60 seconds
        setInterval(() => {
            loadStats();
            loadWorkers();
        }, 60000);
    </script>
    <script src="auth.js"></script>
</body>
</html>
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
{
  "name": "construction-safety",
  "version": "1.0.0",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": {
      "name": "construction-safety",
      "version": "1.0.0",
      "license": "ISC",
      "dependencies": {
        "bcrypt": "^6.0.0",
        "body-parser": "^1.20.4",
        "cookie-parser": "^1.4.7",
        "cors": "^2.8.5",
        "dotenv": "^16.6.1",
        "express": "^4.22.1",
        "express-rate-limit": "^8.5.1",
        "helmet": "^8.1.0",
        "jsonwebtoken": "^9.0.3",
        "multer": "^2.0.2",
        "mysql2": "^3.22.1",
        "ws": "^8.14.2"
      },
      "devDependencies": {
        "nodemon": "^3.0.2"
      }
    },
    "node_modules/@types/node": {
      "version": "25.6.0",
      "resolved": "https://registry.npmjs.org/@types/node/-/node-25.6.0.tgz",
      "integrity": "sha512-+qIYRKdNYJwY3vRCZMdJbPLJAtGjQBudzZzdzwQYkEPQd+PJGixUL5QfvCLDaULoLv+RhT3LDkwEfKaAkgSmNQ==",
      "license": "MIT",
      "peer": true,
      "dependencies": {
        "undici-types": "~7.19.0"
      }
    },
    "node_modules/accepts": {
      "version": "1.3.8",
      "resolved": "https://registry.npmjs.org/accepts/-/accepts-1.3.8.tgz",
      "integrity": "sha512-PYAthTa2m2VKxuvSD3DPC/Gy+U+sOA1LAuT8mkmRuvw+NACSaeXEQ+NHcVF7rONl6qcaxV3Uuemwawk+7+SJLw==",
      "license": "MIT",
      "dependencies": {
        "mime-types": "~2.1.34",
        "negotiator": "0.6.3"
      },
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/anymatch": {
      "version": "3.1.3",
      "resolved": "https://registry.npmjs.org/anymatch/-/anymatch-3.1.3.tgz",
      "integrity": "sha512-KMReFUr0B4t+D+OBkjR3KYqvocp2XaSzO55UcB6mgQMd3KbcE+mWTyvVV7D/zsdEbNnV6acZUutkiHQXvTr1Rw==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "normalize-path": "^3.0.0",
        "picomatch": "^2.0.4"
      },
      "engines": {
        "node": ">= 8"
      }
    },
    "node_modules/append-field": {
      "version": "1.0.0",
      "resolved": "https://registry.npmjs.org/append-field/-/append-field-1.0.0.tgz",
      "integrity": "sha512-klpgFSWLW1ZEs8svjfb7g4qWY0YS5imI82dTg+QahUvJ8YqAY0P10Uk8tTyh9ZGuYEZEMaeJYCF5BFuX552hsw==",
      "license": "MIT"
    },
    "node_modules/array-flatten": {
      "version": "1.1.1",
      "resolved": "https://registry.npmjs.org/array-flatten/-/array-flatten-1.1.1.tgz",
      "integrity": "sha512-PCVAQswWemu6UdxsDFFX/+gVeYqKAod3D3UVm91jHwynguOwAvYPhx8nNlM++NqRcK6CxxpUafjmhIdKiHibqg==",
      "license": "MIT"
    },
    "node_modules/aws-ssl-profiles": {
      "version": "1.1.2",
      "resolved": "https://registry.npmjs.org/aws-ssl-profiles/-/aws-ssl-profiles-1.1.2.tgz",
      "integrity": "sha512-NZKeq9AfyQvEeNlN0zSYAaWrmBffJh3IELMZfRpJVWgrpEbtEpnjvzqBPf+mxoI287JohRDoa+/nsfqqiZmF6g==",
      "license": "MIT",
      "engines": {
        "node": ">= 6.0.0"
      }
    },
    "node_modules/balanced-match": {
      "version": "1.0.2",
      "resolved": "https://registry.npmjs.org/balanced-match/-/balanced-match-1.0.2.tgz",
      "integrity": "sha512-3oSeUO0TMV67hN1AmbXsK4yaqU7tjiHlbxRDZOpH0KW9+CeX4bRAaX0Anxt0tx2MrpRpWwQaPwIlISEJhYU5Pw==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/bcrypt": {
      "version": "6.0.0",
      "resolved": "https://registry.npmjs.org/bcrypt/-/bcrypt-6.0.0.tgz",
      "integrity": "sha512-cU8v/EGSrnH+HnxV2z0J7/blxH8gq7Xh2JFT6Aroax7UohdmiJJlxApMxtKfuI7z68NvvVcmR78k2LbT6efhRg==",
      "hasInstallScript": true,
      "license": "MIT",
      "dependencies": {
        "node-addon-api": "^8.3.0",
        "node-gyp-build": "^4.8.4"
      },
      "engines": {
        "node": ">= 18"
      }
    },
    "node_modules/binary-extensions": {
      "version": "2.3.0",
      "resolved": "https://registry.npmjs.org/binary-extensions/-/binary-extensions-2.3.0.tgz",
      "integrity": "sha512-Ceh+7ox5qe7LJuLHoY0feh3pHuUDHAcRUeyL2VYghZwfpkNIy/+8Ocg0a3UuSoYzavmylwuLWQOf3hl0jjMMIw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=8"
      },
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/body-parser": {
      "version": "1.20.4",
      "resolved": "https://registry.npmjs.org/body-parser/-/body-parser-1.20.4.tgz",
      "integrity": "sha512-ZTgYYLMOXY9qKU/57FAo8F+HA2dGX7bqGc71txDRC1rS4frdFI5R7NhluHxH6M0YItAP0sHB4uqAOcYKxO6uGA==",
      "license": "MIT",
      "dependencies": {
        "bytes": "~3.1.2",
        "content-type": "~1.0.5",
        "debug": "2.6.9",
        "depd": "2.0.0",
        "destroy": "~1.2.0",
        "http-errors": "~2.0.1",
        "iconv-lite": "~0.4.24",
        "on-finished": "~2.4.1",
        "qs": "~6.14.0",
        "raw-body": "~2.5.3",
        "type-is": "~1.6.18",
        "unpipe": "~1.0.0"
      },
      "engines": {
        "node": ">= 0.8",
        "npm": "1.2.8000 || >= 1.4.16"
      }
    },
    "node_modules/body-parser/node_modules/debug": {
      "version": "2.6.9",
      "resolved": "https://registry.npmjs.org/debug/-/debug-2.6.9.tgz",
      "integrity": "sha512-bC7ElrdJaJnPbAP+1EotYvqZsb3ecl5wi6Bfi6BJTUcNowp6cvspg0jXznRTKDjm/E7AdgFBVeAPVMNcKGsHMA==",
      "license": "MIT",
      "dependencies": {
        "ms": "2.0.0"
      }
    },
    "node_modules/body-parser/node_modules/iconv-lite": {
      "version": "0.4.24",
      "resolved": "https://registry.npmjs.org/iconv-lite/-/iconv-lite-0.4.24.tgz",
      "integrity": "sha512-v3MXnZAcvnywkTUEZomIActle7RXXeedOR31wwl7VlyoXO4Qi9arvSenNQWne1TcRwhCL1HwLI21bEqdpj8/rA==",
      "license": "MIT",
      "dependencies": {
        "safer-buffer": ">= 2.1.2 < 3"
      },
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/body-parser/node_modules/ms": {
      "version": "2.0.0",
      "resolved": "https://registry.npmjs.org/ms/-/ms-2.0.0.tgz",
      "integrity": "sha512-Tpp60P6IUJDTuOq/5Z8cdskzJujfwqfOTkrwIwj7IRISpnkJnT6SyJ4PCPnGMoFjC9ddhal5KVIYtAt97ix05A==",
      "license": "MIT"
    },
    "node_modules/brace-expansion": {
      "version": "1.1.14",
      "resolved": "https://registry.npmjs.org/brace-expansion/-/brace-expansion-1.1.14.tgz",
      "integrity": "sha512-MWPGfDxnyzKU7rNOW9SP/c50vi3xrmrua/+6hfPbCS2ABNWfx24vPidzvC7krjU/RTo235sV776ymlsMtGKj8g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "balanced-match": "^1.0.0",
        "concat-map": "0.0.1"
      }
    },
    "node_modules/braces": {
      "version": "3.0.3",
      "resolved": "https://registry.npmjs.org/braces/-/braces-3.0.3.tgz",
      "integrity": "sha512-yQbXgO/OSZVD2IsiLlro+7Hf6Q18EJrKSEsdoMzKePKXct3gvD8oLcOQdIzGupr5Fj+EDe8gO/lxc1BzfMpxvA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "fill-range": "^7.1.1"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/buffer-equal-constant-time": {
      "version": "1.0.1",
      "resolved": "https://registry.npmjs.org/buffer-equal-constant-time/-/buffer-equal-constant-time-1.0.1.tgz",
      "integrity": "sha512-zRpUiDwd/xk6ADqPMATG8vc9VPrkck7T07OIx0gnjmJAnHnTVXNQG3vfvWNuiZIkwu9KrKdA1iJKfsfTVxE6NA==",
      "license": "BSD-3-Clause"
    },
    "node_modules/buffer-from": {
      "version": "1.1.2",
      "resolved": "https://registry.npmjs.org/buffer-from/-/buffer-from-1.1.2.tgz",
      "integrity": "sha512-E+XQCRwSbaaiChtv6k6Dwgc+bx+Bs6vuKJHHl5kox/BaKbhiXzqQOwK4cO22yElGp2OCmjwVhT3HmxgyPGnJfQ==",
      "license": "MIT"
    },
    "node_modules/busboy": {
      "version": "1.6.0",
      "resolved": "https://registry.npmjs.org/busboy/-/busboy-1.6.0.tgz",
      "integrity": "sha512-8SFQbg/0hQ9xy3UNTB0YEnsNBbWfhf7RtnzpL7TkBiTBRfrQ9Fxcnz7VJsleJpyp6rVLvXiuORqjlHi5q+PYuA==",
      "dependencies": {
        "streamsearch": "^1.1.0"
      },
      "engines": {
        "node": ">=10.16.0"
      }
    },
    "node_modules/bytes": {
      "version": "3.1.2",
      "resolved": "https://registry.npmjs.org/bytes/-/bytes-3.1.2.tgz",
      "integrity": "sha512-/Nf7TyzTx6S3yRJObOAV7956r8cr2+Oj8AC5dt8wSP3BQAoeX58NoHyCU8P8zGkNXStjTSi6fzO6F0pBdcYbEg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/call-bind-apply-helpers": {
      "version": "1.0.2",
      "resolved": "https://registry.npmjs.org/call-bind-apply-helpers/-/call-bind-apply-helpers-1.0.2.tgz",
      "integrity": "sha512-Sp1ablJ0ivDkSzjcaJdxEunN5/XvksFJ2sMBFfq6x0ryhQV/2b/KwFe21cMpmHtPOSij8K99/wSfoEuTObmuMQ==",
      "license": "MIT",
      "dependencies": {
        "es-errors": "^1.3.0",
        "function-bind": "^1.1.2"
      },
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/call-bound": {
      "version": "1.0.4",
      "resolved": "https://registry.npmjs.org/call-bound/-/call-bound-1.0.4.tgz",
      "integrity": "sha512-+ys997U96po4Kx/ABpBCqhA9EuxJaQWDQg7295H4hBphv3IZg0boBKuwYpt4YXp6MZ5AmZQnU/tyMTlRpaSejg==",
      "license": "MIT",
      "dependencies": {
        "call-bind-apply-helpers": "^1.0.2",
        "get-intrinsic": "^1.3.0"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/chokidar": {
      "version": "3.6.0",
      "resolved": "https://registry.npmjs.org/chokidar/-/chokidar-3.6.0.tgz",
      "integrity": "sha512-7VT13fmjotKpGipCW9JEQAusEPE+Ei8nl6/g4FBAmIm0GOOLMua9NDDo/DWp0ZAxCr3cPq5ZpBqmPAQgDda2Pw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "anymatch": "~3.1.2",
        "braces": "~3.0.2",
        "glob-parent": "~5.1.2",
        "is-binary-path": "~2.1.0",
        "is-glob": "~4.0.1",
        "normalize-path": "~3.0.0",
        "readdirp": "~3.6.0"
      },
      "engines": {
        "node": ">= 8.10.0"
      },
      "funding": {
        "url": "https://paulmillr.com/funding/"
      },
      "optionalDependencies": {
        "fsevents": "~2.3.2"
      }
    },
    "node_modules/concat-map": {
      "version": "0.0.1",
      "resolved": "https://registry.npmjs.org/concat-map/-/concat-map-0.0.1.tgz",
      "integrity": "sha512-/Srv4dswyQNBfohGpz9o6Yb3Gz3SrUDqBH5rTuhGR7ahtlbYKnVxw2bCFMRljaA7EXHaXZ8wsHdodFvbkhKmqg==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/concat-stream": {
      "version": "2.0.0",
      "resolved": "https://registry.npmjs.org/concat-stream/-/concat-stream-2.0.0.tgz",
      "integrity": "sha512-MWufYdFw53ccGjCA+Ol7XJYpAlW6/prSMzuPOTRnJGcGzuhLn4Scrz7qf6o8bROZ514ltazcIFJZevcfbo0x7A==",
      "engines": [
        "node >= 6.0"
      ],
      "license": "MIT",
      "dependencies": {
        "buffer-from": "^1.0.0",
        "inherits": "^2.0.3",
        "readable-stream": "^3.0.2",
        "typedarray": "^0.0.6"
      }
    },
    "node_modules/content-disposition": {
      "version": "0.5.4",
      "resolved": "https://registry.npmjs.org/content-disposition/-/content-disposition-0.5.4.tgz",
      "integrity": "sha512-FveZTNuGw04cxlAiWbzi6zTAL/lhehaWbTtgluJh4/E95DqMwTmha3KZN1aAWA8cFIhHzMZUvLevkw5Rqk+tSQ==",
      "license": "MIT",
      "dependencies": {
        "safe-buffer": "5.2.1"
      },
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/content-type": {
      "version": "1.0.5",
      "resolved": "https://registry.npmjs.org/content-type/-/content-type-1.0.5.tgz",
      "integrity": "sha512-nTjqfcBFEipKdXCv4YDQWCfmcLZKm81ldF0pAopTvyrFGVbcR6P/VAAd5G7N+0tTr8QqiU0tFadD6FK4NtJwOA==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/cookie": {
      "version": "0.7.2",
      "resolved": "https://registry.npmjs.org/cookie/-/cookie-0.7.2.tgz",
      "integrity": "sha512-yki5XnKuf750l50uGTllt6kKILY4nQ1eNIQatoXEByZ5dWgnKqbnqmTrBE5B4N7lrMJKQ2ytWMiTO2o0v6Ew/w==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/cookie-parser": {
      "version": "1.4.7",
      "resolved": "https://registry.npmjs.org/cookie-parser/-/cookie-parser-1.4.7.tgz",
      "integrity": "sha512-nGUvgXnotP3BsjiLX2ypbQnWoGUPIIfHQNZkkC668ntrzGWEZVW70HDEB1qnNGMicPje6EttlIgzo51YSwNQGw==",
      "license": "MIT",
      "dependencies": {
        "cookie": "0.7.2",
        "cookie-signature": "1.0.6"
      },
      "engines": {
        "node": ">= 0.8.0"
      }
    },
    "node_modules/cookie-parser/node_modules/cookie-signature": {
      "version": "1.0.6",
      "resolved": "https://registry.npmjs.org/cookie-signature/-/cookie-signature-1.0.6.tgz",
      "integrity": "sha512-QADzlaHc8icV8I7vbaJXJwod9HWYp8uCqf1xa4OfNu1T7JVxQIrUgOWtHdNDtPiywmFbiS12VjotIXLrKM3orQ==",
      "license": "MIT"
    },
    "node_modules/cookie-signature": {
      "version": "1.0.7",
      "resolved": "https://registry.npmjs.org/cookie-signature/-/cookie-signature-1.0.7.tgz",
      "integrity": "sha512-NXdYc3dLr47pBkpUCHtKSwIOQXLVn8dZEuywboCOJY/osA0wFSLlSawr3KN8qXJEyX66FcONTH8EIlVuK0yyFA==",
      "license": "MIT"
    },
    "node_modules/cors": {
      "version": "2.8.5",
      "resolved": "https://registry.npmjs.org/cors/-/cors-2.8.5.tgz",
      "integrity": "sha512-KIHbLJqu73RGr/hnbrO9uBeixNGuvSQjul/jdFvS/KFSIH1hWVd1ng7zOHx+YrEfInLG7q4n6GHQ9cDtxv/P6g==",
      "license": "MIT",
      "dependencies": {
        "object-assign": "^4",
        "vary": "^1"
      },
      "engines": {
        "node": ">= 0.10"
      }
    },
    "node_modules/debug": {
      "version": "4.4.3",
      "resolved": "https://registry.npmjs.org/debug/-/debug-4.4.3.tgz",
      "integrity": "sha512-RGwwWnwQvkVfavKVt22FGLw+xYSdzARwm0ru6DhTVA3umU5hZc28V3kO4stgYryrTlLpuvgI9GiijltAjNbcqA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "ms": "^2.1.3"
      },
      "engines": {
        "node": ">=6.0"
      },
      "peerDependenciesMeta": {
        "supports-color": {
          "optional": true
        }
      }
    },
    "node_modules/denque": {
      "version": "2.1.0",
      "resolved": "https://registry.npmjs.org/denque/-/denque-2.1.0.tgz",
      "integrity": "sha512-HVQE3AAb/pxF8fQAoiqpvg9i3evqug3hoiwakOyZAwJm+6vZehbkYXZ0l4JxS+I3QxM97v5aaRNhj8v5oBhekw==",
      "license": "Apache-2.0",
      "engines": {
        "node": ">=0.10"
      }
    },
    "node_modules/depd": {
      "version": "2.0.0",
      "resolved": "https://registry.npmjs.org/depd/-/depd-2.0.0.tgz",
      "integrity": "sha512-g7nH6P6dyDioJogAAGprGpCtVImJhpPk/roCzdb3fIh61/s/nPsfR6onyMwkCAR/OlC3yBC0lESvUoQEAssIrw==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/destroy": {
      "version": "1.2.0",
      "resolved": "https://registry.npmjs.org/destroy/-/destroy-1.2.0.tgz",
      "integrity": "sha512-2sJGJTaXIIaR1w4iJSNoN0hnMY7Gpc/n8D4qSCJw8QqFWXf7cuAgnEHxBpweaVcPevC2l3KpjYCx3NypQQgaJg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8",
        "npm": "1.2.8000 || >= 1.4.16"
      }
    },
    "node_modules/dotenv": {
      "version": "16.6.1",
      "resolved": "https://registry.npmjs.org/dotenv/-/dotenv-16.6.1.tgz",
      "integrity": "sha512-uBq4egWHTcTt33a72vpSG0z3HnPuIl6NqYcTrKEg2azoEyl2hpW0zqlxysq2pK9HlDIHyHyakeYaYnSAwd8bow==",
      "license": "BSD-2-Clause",
      "engines": {
        "node": ">=12"
      },
      "funding": {
        "url": "https://dotenvx.com"
      }
    },
    "node_modules/dunder-proto": {
      "version": "1.0.1",
      "resolved": "https://registry.npmjs.org/dunder-proto/-/dunder-proto-1.0.1.tgz",
      "integrity": "sha512-KIN/nDJBQRcXw0MLVhZE9iQHmG68qAVIBg9CqmUYjmQIhgij9U5MFvrqkUL5FbtyyzZuOeOt0zdeRe4UY7ct+A==",
      "license": "MIT",
      "dependencies": {
        "call-bind-apply-helpers": "^1.0.1",
        "es-errors": "^1.3.0",
        "gopd": "^1.2.0"
      },
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/ecdsa-sig-formatter": {
      "version": "1.0.11",
      "resolved": "https://registry.npmjs.org/ecdsa-sig-formatter/-/ecdsa-sig-formatter-1.0.11.tgz",
      "integrity": "sha512-nagl3RYrbNv6kQkeJIpt6NJZy8twLB/2vtz6yN9Z4vRKHN4/QZJIEbqohALSgwKdnksuY3k5Addp5lg8sVoVcQ==",
      "license": "Apache-2.0",
      "dependencies": {
        "safe-buffer": "^5.0.1"
      }
    },
    "node_modules/ee-first": {
      "version": "1.1.1",
      "resolved": "https://registry.npmjs.org/ee-first/-/ee-first-1.1.1.tgz",
      "integrity": "sha512-WMwm9LhRUo+WUaRN+vRuETqG89IgZphVSNkdFgeb6sS/E4OrDIN7t48CAewSHXc6C8lefD8KKfr5vY61brQlow==",
      "license": "MIT"
    },
    "node_modules/encodeurl": {
      "version": "2.0.0",
      "resolved": "https://registry.npmjs.org/encodeurl/-/encodeurl-2.0.0.tgz",
      "integrity": "sha512-Q0n9HRi4m6JuGIV1eFlmvJB7ZEVxu93IrMyiMsGC0lrMJMWzRgx6WGquyfQgZVb31vhGgXnfmPNNXmxnOkRBrg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/es-define-property": {
      "version": "1.0.1",
      "resolved": "https://registry.npmjs.org/es-define-property/-/es-define-property-1.0.1.tgz",
      "integrity": "sha512-e3nRfgfUZ4rNGL232gUgX06QNyyez04KdjFrF+LTRoOXmrOgFKDg4BCdsjW8EnT69eqdYGmRpJwiPVYNrCaW3g==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/es-errors": {
      "version": "1.3.0",
      "resolved": "https://registry.npmjs.org/es-errors/-/es-errors-1.3.0.tgz",
      "integrity": "sha512-Zf5H2Kxt2xjTvbJvP2ZWLEICxA6j+hAmMzIlypy4xcBg1vKVnx89Wy0GbS+kf5cwCVFFzdCFh2XSCFNULS6csw==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/es-object-atoms": {
      "version": "1.1.1",
      "resolved": "https://registry.npmjs.org/es-object-atoms/-/es-object-atoms-1.1.1.tgz",
      "integrity": "sha512-FGgH2h8zKNim9ljj7dankFPcICIK9Cp5bm+c2gQSYePhpaG5+esrLODihIorn+Pe6FGJzWhXQotPv73jTaldXA==",
      "license": "MIT",
      "dependencies": {
        "es-errors": "^1.3.0"
      },
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/escape-html": {
      "version": "1.0.3",
      "resolved": "https://registry.npmjs.org/escape-html/-/escape-html-1.0.3.tgz",
      "integrity": "sha512-NiSupZ4OeuGwr68lGIeym/ksIZMJodUGOSCZ/FSnTxcrekbvqrgdUxlJOMpijaKZVjAJrWrGs/6Jy8OMuyj9ow==",
      "license": "MIT"
    },
    "node_modules/etag": {
      "version": "1.8.1",
      "resolved": "https://registry.npmjs.org/etag/-/etag-1.8.1.tgz",
      "integrity": "sha512-aIL5Fx7mawVa300al2BnEE4iNvo1qETxLrPI/o05L7z6go7fCw1J6EQmbK4FmJ2AS7kgVF/KEZWufBfdClMcPg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/express": {
      "version": "4.22.1",
      "resolved": "https://registry.npmjs.org/express/-/express-4.22.1.tgz",
      "integrity": "sha512-F2X8g9P1X7uCPZMA3MVf9wcTqlyNp7IhH5qPCI0izhaOIYXaW9L535tGA3qmjRzpH+bZczqq7hVKxTR4NWnu+g==",
      "license": "MIT",
      "dependencies": {
        "accepts": "~1.3.8",
        "array-flatten": "1.1.1",
        "body-parser": "~1.20.3",
        "content-disposition": "~0.5.4",
        "content-type": "~1.0.4",
        "cookie": "~0.7.1",
        "cookie-signature": "~1.0.6",
        "debug": "2.6.9",
        "depd": "2.0.0",
        "encodeurl": "~2.0.0",
        "escape-html": "~1.0.3",
        "etag": "~1.8.1",
        "finalhandler": "~1.3.1",
        "fresh": "~0.5.2",
        "http-errors": "~2.0.0",
        "merge-descriptors": "1.0.3",
        "methods": "~1.1.2",
        "on-finished": "~2.4.1",
        "parseurl": "~1.3.3",
        "path-to-regexp": "~0.1.12",
        "proxy-addr": "~2.0.7",
        "qs": "~6.14.0",
        "range-parser": "~1.2.1",
        "safe-buffer": "5.2.1",
        "send": "~0.19.0",
        "serve-static": "~1.16.2",
        "setprototypeof": "1.2.0",
        "statuses": "~2.0.1",
        "type-is": "~1.6.18",
        "utils-merge": "1.0.1",
        "vary": "~1.1.2"
      },
      "engines": {
        "node": ">= 0.10.0"
      },
      "funding": {
        "type": "opencollective",
        "url": "https://opencollective.com/express"
      }
    },
    "node_modules/express-rate-limit": {
      "version": "8.5.1",
      "resolved": "https://registry.npmjs.org/express-rate-limit/-/express-rate-limit-8.5.1.tgz",
      "integrity": "sha512-5O6KYmyJEpuPJV5hNTXKbAHWRqrzyu+OI3vUnSd2kXFubIVpG7ezpgxQy76Zo5GQZtrQBg86hF+CM/NX+cioiQ==",
      "license": "MIT",
      "dependencies": {
        "ip-address": "^10.2.0"
      },
      "engines": {
        "node": ">= 16"
      },
      "funding": {
        "url": "https://github.com/sponsors/express-rate-limit"
      },
      "peerDependencies": {
        "express": ">= 4.11"
      }
    },
    "node_modules/express/node_modules/debug": {
      "version": "2.6.9",
      "resolved": "https://registry.npmjs.org/debug/-/debug-2.6.9.tgz",
      "integrity": "sha512-bC7ElrdJaJnPbAP+1EotYvqZsb3ecl5wi6Bfi6BJTUcNowp6cvspg0jXznRTKDjm/E7AdgFBVeAPVMNcKGsHMA==",
      "license": "MIT",
      "dependencies": {
        "ms": "2.0.0"
      }
    },
    "node_modules/express/node_modules/ms": {
      "version": "2.0.0",
      "resolved": "https://registry.npmjs.org/ms/-/ms-2.0.0.tgz",
      "integrity": "sha512-Tpp60P6IUJDTuOq/5Z8cdskzJujfwqfOTkrwIwj7IRISpnkJnT6SyJ4PCPnGMoFjC9ddhal5KVIYtAt97ix05A==",
      "license": "MIT"
    },
    "node_modules/fill-range": {
      "version": "7.1.1",
      "resolved": "https://registry.npmjs.org/fill-range/-/fill-range-7.1.1.tgz",
      "integrity": "sha512-YsGpe3WHLK8ZYi4tWDg2Jy3ebRz2rXowDxnld4bkQB00cc/1Zw9AWnC0i9ztDJitivtQvaI9KaLyKrc+hBW0yg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "to-regex-range": "^5.0.1"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/finalhandler": {
      "version": "1.3.2",
      "resolved": "https://registry.npmjs.org/finalhandler/-/finalhandler-1.3.2.tgz",
      "integrity": "sha512-aA4RyPcd3badbdABGDuTXCMTtOneUCAYH/gxoYRTZlIJdF0YPWuGqiAsIrhNnnqdXGswYk6dGujem4w80UJFhg==",
      "license": "MIT",
      "dependencies": {
        "debug": "2.6.9",
        "encodeurl": "~2.0.0",
        "escape-html": "~1.0.3",
        "on-finished": "~2.4.1",
        "parseurl": "~1.3.3",
        "statuses": "~2.0.2",
        "unpipe": "~1.0.0"
      },
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/finalhandler/node_modules/debug": {
      "version": "2.6.9",
      "resolved": "https://registry.npmjs.org/debug/-/debug-2.6.9.tgz",
      "integrity": "sha512-bC7ElrdJaJnPbAP+1EotYvqZsb3ecl5wi6Bfi6BJTUcNowp6cvspg0jXznRTKDjm/E7AdgFBVeAPVMNcKGsHMA==",
      "license": "MIT",
      "dependencies": {
        "ms": "2.0.0"
      }
    },
    "node_modules/finalhandler/node_modules/ms": {
      "version": "2.0.0",
      "resolved": "https://registry.npmjs.org/ms/-/ms-2.0.0.tgz",
      "integrity": "sha512-Tpp60P6IUJDTuOq/5Z8cdskzJujfwqfOTkrwIwj7IRISpnkJnT6SyJ4PCPnGMoFjC9ddhal5KVIYtAt97ix05A==",
      "license": "MIT"
    },
    "node_modules/forwarded": {
      "version": "0.2.0",
      "resolved": "https://registry.npmjs.org/forwarded/-/forwarded-0.2.0.tgz",
      "integrity": "sha512-buRG0fpBtRHSTCOASe6hD258tEubFoRLb4ZNA6NxMVHNw2gOcwHo9wyablzMzOA5z9xA9L1KNjk/Nt6MT9aYow==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/fresh": {
      "version": "0.5.2",
      "resolved": "https://registry.npmjs.org/fresh/-/fresh-0.5.2.tgz",
      "integrity": "sha512-zJ2mQYM18rEFOudeV4GShTGIQ7RbzA7ozbU9I/XBpm7kqgMywgmylMwXHxZJmkVoYkna9d2pVXVXPdYTP9ej8Q==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/fsevents": {
      "version": "2.3.3",
      "resolved": "https://registry.npmjs.org/fsevents/-/fsevents-2.3.3.tgz",
      "integrity": "sha512-5xoDfX+fL7faATnagmWPpbFtwh/R77WmMMqqHGS65C3vvB0YHrgF+B1YmZ3441tMj5n63k0212XNoJwzlhffQw==",
      "dev": true,
      "hasInstallScript": true,
      "license": "MIT",
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": "^8.16.0 || ^10.6.0 || >=11.0.0"
      }
    },
    "node_modules/function-bind": {
      "version": "1.1.2",
      "resolved": "https://registry.npmjs.org/function-bind/-/function-bind-1.1.2.tgz",
      "integrity": "sha512-7XHNxH7qX9xG5mIwxkhumTox/MIRNcOgDrxWsMt2pAr23WHp6MrRlN7FBSFpCpr+oVO0F744iUgR82nJMfG2SA==",
      "license": "MIT",
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/generate-function": {
      "version": "2.3.1",
      "resolved": "https://registry.npmjs.org/generate-function/-/generate-function-2.3.1.tgz",
      "integrity": "sha512-eeB5GfMNeevm/GRYq20ShmsaGcmI81kIX2K9XQx5miC8KdHaC6Jm0qQ8ZNeGOi7wYB8OsdxKs+Y2oVuTFuVwKQ==",
      "license": "MIT",
      "dependencies": {
        "is-property": "^1.0.2"
      }
    },
    "node_modules/get-intrinsic": {
      "version": "1.3.0",
      "resolved": "https://registry.npmjs.org/get-intrinsic/-/get-intrinsic-1.3.0.tgz",
      "integrity": "sha512-9fSjSaos/fRIVIp+xSJlE6lfwhES7LNtKaCBIamHsjr2na1BiABJPo0mOjjz8GJDURarmCPGqaiVg5mfjb98CQ==",
      "license": "MIT",
      "dependencies": {
        "call-bind-apply-helpers": "^1.0.2",
        "es-define-property": "^1.0.1",
        "es-errors": "^1.3.0",
        "es-object-atoms": "^1.1.1",
        "function-bind": "^1.1.2",
        "get-proto": "^1.0.1",
        "gopd": "^1.2.0",
        "has-symbols": "^1.1.0",
        "hasown": "^2.0.2",
        "math-intrinsics": "^1.1.0"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/get-proto": {
      "version": "1.0.1",
      "resolved": "https://registry.npmjs.org/get-proto/-/get-proto-1.0.1.tgz",
      "integrity": "sha512-sTSfBjoXBp89JvIKIefqw7U2CCebsc74kiY6awiGogKtoSGbgjYE/G/+l9sF3MWFPNc9IcoOC4ODfKHfxFmp0g==",
      "license": "MIT",
      "dependencies": {
        "dunder-proto": "^1.0.1",
        "es-object-atoms": "^1.0.0"
      },
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/glob-parent": {
      "version": "5.1.2",
      "resolved": "https://registry.npmjs.org/glob-parent/-/glob-parent-5.1.2.tgz",
      "integrity": "sha512-AOIgSQCepiJYwP3ARnGx+5VnTu2HBYdzbGP45eLw1vr3zB3vZLeyed1sC9hnbcOc9/SrMyM5RPQrkGz4aS9Zow==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "is-glob": "^4.0.1"
      },
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/gopd": {
      "version": "1.2.0",
      "resolved": "https://registry.npmjs.org/gopd/-/gopd-1.2.0.tgz",
      "integrity": "sha512-ZUKRh6/kUFoAiTAtTYPZJ3hw9wNxx+BIBOijnlG9PnrJsCcSjs1wyyD6vJpaYtgnzDrKYRSqf3OO6Rfa93xsRg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/has-flag": {
      "version": "3.0.0",
      "resolved": "https://registry.npmjs.org/has-flag/-/has-flag-3.0.0.tgz",
      "integrity": "sha512-sKJf1+ceQBr4SMkvQnBDNDtf4TXpVhVGateu0t918bl30FnbE2m4vNLX+VWe/dpjlb+HugGYzW7uQXH98HPEYw==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/has-symbols": {
      "version": "1.1.0",
      "resolved": "https://registry.npmjs.org/has-symbols/-/has-symbols-1.1.0.tgz",
      "integrity": "sha512-1cDNdwJ2Jaohmb3sg4OmKaMBwuC48sYni5HUw2DvsC8LjGTLK9h+eb1X6RyuOHe4hT0ULCW68iomhjUoKUqlPQ==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/hasown": {
      "version": "2.0.2",
      "resolved": "https://registry.npmjs.org/hasown/-/hasown-2.0.2.tgz",
      "integrity": "sha512-0hJU9SCPvmMzIBdZFqNPXWa6dqh7WdH0cII9y+CyS8rG3nL48Bclra9HmKhVVUHyPWNH5Y7xDwAB7bfgSjkUMQ==",
      "license": "MIT",
      "dependencies": {
        "function-bind": "^1.1.2"
      },
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/helmet": {
      "version": "8.1.0",
      "resolved": "https://registry.npmjs.org/helmet/-/helmet-8.1.0.tgz",
      "integrity": "sha512-jOiHyAZsmnr8LqoPGmCjYAaiuWwjAPLgY8ZX2XrmHawt99/u1y6RgrZMTeoPfpUbV96HOalYgz1qzkRbw54Pmg==",
      "license": "MIT",
      "engines": {
        "node": ">=18.0.0"
      }
    },
    "node_modules/http-errors": {
      "version": "2.0.1",
      "resolved": "https://registry.npmjs.org/http-errors/-/http-errors-2.0.1.tgz",
      "integrity": "sha512-4FbRdAX+bSdmo4AUFuS0WNiPz8NgFt+r8ThgNWmlrjQjt1Q7ZR9+zTlce2859x4KSXrwIsaeTqDoKQmtP8pLmQ==",
      "license": "MIT",
      "dependencies": {
        "depd": "~2.0.0",
        "inherits": "~2.0.4",
        "setprototypeof": "~1.2.0",
        "statuses": "~2.0.2",
        "toidentifier": "~1.0.1"
      },
      "engines": {
        "node": ">= 0.8"
      },
      "funding": {
        "type": "opencollective",
        "url": "https://opencollective.com/express"
      }
    },
    "node_modules/iconv-lite": {
      "version": "0.7.2",
      "resolved": "https://registry.npmjs.org/iconv-lite/-/iconv-lite-0.7.2.tgz",
      "integrity": "sha512-im9DjEDQ55s9fL4EYzOAv0yMqmMBSZp6G0VvFyTMPKWxiSBHUj9NW/qqLmXUwXrrM7AvqSlTCfvqRb0cM8yYqw==",
      "license": "MIT",
      "dependencies": {
        "safer-buffer": ">= 2.1.2 < 3.0.0"
      },
      "engines": {
        "node": ">=0.10.0"
      },
      "funding": {
        "type": "opencollective",
        "url": "https://opencollective.com/express"
      }
    },
    "node_modules/ignore-by-default": {
      "version": "1.0.1",
      "resolved": "https://registry.npmjs.org/ignore-by-default/-/ignore-by-default-1.0.1.tgz",
      "integrity": "sha512-Ius2VYcGNk7T90CppJqcIkS5ooHUZyIQK+ClZfMfMNFEF9VSE73Fq+906u/CWu92x4gzZMWOwfFYckPObzdEbA==",
      "dev": true,
      "license": "ISC"
    },
    "node_modules/inherits": {
      "version": "2.0.4",
      "resolved": "https://registry.npmjs.org/inherits/-/inherits-2.0.4.tgz",
      "integrity": "sha512-k/vGaX4/Yla3WzyMCvTQOXYeIHvqOKtnqBduzTHpzpQZzAskKMhZ2K+EnBiSM9zGSoIFeMpXKxa4dYeZIQqewQ==",
      "license": "ISC"
    },
    "node_modules/ip-address": {
      "version": "10.2.0",
      "resolved": "https://registry.npmjs.org/ip-address/-/ip-address-10.2.0.tgz",
      "integrity": "sha512-/+S6j4E9AHvW9SWMSEY9Xfy66O5PWvVEJ08O0y5JGyEKQpojb0K0GKpz/v5HJ/G0vi3D2sjGK78119oXZeE0qA==",
      "license": "MIT",
      "engines": {
        "node": ">= 12"
      }
    },
    "node_modules/ipaddr.js": {
      "version": "1.9.1",
      "resolved": "https://registry.npmjs.org/ipaddr.js/-/ipaddr.js-1.9.1.tgz",
      "integrity": "sha512-0KI/607xoxSToH7GjN1FfSbLoU0+btTicjsQSWQlh/hZykN8KpmMf7uYwPW3R+akZ6R/w18ZlXSHBYXiYUPO3g==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.10"
      }
    },
    "node_modules/is-binary-path": {
      "version": "2.1.0",
      "resolved": "https://registry.npmjs.org/is-binary-path/-/is-binary-path-2.1.0.tgz",
      "integrity": "sha512-ZMERYes6pDydyuGidse7OsHxtbI7WVeUEozgR/g7rd0xUimYNlvZRE/K2MgZTjWy725IfelLeVcEM97mmtRGXw==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "binary-extensions": "^2.0.0"
      },
      "engines": {
        "node": ">=8"
      }
    },
    "node_modules/is-extglob": {
      "version": "2.1.1",
      "resolved": "https://registry.npmjs.org/is-extglob/-/is-extglob-2.1.1.tgz",
      "integrity": "sha512-SbKbANkN603Vi4jEZv49LeVJMn4yGwsbzZworEoyEiutsN3nJYdbO36zfhGJ6QEDpOZIFkDtnq5JRxmvl3jsoQ==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/is-glob": {
      "version": "4.0.3",
      "resolved": "https://registry.npmjs.org/is-glob/-/is-glob-4.0.3.tgz",
      "integrity": "sha512-xelSayHH36ZgE7ZWhli7pW34hNbNl8Ojv5KVmkJD4hBdD3th8Tfk9vYasLM+mXWOZhFkgZfxhLSnrwRr4elSSg==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "is-extglob": "^2.1.1"
      },
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/is-number": {
      "version": "7.0.0",
      "resolved": "https://registry.npmjs.org/is-number/-/is-number-7.0.0.tgz",
      "integrity": "sha512-41Cifkg6e8TylSpdtTpeLVMqvSBEVzTttHvERD741+pnZ8ANv0004MRL43QKPDlK9cGvNp6NZWZUBlbGXYxxng==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.12.0"
      }
    },
    "node_modules/is-property": {
      "version": "1.0.2",
      "resolved": "https://registry.npmjs.org/is-property/-/is-property-1.0.2.tgz",
      "integrity": "sha512-Ks/IoX00TtClbGQr4TWXemAnktAQvYB7HzcCxDGqEZU6oCmb2INHuOoKxbtR+HFkmYWBKv/dOZtGRiAjDhj92g==",
      "license": "MIT"
    },
    "node_modules/jsonwebtoken": {
      "version": "9.0.3",
      "resolved": "https://registry.npmjs.org/jsonwebtoken/-/jsonwebtoken-9.0.3.tgz",
      "integrity": "sha512-MT/xP0CrubFRNLNKvxJ2BYfy53Zkm++5bX9dtuPbqAeQpTVe0MQTFhao8+Cp//EmJp244xt6Drw/GVEGCUj40g==",
      "license": "MIT",
      "dependencies": {
        "jws": "^4.0.1",
        "lodash.includes": "^4.3.0",
        "lodash.isboolean": "^3.0.3",
        "lodash.isinteger": "^4.0.4",
        "lodash.isnumber": "^3.0.3",
        "lodash.isplainobject": "^4.0.6",
        "lodash.isstring": "^4.0.1",
        "lodash.once": "^4.0.0",
        "ms": "^2.1.1",
        "semver": "^7.5.4"
      },
      "engines": {
        "node": ">=12",
        "npm": ">=6"
      }
    },
    "node_modules/jwa": {
      "version": "2.0.1",
      "resolved": "https://registry.npmjs.org/jwa/-/jwa-2.0.1.tgz",
      "integrity": "sha512-hRF04fqJIP8Abbkq5NKGN0Bbr3JxlQ+qhZufXVr0DvujKy93ZCbXZMHDL4EOtodSbCWxOqR8MS1tXA5hwqCXDg==",
      "license": "MIT",
      "dependencies": {
        "buffer-equal-constant-time": "^1.0.1",
        "ecdsa-sig-formatter": "1.0.11",
        "safe-buffer": "^5.0.1"
      }
    },
    "node_modules/jws": {
      "version": "4.0.1",
      "resolved": "https://registry.npmjs.org/jws/-/jws-4.0.1.tgz",
      "integrity": "sha512-EKI/M/yqPncGUUh44xz0PxSidXFr/+r0pA70+gIYhjv+et7yxM+s29Y+VGDkovRofQem0fs7Uvf4+YmAdyRduA==",
      "license": "MIT",
      "dependencies": {
        "jwa": "^2.0.1",
        "safe-buffer": "^5.0.1"
      }
    },
    "node_modules/lodash.includes": {
      "version": "4.3.0",
      "resolved": "https://registry.npmjs.org/lodash.includes/-/lodash.includes-4.3.0.tgz",
      "integrity": "sha512-W3Bx6mdkRTGtlJISOvVD/lbqjTlPPUDTMnlXZFnVwi9NKJ6tiAk6LVdlhZMm17VZisqhKcgzpO5Wz91PCt5b0w==",
      "license": "MIT"
    },
    "node_modules/lodash.isboolean": {
      "version": "3.0.3",
      "resolved": "https://registry.npmjs.org/lodash.isboolean/-/lodash.isboolean-3.0.3.tgz",
      "integrity": "sha512-Bz5mupy2SVbPHURB98VAcw+aHh4vRV5IPNhILUCsOzRmsTmSQ17jIuqopAentWoehktxGd9e/hbIXq980/1QJg==",
      "license": "MIT"
    },
    "node_modules/lodash.isinteger": {
      "version": "4.0.4",
      "resolved": "https://registry.npmjs.org/lodash.isinteger/-/lodash.isinteger-4.0.4.tgz",
      "integrity": "sha512-DBwtEWN2caHQ9/imiNeEA5ys1JoRtRfY3d7V9wkqtbycnAmTvRRmbHKDV4a0EYc678/dia0jrte4tjYwVBaZUA==",
      "license": "MIT"
    },
    "node_modules/lodash.isnumber": {
      "version": "3.0.3",
      "resolved": "https://registry.npmjs.org/lodash.isnumber/-/lodash.isnumber-3.0.3.tgz",
      "integrity": "sha512-QYqzpfwO3/CWf3XP+Z+tkQsfaLL/EnUlXWVkIk5FUPc4sBdTehEqZONuyRt2P67PXAk+NXmTBcc97zw9t1FQrw==",
      "license": "MIT"
    },
    "node_modules/lodash.isplainobject": {
      "version": "4.0.6",
      "resolved": "https://registry.npmjs.org/lodash.isplainobject/-/lodash.isplainobject-4.0.6.tgz",
      "integrity": "sha512-oSXzaWypCMHkPC3NvBEaPHf0KsA5mvPrOPgQWDsbg8n7orZ290M0BmC/jgRZ4vcJ6DTAhjrsSYgdsW/F+MFOBA==",
      "license": "MIT"
    },
    "node_modules/lodash.isstring": {
      "version": "4.0.1",
      "resolved": "https://registry.npmjs.org/lodash.isstring/-/lodash.isstring-4.0.1.tgz",
      "integrity": "sha512-0wJxfxH1wgO3GrbuP+dTTk7op+6L41QCXbGINEmD+ny/G/eCqGzxyCsh7159S+mgDDcoarnBw6PC1PS5+wUGgw==",
      "license": "MIT"
    },
    "node_modules/lodash.once": {
      "version": "4.1.1",
      "resolved": "https://registry.npmjs.org/lodash.once/-/lodash.once-4.1.1.tgz",
      "integrity": "sha512-Sb487aTOCr9drQVL8pIxOzVhafOjZN9UU54hiN8PU3uAiSV7lx1yYNpbNmex2PK6dSJoNTSJUUswT651yww3Mg==",
      "license": "MIT"
    },
    "node_modules/long": {
      "version": "5.3.2",
      "resolved": "https://registry.npmjs.org/long/-/long-5.3.2.tgz",
      "integrity": "sha512-mNAgZ1GmyNhD7AuqnTG3/VQ26o760+ZYBPKjPvugO8+nLbYfX6TVpJPseBvopbdY+qpZ/lKUnmEc1LeZYS3QAA==",
      "license": "Apache-2.0"
    },
    "node_modules/lru.min": {
      "version": "1.1.4",
      "resolved": "https://registry.npmjs.org/lru.min/-/lru.min-1.1.4.tgz",
      "integrity": "sha512-DqC6n3QQ77zdFpCMASA1a3Jlb64Hv2N2DciFGkO/4L9+q/IpIAuRlKOvCXabtRW6cQf8usbmM6BE/TOPysCdIA==",
      "license": "MIT",
      "engines": {
        "bun": ">=1.0.0",
        "deno": ">=1.30.0",
        "node": ">=8.0.0"
      },
      "funding": {
        "type": "github",
        "url": "https://github.com/sponsors/wellwelwel"
      }
    },
    "node_modules/math-intrinsics": {
      "version": "1.1.0",
      "resolved": "https://registry.npmjs.org/math-intrinsics/-/math-intrinsics-1.1.0.tgz",
      "integrity": "sha512-/IXtbwEk5HTPyEwyKX6hGkYXxM9nbj64B+ilVJnC/R6B0pH5G4V3b0pVbL7DBj4tkhBAppbQUlf6F6Xl9LHu1g==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      }
    },
    "node_modules/media-typer": {
      "version": "0.3.0",
      "resolved": "https://registry.npmjs.org/media-typer/-/media-typer-0.3.0.tgz",
      "integrity": "sha512-dq+qelQ9akHpcOl/gUVRTxVIOkAJ1wR3QAvb4RsVjS8oVoFjDGTc679wJYmUmknUF5HwMLOgb5O+a3KxfWapPQ==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/merge-descriptors": {
      "version": "1.0.3",
      "resolved": "https://registry.npmjs.org/merge-descriptors/-/merge-descriptors-1.0.3.tgz",
      "integrity": "sha512-gaNvAS7TZ897/rVaZ0nMtAyxNyi/pdbjbAwUpFQpN70GqnVfOiXpeUUMKRBmzXaSQ8DdTX4/0ms62r2K+hE6mQ==",
      "license": "MIT",
      "funding": {
        "url": "https://github.com/sponsors/sindresorhus"
      }
    },
    "node_modules/methods": {
      "version": "1.1.2",
      "resolved": "https://registry.npmjs.org/methods/-/methods-1.1.2.tgz",
      "integrity": "sha512-iclAHeNqNm68zFtnZ0e+1L2yUIdvzNoauKU4WBA3VvH/vPFieF7qfRlwUZU+DA9P9bPXIS90ulxoUoCH23sV2w==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/mime": {
      "version": "1.6.0",
      "resolved": "https://registry.npmjs.org/mime/-/mime-1.6.0.tgz",
      "integrity": "sha512-x0Vn8spI+wuJ1O6S7gnbaQg8Pxh4NNHb7KSINmEWKiPE4RKOplvijn+NkmYmmRgP68mc70j2EbeTFRsrswaQeg==",
      "license": "MIT",
      "bin": {
        "mime": "cli.js"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/mime-db": {
      "version": "1.52.0",
      "resolved": "https://registry.npmjs.org/mime-db/-/mime-db-1.52.0.tgz",
      "integrity": "sha512-sPU4uV7dYlvtWJxwwxHD0PuihVNiE7TyAbQ5SWxDCB9mUYvOgroQOwYQQOKPJ8CIbE+1ETVlOoK1UC2nU3gYvg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/mime-types": {
      "version": "2.1.35",
      "resolved": "https://registry.npmjs.org/mime-types/-/mime-types-2.1.35.tgz",
      "integrity": "sha512-ZDY+bPm5zTTF+YpCrAU9nK0UgICYPT0QtT1NZWFv4s++TNkcgVaT0g6+4R2uI4MjQjzysHB1zxuWL50hzaeXiw==",
      "license": "MIT",
      "dependencies": {
        "mime-db": "1.52.0"
      },
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/minimatch": {
      "version": "3.1.5",
      "resolved": "https://registry.npmjs.org/minimatch/-/minimatch-3.1.5.tgz",
      "integrity": "sha512-VgjWUsnnT6n+NUk6eZq77zeFdpW2LWDzP6zFGrCbHXiYNul5Dzqk2HHQ5uFH2DNW5Xbp8+jVzaeNt94ssEEl4w==",
      "dev": true,
      "license": "ISC",
      "dependencies": {
        "brace-expansion": "^1.1.7"
      },
      "engines": {
        "node": "*"
      }
    },
    "node_modules/ms": {
      "version": "2.1.3",
      "resolved": "https://registry.npmjs.org/ms/-/ms-2.1.3.tgz",
      "integrity": "sha512-6FlzubTLZG3J2a/NVCAleEhjzq5oxgHyaCU9yYXvcLsvoVaHJq/s5xXI6/XXP6tz7R9xAOtHnSO/tXtF3WRTlA==",
      "license": "MIT"
    },
    "node_modules/multer": {
      "version": "2.1.1",
      "resolved": "https://registry.npmjs.org/multer/-/multer-2.1.1.tgz",
      "integrity": "sha512-mo+QTzKlx8R7E5ylSXxWzGoXoZbOsRMpyitcht8By2KHvMbf3tjwosZ/Mu/XYU6UuJ3VZnODIrak5ZrPiPyB6A==",
      "license": "MIT",
      "dependencies": {
        "append-field": "^1.0.0",
        "busboy": "^1.6.0",
        "concat-stream": "^2.0.0",
        "type-is": "^1.6.18"
      },
      "engines": {
        "node": ">= 10.16.0"
      },
      "funding": {
        "type": "opencollective",
        "url": "https://opencollective.com/express"
      }
    },
    "node_modules/mysql2": {
      "version": "3.22.1",
      "resolved": "https://registry.npmjs.org/mysql2/-/mysql2-3.22.1.tgz",
      "integrity": "sha512-48+9UXehKyxxiP2pqCxUq+MSFvX+v41jwsSpFDQO/jAoFuAELutBGJUhWJnDbe82/OBlIhSBMC82WeonmznT/Q==",
      "license": "MIT",
      "dependencies": {
        "aws-ssl-profiles": "^1.1.2",
        "denque": "^2.1.0",
        "generate-function": "^2.3.1",
        "iconv-lite": "^0.7.2",
        "long": "^5.3.2",
        "lru.min": "^1.1.4",
        "named-placeholders": "^1.1.6",
        "sql-escaper": "^1.3.3"
      },
      "engines": {
        "node": ">= 8.0"
      },
      "peerDependencies": {
        "@types/node": ">= 8"
      }
    },
    "node_modules/named-placeholders": {
      "version": "1.1.6",
      "resolved": "https://registry.npmjs.org/named-placeholders/-/named-placeholders-1.1.6.tgz",
      "integrity": "sha512-Tz09sEL2EEuv5fFowm419c1+a/jSMiBjI9gHxVLrVdbUkkNUUfjsVYs9pVZu5oCon/kmRh9TfLEObFtkVxmY0w==",
      "license": "MIT",
      "dependencies": {
        "lru.min": "^1.1.0"
      },
      "engines": {
        "node": ">=8.0.0"
      }
    },
    "node_modules/negotiator": {
      "version": "0.6.3",
      "resolved": "https://registry.npmjs.org/negotiator/-/negotiator-0.6.3.tgz",
      "integrity": "sha512-+EUsqGPLsM+j/zdChZjsnX51g4XrHFOIXwfnCVPGlQk/k5giakcKsuxCObBRu6DSm9opw/O6slWbJdghQM4bBg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/node-addon-api": {
      "version": "8.5.0",
      "resolved": "https://registry.npmjs.org/node-addon-api/-/node-addon-api-8.5.0.tgz",
      "integrity": "sha512-/bRZty2mXUIFY/xU5HLvveNHlswNJej+RnxBjOMkidWfwZzgTbPG1E3K5TOxRLOR+5hX7bSofy8yf1hZevMS8A==",
      "license": "MIT",
      "engines": {
        "node": "^18 || ^20 || >= 21"
      }
    },
    "node_modules/node-gyp-build": {
      "version": "4.8.4",
      "resolved": "https://registry.npmjs.org/node-gyp-build/-/node-gyp-build-4.8.4.tgz",
      "integrity": "sha512-LA4ZjwlnUblHVgq0oBF3Jl/6h/Nvs5fzBLwdEF4nuxnFdsfajde4WfxtJr3CaiH+F6ewcIB/q4jQ4UzPyid+CQ==",
      "license": "MIT",
      "bin": {
        "node-gyp-build": "bin.js",
        "node-gyp-build-optional": "optional.js",
        "node-gyp-build-test": "build-test.js"
      }
    },
    "node_modules/nodemon": {
      "version": "3.1.11",
      "resolved": "https://registry.npmjs.org/nodemon/-/nodemon-3.1.11.tgz",
      "integrity": "sha512-is96t8F/1//UHAjNPHpbsNY46ELPpftGUoSVNXwUfMk/qdjSylYrWSu1XavVTBOn526kFiOR733ATgNBCQyH0g==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "chokidar": "^3.5.2",
        "debug": "^4",
        "ignore-by-default": "^1.0.1",
        "minimatch": "^3.1.2",
        "pstree.remy": "^1.1.8",
        "semver": "^7.5.3",
        "simple-update-notifier": "^2.0.0",
        "supports-color": "^5.5.0",
        "touch": "^3.1.0",
        "undefsafe": "^2.0.5"
      },
      "bin": {
        "nodemon": "bin/nodemon.js"
      },
      "engines": {
        "node": ">=10"
      },
      "funding": {
        "type": "opencollective",
        "url": "https://opencollective.com/nodemon"
      }
    },
    "node_modules/normalize-path": {
      "version": "3.0.0",
      "resolved": "https://registry.npmjs.org/normalize-path/-/normalize-path-3.0.0.tgz",
      "integrity": "sha512-6eZs5Ls3WtCisHWp9S2GUy8dqkpGi4BVSz3GaqiE6ezub0512ESztXUwUB6C6IKbQkY2Pnb/mD4WYojCRwcwLA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/object-assign": {
      "version": "4.1.1",
      "resolved": "https://registry.npmjs.org/object-assign/-/object-assign-4.1.1.tgz",
      "integrity": "sha512-rJgTQnkUnH1sFw8yT6VSU3zD3sWmu6sZhIseY8VX+GRu3P6F7Fu+JNDoXfklElbLJSnc3FUQHVe4cU5hj+BcUg==",
      "license": "MIT",
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/object-inspect": {
      "version": "1.13.4",
      "resolved": "https://registry.npmjs.org/object-inspect/-/object-inspect-1.13.4.tgz",
      "integrity": "sha512-W67iLl4J2EXEGTbfeHCffrjDfitvLANg0UlX3wFUUSTx92KXRFegMHUVgSqE+wvhAbi4WqjGg9czysTV2Epbew==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/on-finished": {
      "version": "2.4.1",
      "resolved": "https://registry.npmjs.org/on-finished/-/on-finished-2.4.1.tgz",
      "integrity": "sha512-oVlzkg3ENAhCk2zdv7IJwd/QUD4z2RxRwpkcGY8psCVcCYZNq4wYnVWALHM+brtuJjePWiYF/ClmuDr8Ch5+kg==",
      "license": "MIT",
      "dependencies": {
        "ee-first": "1.1.1"
      },
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/parseurl": {
      "version": "1.3.3",
      "resolved": "https://registry.npmjs.org/parseurl/-/parseurl-1.3.3.tgz",
      "integrity": "sha512-CiyeOxFT/JZyN5m0z9PfXw4SCBJ6Sygz1Dpl0wqjlhDEGGBP1GnsUVEL0p63hoG1fcj3fHynXi9NYO4nWOL+qQ==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/path-to-regexp": {
      "version": "0.1.13",
      "resolved": "https://registry.npmjs.org/path-to-regexp/-/path-to-regexp-0.1.13.tgz",
      "integrity": "sha512-A/AGNMFN3c8bOlvV9RreMdrv7jsmF9XIfDeCd87+I8RNg6s78BhJxMu69NEMHBSJFxKidViTEdruRwEk/WIKqA==",
      "license": "MIT"
    },
    "node_modules/picomatch": {
      "version": "2.3.2",
      "resolved": "https://registry.npmjs.org/picomatch/-/picomatch-2.3.2.tgz",
      "integrity": "sha512-V7+vQEJ06Z+c5tSye8S+nHUfI51xoXIXjHQ99cQtKUkQqqO1kO/KCJUfZXuB47h/YBlDhah2H3hdUGXn8ie0oA==",
      "dev": true,
      "license": "MIT",
      "engines": {
        "node": ">=8.6"
      },
      "funding": {
        "url": "https://github.com/sponsors/jonschlinkert"
      }
    },
    "node_modules/proxy-addr": {
      "version": "2.0.7",
      "resolved": "https://registry.npmjs.org/proxy-addr/-/proxy-addr-2.0.7.tgz",
      "integrity": "sha512-llQsMLSUDUPT44jdrU/O37qlnifitDP+ZwrmmZcoSKyLKvtZxpyV0n2/bD/N4tBAAZ/gJEdZU7KMraoK1+XYAg==",
      "license": "MIT",
      "dependencies": {
        "forwarded": "0.2.0",
        "ipaddr.js": "1.9.1"
      },
      "engines": {
        "node": ">= 0.10"
      }
    },
    "node_modules/pstree.remy": {
      "version": "1.1.8",
      "resolved": "https://registry.npmjs.org/pstree.remy/-/pstree.remy-1.1.8.tgz",
      "integrity": "sha512-77DZwxQmxKnu3aR542U+X8FypNzbfJ+C5XQDk3uWjWxn6151aIMGthWYRXTqT1E5oJvg+ljaa2OJi+VfvCOQ8w==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/qs": {
      "version": "6.14.2",
      "resolved": "https://registry.npmjs.org/qs/-/qs-6.14.2.tgz",
      "integrity": "sha512-V/yCWTTF7VJ9hIh18Ugr2zhJMP01MY7c5kh4J870L7imm6/DIzBsNLTXzMwUA3yZ5b/KBqLx8Kp3uRvd7xSe3Q==",
      "license": "BSD-3-Clause",
      "dependencies": {
        "side-channel": "^1.1.0"
      },
      "engines": {
        "node": ">=0.6"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/range-parser": {
      "version": "1.2.1",
      "resolved": "https://registry.npmjs.org/range-parser/-/range-parser-1.2.1.tgz",
      "integrity": "sha512-Hrgsx+orqoygnmhFbKaHE6c296J+HTAQXoxEF6gNupROmmGJRoyzfG3ccAveqCBrwr/2yxQ5BVd/GTl5agOwSg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/raw-body": {
      "version": "2.5.3",
      "resolved": "https://registry.npmjs.org/raw-body/-/raw-body-2.5.3.tgz",
      "integrity": "sha512-s4VSOf6yN0rvbRZGxs8Om5CWj6seneMwK3oDb4lWDH0UPhWcxwOWw5+qk24bxq87szX1ydrwylIOp2uG1ojUpA==",
      "license": "MIT",
      "dependencies": {
        "bytes": "~3.1.2",
        "http-errors": "~2.0.1",
        "iconv-lite": "~0.4.24",
        "unpipe": "~1.0.0"
      },
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/raw-body/node_modules/iconv-lite": {
      "version": "0.4.24",
      "resolved": "https://registry.npmjs.org/iconv-lite/-/iconv-lite-0.4.24.tgz",
      "integrity": "sha512-v3MXnZAcvnywkTUEZomIActle7RXXeedOR31wwl7VlyoXO4Qi9arvSenNQWne1TcRwhCL1HwLI21bEqdpj8/rA==",
      "license": "MIT",
      "dependencies": {
        "safer-buffer": ">= 2.1.2 < 3"
      },
      "engines": {
        "node": ">=0.10.0"
      }
    },
    "node_modules/readable-stream": {
      "version": "3.6.2",
      "resolved": "https://registry.npmjs.org/readable-stream/-/readable-stream-3.6.2.tgz",
      "integrity": "sha512-9u/sniCrY3D5WdsERHzHE4G2YCXqoG5FTHUiCC4SIbr6XcLZBY05ya9EKjYek9O5xOAwjGq+1JdGBAS7Q9ScoA==",
      "license": "MIT",
      "dependencies": {
        "inherits": "^2.0.3",
        "string_decoder": "^1.1.1",
        "util-deprecate": "^1.0.1"
      },
      "engines": {
        "node": ">= 6"
      }
    },
    "node_modules/readdirp": {
      "version": "3.6.0",
      "resolved": "https://registry.npmjs.org/readdirp/-/readdirp-3.6.0.tgz",
      "integrity": "sha512-hOS089on8RduqdbhvQ5Z37A0ESjsqz6qnRcffsMU3495FuTdqSm+7bhJ29JvIOsBDEEnan5DPu9t3To9VRlMzA==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "picomatch": "^2.2.1"
      },
      "engines": {
        "node": ">=8.10.0"
      }
    },
    "node_modules/safe-buffer": {
      "version": "5.2.1",
      "resolved": "https://registry.npmjs.org/safe-buffer/-/safe-buffer-5.2.1.tgz",
      "integrity": "sha512-rp3So07KcdmmKbGvgaNxQSJr7bGVSVk5S9Eq1F+ppbRo70+YeaDxkw5Dd8NPN+GD6bjnYm2VuPuCXmpuYvmCXQ==",
      "funding": [
        {
          "type": "github",
          "url": "https://github.com/sponsors/feross"
        },
        {
          "type": "patreon",
          "url": "https://www.patreon.com/feross"
        },
        {
          "type": "consulting",
          "url": "https://feross.org/support"
        }
      ],
      "license": "MIT"
    },
    "node_modules/safer-buffer": {
      "version": "2.1.2",
      "resolved": "https://registry.npmjs.org/safer-buffer/-/safer-buffer-2.1.2.tgz",
      "integrity": "sha512-YZo3K82SD7Riyi0E1EQPojLz7kpepnSQI9IyPbHHg1XXXevb5dJI7tpyN2ADxGcQbHG7vcyRHk0cbwqcQriUtg==",
      "license": "MIT"
    },
    "node_modules/semver": {
      "version": "7.7.3",
      "resolved": "https://registry.npmjs.org/semver/-/semver-7.7.3.tgz",
      "integrity": "sha512-SdsKMrI9TdgjdweUSR9MweHA4EJ8YxHn8DFaDisvhVlUOe4BF1tLD7GAj0lIqWVl+dPb/rExr0Btby5loQm20Q==",
      "license": "ISC",
      "bin": {
        "semver": "bin/semver.js"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/send": {
      "version": "0.19.1",
      "resolved": "https://registry.npmjs.org/send/-/send-0.19.1.tgz",
      "integrity": "sha512-p4rRk4f23ynFEfcD9LA0xRYngj+IyGiEYyqqOak8kaN0TvNmuxC2dcVeBn62GpCeR2CpWqyHCNScTP91QbAVFg==",
      "license": "MIT",
      "dependencies": {
        "debug": "2.6.9",
        "depd": "2.0.0",
        "destroy": "1.2.0",
        "encodeurl": "~2.0.0",
        "escape-html": "~1.0.3",
        "etag": "~1.8.1",
        "fresh": "0.5.2",
        "http-errors": "2.0.0",
        "mime": "1.6.0",
        "ms": "2.1.3",
        "on-finished": "2.4.1",
        "range-parser": "~1.2.1",
        "statuses": "2.0.1"
      },
      "engines": {
        "node": ">= 0.8.0"
      }
    },
    "node_modules/send/node_modules/debug": {
      "version": "2.6.9",
      "resolved": "https://registry.npmjs.org/debug/-/debug-2.6.9.tgz",
      "integrity": "sha512-bC7ElrdJaJnPbAP+1EotYvqZsb3ecl5wi6Bfi6BJTUcNowp6cvspg0jXznRTKDjm/E7AdgFBVeAPVMNcKGsHMA==",
      "license": "MIT",
      "dependencies": {
        "ms": "2.0.0"
      }
    },
    "node_modules/send/node_modules/debug/node_modules/ms": {
      "version": "2.0.0",
      "resolved": "https://registry.npmjs.org/ms/-/ms-2.0.0.tgz",
      "integrity": "sha512-Tpp60P6IUJDTuOq/5Z8cdskzJujfwqfOTkrwIwj7IRISpnkJnT6SyJ4PCPnGMoFjC9ddhal5KVIYtAt97ix05A==",
      "license": "MIT"
    },
    "node_modules/send/node_modules/http-errors": {
      "version": "2.0.0",
      "resolved": "https://registry.npmjs.org/http-errors/-/http-errors-2.0.0.tgz",
      "integrity": "sha512-FtwrG/euBzaEjYeRqOgly7G0qviiXoJWnvEH2Z1plBdXgbyjv34pHTSb9zoeHMyDy33+DWy5Wt9Wo+TURtOYSQ==",
      "license": "MIT",
      "dependencies": {
        "depd": "2.0.0",
        "inherits": "2.0.4",
        "setprototypeof": "1.2.0",
        "statuses": "2.0.1",
        "toidentifier": "1.0.1"
      },
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/send/node_modules/statuses": {
      "version": "2.0.1",
      "resolved": "https://registry.npmjs.org/statuses/-/statuses-2.0.1.tgz",
      "integrity": "sha512-RwNA9Z/7PrK06rYLIzFMlaF+l73iwpzsqRIFgbMLbTcLD6cOao82TaWefPXQvB2fOC4AjuYSEndS7N/mTCbkdQ==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/serve-static": {
      "version": "1.16.2",
      "resolved": "https://registry.npmjs.org/serve-static/-/serve-static-1.16.2.tgz",
      "integrity": "sha512-VqpjJZKadQB/PEbEwvFdO43Ax5dFBZ2UECszz8bQ7pi7wt//PWe1P6MN7eCnjsatYtBT6EuiClbjSWP2WrIoTw==",
      "license": "MIT",
      "dependencies": {
        "encodeurl": "~2.0.0",
        "escape-html": "~1.0.3",
        "parseurl": "~1.3.3",
        "send": "0.19.0"
      },
      "engines": {
        "node": ">= 0.8.0"
      }
    },
    "node_modules/serve-static/node_modules/debug": {
      "version": "2.6.9",
      "resolved": "https://registry.npmjs.org/debug/-/debug-2.6.9.tgz",
      "integrity": "sha512-bC7ElrdJaJnPbAP+1EotYvqZsb3ecl5wi6Bfi6BJTUcNowp6cvspg0jXznRTKDjm/E7AdgFBVeAPVMNcKGsHMA==",
      "license": "MIT",
      "dependencies": {
        "ms": "2.0.0"
      }
    },
    "node_modules/serve-static/node_modules/debug/node_modules/ms": {
      "version": "2.0.0",
      "resolved": "https://registry.npmjs.org/ms/-/ms-2.0.0.tgz",
      "integrity": "sha512-Tpp60P6IUJDTuOq/5Z8cdskzJujfwqfOTkrwIwj7IRISpnkJnT6SyJ4PCPnGMoFjC9ddhal5KVIYtAt97ix05A==",
      "license": "MIT"
    },
    "node_modules/serve-static/node_modules/http-errors": {
      "version": "2.0.0",
      "resolved": "https://registry.npmjs.org/http-errors/-/http-errors-2.0.0.tgz",
      "integrity": "sha512-FtwrG/euBzaEjYeRqOgly7G0qviiXoJWnvEH2Z1plBdXgbyjv34pHTSb9zoeHMyDy33+DWy5Wt9Wo+TURtOYSQ==",
      "license": "MIT",
      "dependencies": {
        "depd": "2.0.0",
        "inherits": "2.0.4",
        "setprototypeof": "1.2.0",
        "statuses": "2.0.1",
        "toidentifier": "1.0.1"
      },
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/serve-static/node_modules/send": {
      "version": "0.19.0",
      "resolved": "https://registry.npmjs.org/send/-/send-0.19.0.tgz",
      "integrity": "sha512-dW41u5VfLXu8SJh5bwRmyYUbAoSB3c9uQh6L8h/KtsFREPWpbX1lrljJo186Jc4nmci/sGUZ9a0a0J2zgfq2hw==",
      "license": "MIT",
      "dependencies": {
        "debug": "2.6.9",
        "depd": "2.0.0",
        "destroy": "1.2.0",
        "encodeurl": "~1.0.2",
        "escape-html": "~1.0.3",
        "etag": "~1.8.1",
        "fresh": "0.5.2",
        "http-errors": "2.0.0",
        "mime": "1.6.0",
        "ms": "2.1.3",
        "on-finished": "2.4.1",
        "range-parser": "~1.2.1",
        "statuses": "2.0.1"
      },
      "engines": {
        "node": ">= 0.8.0"
      }
    },
    "node_modules/serve-static/node_modules/send/node_modules/encodeurl": {
      "version": "1.0.2",
      "resolved": "https://registry.npmjs.org/encodeurl/-/encodeurl-1.0.2.tgz",
      "integrity": "sha512-TPJXq8JqFaVYm2CWmPvnP2Iyo4ZSM7/QKcSmuMLDObfpH5fi7RUGmd/rTDf+rut/saiDiQEeVTNgAmJEdAOx0w==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/serve-static/node_modules/statuses": {
      "version": "2.0.1",
      "resolved": "https://registry.npmjs.org/statuses/-/statuses-2.0.1.tgz",
      "integrity": "sha512-RwNA9Z/7PrK06rYLIzFMlaF+l73iwpzsqRIFgbMLbTcLD6cOao82TaWefPXQvB2fOC4AjuYSEndS7N/mTCbkdQ==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/setprototypeof": {
      "version": "1.2.0",
      "resolved": "https://registry.npmjs.org/setprototypeof/-/setprototypeof-1.2.0.tgz",
      "integrity": "sha512-E5LDX7Wrp85Kil5bhZv46j8jOeboKq5JMmYM3gVGdGH8xFpPWXUMsNrlODCrkoxMEeNi/XZIwuRvY4XNwYMJpw==",
      "license": "ISC"
    },
    "node_modules/side-channel": {
      "version": "1.1.0",
      "resolved": "https://registry.npmjs.org/side-channel/-/side-channel-1.1.0.tgz",
      "integrity": "sha512-ZX99e6tRweoUXqR+VBrslhda51Nh5MTQwou5tnUDgbtyM0dBgmhEDtWGP/xbKn6hqfPRHujUNwz5fy/wbbhnpw==",
      "license": "MIT",
      "dependencies": {
        "es-errors": "^1.3.0",
        "object-inspect": "^1.13.3",
        "side-channel-list": "^1.0.0",
        "side-channel-map": "^1.0.1",
        "side-channel-weakmap": "^1.0.2"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/side-channel-list": {
      "version": "1.0.0",
      "resolved": "https://registry.npmjs.org/side-channel-list/-/side-channel-list-1.0.0.tgz",
      "integrity": "sha512-FCLHtRD/gnpCiCHEiJLOwdmFP+wzCmDEkc9y7NsYxeF4u7Btsn1ZuwgwJGxImImHicJArLP4R0yX4c2KCrMrTA==",
      "license": "MIT",
      "dependencies": {
        "es-errors": "^1.3.0",
        "object-inspect": "^1.13.3"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/side-channel-map": {
      "version": "1.0.1",
      "resolved": "https://registry.npmjs.org/side-channel-map/-/side-channel-map-1.0.1.tgz",
      "integrity": "sha512-VCjCNfgMsby3tTdo02nbjtM/ewra6jPHmpThenkTYh8pG9ucZ/1P8So4u4FGBek/BjpOVsDCMoLA/iuBKIFXRA==",
      "license": "MIT",
      "dependencies": {
        "call-bound": "^1.0.2",
        "es-errors": "^1.3.0",
        "get-intrinsic": "^1.2.5",
        "object-inspect": "^1.13.3"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/side-channel-weakmap": {
      "version": "1.0.2",
      "resolved": "https://registry.npmjs.org/side-channel-weakmap/-/side-channel-weakmap-1.0.2.tgz",
      "integrity": "sha512-WPS/HvHQTYnHisLo9McqBHOJk2FkHO/tlpvldyrnem4aeQp4hai3gythswg6p01oSoTl58rcpiFAjF2br2Ak2A==",
      "license": "MIT",
      "dependencies": {
        "call-bound": "^1.0.2",
        "es-errors": "^1.3.0",
        "get-intrinsic": "^1.2.5",
        "object-inspect": "^1.13.3",
        "side-channel-map": "^1.0.1"
      },
      "engines": {
        "node": ">= 0.4"
      },
      "funding": {
        "url": "https://github.com/sponsors/ljharb"
      }
    },
    "node_modules/simple-update-notifier": {
      "version": "2.0.0",
      "resolved": "https://registry.npmjs.org/simple-update-notifier/-/simple-update-notifier-2.0.0.tgz",
      "integrity": "sha512-a2B9Y0KlNXl9u/vsW6sTIu9vGEpfKu2wRV6l1H3XEas/0gUIzGzBoP/IouTcUQbm9JWZLH3COxyn03TYlFax6w==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "semver": "^7.5.3"
      },
      "engines": {
        "node": ">=10"
      }
    },
    "node_modules/sql-escaper": {
      "version": "1.3.3",
      "resolved": "https://registry.npmjs.org/sql-escaper/-/sql-escaper-1.3.3.tgz",
      "integrity": "sha512-BsTCV265VpTp8tm1wyIm1xqQCS+Q9NHx2Sr+WcnUrgLrQ6yiDIvHYJV5gHxsj1lMBy2zm5twLaZao8Jd+S8JJw==",
      "license": "MIT",
      "engines": {
        "bun": ">=1.0.0",
        "deno": ">=2.0.0",
        "node": ">=12.0.0"
      },
      "funding": {
        "type": "github",
        "url": "https://github.com/mysqljs/sql-escaper?sponsor=1"
      }
    },
    "node_modules/statuses": {
      "version": "2.0.2",
      "resolved": "https://registry.npmjs.org/statuses/-/statuses-2.0.2.tgz",
      "integrity": "sha512-DvEy55V3DB7uknRo+4iOGT5fP1slR8wQohVdknigZPMpMstaKJQWhwiYBACJE3Ul2pTnATihhBYnRhZQHGBiRw==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/streamsearch": {
      "version": "1.1.0",
      "resolved": "https://registry.npmjs.org/streamsearch/-/streamsearch-1.1.0.tgz",
      "integrity": "sha512-Mcc5wHehp9aXz1ax6bZUyY5afg9u2rv5cqQI3mRrYkGC8rW2hM02jWuwjtL++LS5qinSyhj2QfLyNsuc+VsExg==",
      "engines": {
        "node": ">=10.0.0"
      }
    },
    "node_modules/string_decoder": {
      "version": "1.3.0",
      "resolved": "https://registry.npmjs.org/string_decoder/-/string_decoder-1.3.0.tgz",
      "integrity": "sha512-hkRX8U1WjJFd8LsDJ2yQ/wWWxaopEsABU1XfkM8A+j0+85JAGppt16cr1Whg6KIbb4okU6Mql6BOj+uup/wKeA==",
      "license": "MIT",
      "dependencies": {
        "safe-buffer": "~5.2.0"
      }
    },
    "node_modules/supports-color": {
      "version": "5.5.0",
      "resolved": "https://registry.npmjs.org/supports-color/-/supports-color-5.5.0.tgz",
      "integrity": "sha512-QjVjwdXIt408MIiAqCX4oUKsgU2EqAGzs2Ppkm4aQYbjm+ZEWEcW4SfFNTr4uMNZma0ey4f5lgLrkB0aX0QMow==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "has-flag": "^3.0.0"
      },
      "engines": {
        "node": ">=4"
      }
    },
    "node_modules/to-regex-range": {
      "version": "5.0.1",
      "resolved": "https://registry.npmjs.org/to-regex-range/-/to-regex-range-5.0.1.tgz",
      "integrity": "sha512-65P7iz6X5yEr1cwcgvQxbbIw7Uk3gOy5dIdtZ4rDveLqhrdJP+Li/Hx6tyK0NEb+2GCyneCMJiGqrADCSNk8sQ==",
      "dev": true,
      "license": "MIT",
      "dependencies": {
        "is-number": "^7.0.0"
      },
      "engines": {
        "node": ">=8.0"
      }
    },
    "node_modules/toidentifier": {
      "version": "1.0.1",
      "resolved": "https://registry.npmjs.org/toidentifier/-/toidentifier-1.0.1.tgz",
      "integrity": "sha512-o5sSPKEkg/DIQNmH43V0/uerLrpzVedkUh8tGNvaeXpfpuwjKenlSox/2O/BTlZUtEe+JG7s5YhEz608PlAHRA==",
      "license": "MIT",
      "engines": {
        "node": ">=0.6"
      }
    },
    "node_modules/touch": {
      "version": "3.1.1",
      "resolved": "https://registry.npmjs.org/touch/-/touch-3.1.1.tgz",
      "integrity": "sha512-r0eojU4bI8MnHr8c5bNo7lJDdI2qXlWWJk6a9EAFG7vbhTjElYhBVS3/miuE0uOuoLdb8Mc/rVfsmm6eo5o9GA==",
      "dev": true,
      "license": "ISC",
      "bin": {
        "nodetouch": "bin/nodetouch.js"
      }
    },
    "node_modules/type-is": {
      "version": "1.6.18",
      "resolved": "https://registry.npmjs.org/type-is/-/type-is-1.6.18.tgz",
      "integrity": "sha512-TkRKr9sUTxEH8MdfuCSP7VizJyzRNMjj2J2do2Jr3Kym598JVdEksuzPQCnlFPW4ky9Q+iA+ma9BGm06XQBy8g==",
      "license": "MIT",
      "dependencies": {
        "media-typer": "0.3.0",
        "mime-types": "~2.1.24"
      },
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/typedarray": {
      "version": "0.0.6",
      "resolved": "https://registry.npmjs.org/typedarray/-/typedarray-0.0.6.tgz",
      "integrity": "sha512-/aCDEGatGvZ2BIk+HmLf4ifCJFwvKFNb9/JeZPMulfgFracn9QFcAf5GO8B/mweUjSoblS5In0cWhqpfs/5PQA==",
      "license": "MIT"
    },
    "node_modules/undefsafe": {
      "version": "2.0.5",
      "resolved": "https://registry.npmjs.org/undefsafe/-/undefsafe-2.0.5.tgz",
      "integrity": "sha512-WxONCrssBM8TSPRqN5EmsjVrsv4A8X12J4ArBiiayv3DyyG3ZlIg6yysuuSYdZsVz3TKcTg2fd//Ujd4CHV1iA==",
      "dev": true,
      "license": "MIT"
    },
    "node_modules/undici-types": {
      "version": "7.19.2",
      "resolved": "https://registry.npmjs.org/undici-types/-/undici-types-7.19.2.tgz",
      "integrity": "sha512-qYVnV5OEm2AW8cJMCpdV20CDyaN3g0AjDlOGf1OW4iaDEx8MwdtChUp4zu4H0VP3nDRF/8RKWH+IPp9uW0YGZg==",
      "license": "MIT",
      "peer": true
    },
    "node_modules/unpipe": {
      "version": "1.0.0",
      "resolved": "https://registry.npmjs.org/unpipe/-/unpipe-1.0.0.tgz",
      "integrity": "sha512-pjy2bYhSsufwWlKwPc+l3cN7+wuJlK6uz0YdJEOlQDbl6jo/YlPi4mb8agUkVC8BF7V8NuzeyPNqRksA3hztKQ==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/util-deprecate": {
      "version": "1.0.2",
      "resolved": "https://registry.npmjs.org/util-deprecate/-/util-deprecate-1.0.2.tgz",
      "integrity": "sha512-EPD5q1uXyFxJpCrLnCc1nHnq3gOa6DZBocAIiI2TaSCA7VCJ1UJDMagCzIkXNsUYfD1daK//LTEQ8xiIbrHtcw==",
      "license": "MIT"
    },
    "node_modules/utils-merge": {
      "version": "1.0.1",
      "resolved": "https://registry.npmjs.org/utils-merge/-/utils-merge-1.0.1.tgz",
      "integrity": "sha512-pMZTvIkT1d+TFGvDOqodOclx0QWkkgi6Tdoa8gC8ffGAAqz9pzPTZWAybbsHHoED/ztMtkv/VoYTYyShUn81hA==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.4.0"
      }
    },
    "node_modules/vary": {
      "version": "1.1.2",
      "resolved": "https://registry.npmjs.org/vary/-/vary-1.1.2.tgz",
      "integrity": "sha512-BNGbWLfd0eUPabhkXUVm0j8uuvREyTh5ovRa/dyow/BqAbZJyC+5fU+IzQOzmAKzYqYRAISoRhdQr3eIZ/PXqg==",
      "license": "MIT",
      "engines": {
        "node": ">= 0.8"
      }
    },
    "node_modules/ws": {
      "version": "8.18.3",
      "resolved": "https://registry.npmjs.org/ws/-/ws-8.18.3.tgz",
      "integrity": "sha512-PEIGCY5tSlUt50cqyMXfCzX+oOPqN0vuGqWzbcJ2xvnkzkq46oOpz7dQaTDBdfICb4N14+GARUDw2XV2N4tvzg==",
      "license": "MIT",
      "engines": {
        "node": ">=10.0.0"
      },
      "peerDependencies": {
        "bufferutil": "^4.0.1",
        "utf-8-validate": ">=5.0.2"
      },
      "peerDependenciesMeta": {
        "bufferutil": {
          "optional": true
        },
        "utf-8-validate": {
          "optional": true
        }
      }
    }
  }
}
{
  "name": "construction-safety",
  "version": "1.0.0",
  "description": "Construction Site Safety Management System with RTSP CCTV Streaming",
  "main": "backend/server.js",
  "scripts": {
    "start": "node backend/server.js",
    "dev": "nodemon backend/server.js"
  },
  "keywords": [
    "construction",
    "safety",
    "mysql",
    "cctv",
    "rtsp",
    "streaming"
  ],
  "author": "Your Name",
  "license": "ISC",
  "dependencies": {
    "bcrypt": "^6.0.0",
    "body-parser": "^1.20.4",
    "cookie-parser": "^1.4.7",
    "cors": "^2.8.5",
    "dotenv": "^16.6.1",
    "express": "^4.22.1",
    "express-rate-limit": "^8.5.1",
    "helmet": "^8.1.0",
    "jsonwebtoken": "^9.0.3",
    "multer": "^2.0.2",
    "mysql2": "^3.22.1",
    "ws": "^8.14.2"
  },
  "devDependencies": {
    "nodemon": "^3.0.2"
  }
}

// File: backend/config/database.js
const mysql = require('mysql2');
require('dotenv').config({ path: __dirname + '/.env' });

const pool = mysql.createPool({
    host: process.env.DB_HOST || '127.0.0.1',
      port: process.env.DB_PORT || 3306,
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASSWORD || '',
    database: process.env.DB_NAME || 'construction_safety',
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0
});

// Create promise pool
const promisePool = pool.promise();

// Test connection
pool.getConnection((err, connection) => {
    if (err) {
        console.error('❌ Database connection failed:', err.message);
    } else {
        console.log('✅ Database connected successfully!');
        connection.release();
    }
});

// IMPORTANT: Export the promise pool, not the regular pool
module.exports = promisePool;
const multer = require('multer');
const path = require('path');
const fs = require('fs');

// Create uploads directory if it doesn't exist
const uploadDir = path.join(__dirname, '../../uploads/workers');
if (!fs.existsSync(uploadDir)) {
    fs.mkdirSync(uploadDir, { recursive: true });
}

// Configure storage
const storage = multer.diskStorage({
    destination: function (req, file, cb) {
        cb(null, uploadDir);
    },
    filename: function (req, file, cb) {
        // Generate unique filename: workerId_timestamp.extension
        const workerId = req.body.worker_id || 'temp';
        const extension = path.extname(file.originalname);
        const filename = `${workerId}_${Date.now()}${extension}`;
        cb(null, filename);
    }
});

// File filter to accept only images
const fileFilter = (req, file, cb) => {
    const allowedTypes = /jpeg|jpg|png|gif/;
    const extname = allowedTypes.test(path.extname(file.originalname).toLowerCase());
    const mimetype = allowedTypes.test(file.mimetype);

    if (mimetype && extname) {
        return cb(null, true);
    } else {
        cb(new Error('Only image files (jpeg, jpg, png, gif) are allowed!'));
    }
};

// Configure multer
const upload = multer({
    storage: storage,
    limits: {
        fileSize: 5 * 1024 * 1024 // 5MB limit
    },
    fileFilter: fileFilter
});

module.exports = upload;


