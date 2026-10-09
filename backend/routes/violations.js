// File: backend/routes/violations.js
const express = require('express');
const router = express.Router();
const db = require('../config/database');
const { authenticateToken, authorizeRoles } = require('../middleware/auth');

// Get all violations with filters and pagination (Rules 8 & 9)
router.get('/', authenticateToken, async (req, res) => {
    try {
        const { date_from, date_to, violation_type, severity, camera_id, worker_id } = req.query;
        const limit = Math.min(Math.max(parseInt(req.query.limit) || 50, 1), 100);
        const offset = Math.max(parseInt(req.query.offset) || 0, 0);

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

        query += ' ORDER BY v.timestamp DESC LIMIT ? OFFSET ?';
        params.push(limit, offset);

        const [rows] = await db.query(query, params);
        res.json(rows);
    } catch (error) {
        console.error('Error fetching violations:', error);
        res.status(500).json({ error: 'Failed to retrieve violations' });
    }
});

// Get violation stats
router.get('/stats/summary', authenticateToken, async (req, res) => {
    try {
        const [today] = await db.query(`
            SELECT COUNT(*) as today_count
            FROM violations
            WHERE DATE(timestamp) = date('now', 'localtime')
        `);

        const [week] = await db.query(`
            SELECT COUNT(*) as week_count
            FROM violations
            WHERE timestamp >= datetime('now', 'localtime', '-7 days')
        `);

        const [pending] = await db.query(`
            SELECT COUNT(*) as pending_count
            FROM violations
            WHERE status = 'pending'
        `);

        res.json({
            today: today[0]?.today_count || 0,
            week: week[0]?.week_count || 0,
            pending: pending[0]?.pending_count || 0
        });
    } catch (error) {
        console.error('Error fetching violation stats:', error);
        res.status(500).json({ error: 'Failed to retrieve violation statistics' });
    }
});

// Create new violation (Can be called by Python AI service or admin)
router.post('/', async (req, res) => {
    try {
        let { violation_id, worker_id, violation_type, severity, camera_id, fine_amount, snapshot_path } = req.body;

        // Rule 4: Validate inputs
        if (!violation_type) {
            return res.status(400).json({ error: 'violation_type is required' });
        }

        // Auto-generate violation_id if not supplied by caller
        if (!violation_id) {
            violation_id = `V${Date.now()}`;
        }

        // Default severity and fine
        const validSeverities = ['low', 'medium', 'high'];
        severity = validSeverities.includes(severity) ? severity : 'medium';
        fine_amount = parseFloat(fine_amount) || 0;

        await db.query(
            `INSERT INTO violations (violation_id, timestamp, worker_id, violation_type, severity, camera_id, fine_amount, snapshot_path, status)
             VALUES (?, datetime('now', 'localtime'), ?, ?, ?, ?, ?, ?, 'pending')`,
            [violation_id, worker_id || null, violation_type, severity, camera_id || null, fine_amount, snapshot_path || null]
        );

        res.status(201).json({
            success: true,
            message: 'Violation recorded successfully',
            violation_id
        });
    } catch (error) {
        console.error('Error creating violation:', error);
        res.status(500).json({ error: 'Failed to record violation' });
    }
});

// Resolve violation (Restricted to Admin / Supervisor / Safety Officer)
router.put('/:id/resolve', authenticateToken, authorizeRoles('admin', 'supervisor', 'safety officer'), async (req, res) => {
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
        res.status(500).json({ error: 'Failed to resolve violation' });
    }
});

// Get violations by worker (Rule 3: Access Control)
router.get('/worker/:worker_id', authenticateToken, async (req, res) => {
    try {
        const targetWorkerId = req.params.worker_id;

        // If logged in as worker, can only see their own violations
        if (req.user.role === 'worker' && req.user.username !== targetWorkerId) {
            return res.status(403).json({ error: 'Forbidden. You can only view your own violations.' });
        }

        const [rows] = await db.query(`
            SELECT v.*, c.camera_name
            FROM violations v
            LEFT JOIN cameras c ON v.camera_id = c.camera_id
            WHERE v.worker_id = ?
            ORDER BY v.timestamp DESC
            LIMIT 50
        `, [targetWorkerId]);

        res.json(rows);
    } catch (error) {
        console.error('Error fetching worker violations:', error);
        res.status(500).json({ error: 'Failed to retrieve worker violations' });
    }
});

module.exports = router;