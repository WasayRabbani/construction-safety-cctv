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
