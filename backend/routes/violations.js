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