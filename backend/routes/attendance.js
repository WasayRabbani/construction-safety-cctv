// File: backend/routes/attendance.js
const express = require('express');
const router = express.Router();
const db = require('../config/database');
const { authenticateToken } = require('../middleware/auth');

// Get attendance for a specific date (Rule 1 & 2)
router.get('/date/:date', authenticateToken, async (req, res) => {
    try {
        const targetDate = req.params.date;
        const [rows] = await db.query(`
            SELECT a.*, w.name, w.photo_path
            FROM attendance a
            JOIN workers w ON a.worker_id = w.worker_id
            WHERE date(a.check_in_time) = ?
            ORDER BY a.check_in_time ASC
        `, [targetDate]);

        res.json(rows);
    } catch (error) {
        console.error('Error fetching attendance:', error);
        res.status(500).json({ error: 'Failed to retrieve attendance records' });
    }
});

// Get today's attendance stats
router.get('/stats/today', authenticateToken, async (req, res) => {
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
            WHERE date(check_in_time) = date('now', 'localtime')
        `);

        res.json(stats[0] || {});
    } catch (error) {
        console.error('Error fetching attendance stats:', error);
        res.status(500).json({ error: 'Failed to retrieve attendance statistics' });
    }
});

// Check in worker
router.post('/checkin', async (req, res) => {
    try {
        const { worker_id, location } = req.body;
        if (!worker_id) {
            return res.status(400).json({ error: 'worker_id is required' });
        }

        const now = new Date();
        const check_in_time = now.toISOString().replace('T', ' ').slice(0, 19);
        const attendance_date = now.toISOString().slice(0, 10);

        // Determine if late (after 8:30 AM)
        const hour = now.getHours();
        const minute = now.getMinutes();
        const status = (hour > 8 || (hour === 8 && minute > 30)) ? 'late' : 'present';

        const [result] = await db.query(
            `INSERT INTO attendance (worker_id, check_in_time, status, location, attendance_date)
             VALUES (?, ?, ?, ?, ?)`,
            [worker_id, check_in_time, status, location || 'Main Gate', attendance_date]
        );

        res.status(201).json({ 
            message: 'Check-in successful', 
            attendance_id: result.insertId,
            status: status
        });
    } catch (error) {
        console.error('Error checking in:', error);
        res.status(500).json({ error: 'Failed to record check-in' });
    }
});

// Check out worker
router.put('/checkout/:attendance_id', async (req, res) => {
    try {
        const attendance_id = req.params.attendance_id;

        const [existing] = await db.query(
            'SELECT check_in_time FROM attendance WHERE attendance_id = ?',
            [attendance_id]
        );

        if (existing.length === 0) {
            return res.status(404).json({ error: 'Attendance record not found' });
        }

        const now = new Date();
        const check_out_time = now.toISOString().replace('T', ' ').slice(0, 19);

        // Calculate working hours in JS (database-agnostic)
        const checkInDate = new Date(existing[0].check_in_time);
        const diffMs = now - checkInDate;
        const working_hours = Math.max(0, parseFloat((diffMs / (1000 * 60 * 60)).toFixed(2)));

        const [result] = await db.query(
            `UPDATE attendance 
             SET check_out_time = ?,
                 working_hours = ?
             WHERE attendance_id = ?`,
            [check_out_time, working_hours, attendance_id]
        );

        res.json({ message: 'Check-out successful', working_hours });
    } catch (error) {
        console.error('Error checking out:', error);
        res.status(500).json({ error: 'Failed to record check-out' });
    }
});

// Get attendance by worker (Rule 3: Data Ownership)
router.get('/worker/:worker_id', authenticateToken, async (req, res) => {
    try {
        const targetWorkerId = req.params.worker_id;

        // Workers can only view their own attendance
        if (req.user.role === 'worker' && req.user.username !== targetWorkerId) {
            return res.status(403).json({ error: 'Forbidden. You can only view your own attendance.' });
        }

        const [rows] = await db.query(`
            SELECT * FROM attendance 
            WHERE worker_id = ?
            ORDER BY check_in_time DESC
            LIMIT 30
        `, [targetWorkerId]);

        res.json(rows);
    } catch (error) {
        console.error('Error fetching worker attendance:', error);
        res.status(500).json({ error: 'Failed to retrieve worker attendance' });
    }
});

module.exports = router;
