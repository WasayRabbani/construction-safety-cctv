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
