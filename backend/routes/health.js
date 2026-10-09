// File: backend/routes/health.js
const express = require('express');
const router = express.Router();
const db = require('../config/database');
const { authenticateToken, authorizeRoles } = require('../middleware/auth');

// Get all health alerts with filters and pagination
router.get('/', authenticateToken, async (req, res) => {
    try {
        const { status, severity, worker_id } = req.query;
        const limit = Math.min(Math.max(parseInt(req.query.limit) || 50, 1), 100);
        const offset = Math.max(parseInt(req.query.offset) || 0, 0);

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

        query += ' ORDER BY h.timestamp DESC LIMIT ? OFFSET ?';
        params.push(limit, offset);

        const [rows] = await db.query(query, params);
        res.json(rows);
    } catch (error) {
        console.error('Error fetching health alerts:', error);
        res.status(500).json({ error: 'Failed to retrieve health alerts' });
    }
});

// Get health alerts stats
router.get('/stats/summary', authenticateToken, async (req, res) => {
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
            WHERE status = 'resolved' AND date(resolved_at) = date('now', 'localtime')
        `);

        const [avgResponse] = await db.query(`
            SELECT AVG(response_time) as avg_time FROM health_alerts
            WHERE response_time IS NOT NULL AND date(timestamp) >= date('now', 'localtime', '-7 days')
        `);

        res.json({
            critical: critical[0]?.count || 0,
            active: active[0]?.count || 0,
            resolved: resolved[0]?.count || 0,
            avg_response_time: avgResponse[0]?.avg_time ? Math.round(avgResponse[0].avg_time) : 0
        });
    } catch (error) {
        console.error('Error fetching health stats:', error);
        res.status(500).json({ error: 'Failed to retrieve health statistics' });
    }
});

// Create new health alert (Alert detection from camera or staff)
router.post('/', async (req, res) => {
    try {
        const { worker_id, alert_type, severity, description, location, camera_id } = req.body;

        if (!alert_type) {
            return res.status(400).json({ error: 'alert_type is required' });
        }

        const [result] = await db.query(
            `INSERT INTO health_alerts (timestamp, worker_id, alert_type, severity, description, location, camera_id)
             VALUES (datetime('now', 'localtime'), ?, ?, ?, ?, ?, ?)`,
            [worker_id || null, alert_type, severity || 'medium', description || null, location || null, camera_id || null]
        );

        res.status(201).json({ 
            message: 'Health alert created successfully', 
            alert_id: result.insertId 
        });
    } catch (error) {
        console.error('Error creating health alert:', error);
        res.status(500).json({ error: 'Failed to create health alert' });
    }
});

// Resolve health alert (Restricted to safety officer / admin / supervisor)
router.put('/:id/resolve', authenticateToken, authorizeRoles('admin', 'supervisor', 'safety officer'), async (req, res) => {
    try {
        const { response_time } = req.body;

        const [result] = await db.query(
            `UPDATE health_alerts 
             SET status = 'resolved', resolved_at = datetime('now', 'localtime'), response_time = ? 
             WHERE alert_id = ?`,
            [response_time || 0, req.params.id]
        );

        if (result.affectedRows === 0) {
            return res.status(404).json({ error: 'Health alert not found' });
        }

        res.json({ message: 'Health alert resolved successfully' });
    } catch (error) {
        console.error('Error resolving health alert:', error);
        res.status(500).json({ error: 'Failed to resolve health alert' });
    }
});

// Get alerts by worker
router.get('/worker/:worker_id', authenticateToken, async (req, res) => {
    try {
        const targetWorkerId = req.params.worker_id;

        if (req.user.role === 'worker' && req.user.username !== targetWorkerId) {
            return res.status(403).json({ error: 'Forbidden. You can only view your own health alerts.' });
        }

        const [rows] = await db.query(`
            SELECT h.*, c.camera_name
            FROM health_alerts h
            LEFT JOIN cameras c ON h.camera_id = c.camera_id
            WHERE h.worker_id = ?
            ORDER BY h.timestamp DESC
            LIMIT 50
        `, [targetWorkerId]);

        res.json(rows);
    } catch (error) {
        console.error('Error fetching worker health alerts:', error);
        res.status(500).json({ error: 'Failed to retrieve worker health alerts' });
    }
});

module.exports = router;
