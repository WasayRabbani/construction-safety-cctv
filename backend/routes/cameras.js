// File: backend/routes/cameras.js
const express = require('express');
const router = express.Router();
const db = require('../config/database');
const { authenticateToken, authorizeRoles, requireApiKeyOrAuth } = require('../middleware/auth');

// Get all cameras (Accessible by authenticated users or Python AI services)
router.get('/', requireApiKeyOrAuth, async (req, res) => {
    try {
        const [rows] = await db.query(
            'SELECT camera_id, camera_name, location, status, resolution, fps, last_active FROM cameras ORDER BY camera_id ASC'
        );
        res.json(rows);
    } catch (error) {
        console.error('Error fetching cameras:', error);
        res.status(500).json({ error: 'Failed to retrieve cameras list' });
    }
});

// Camera stats summary (Count online/offline cameras)
router.get('/stats/summary', authenticateToken, async (req, res) => {
    try {
        const [stats] = await db.query(`
            SELECT 
                COUNT(*) as total_cameras,
                SUM(CASE WHEN status = 'online' THEN 1 ELSE 0 END) as online_cameras,
                SUM(CASE WHEN status = 'offline' THEN 1 ELSE 0 END) as offline_cameras
            FROM cameras
        `);
        res.json(stats[0] || { total_cameras: 0, online_cameras: 0, offline_cameras: 0 });
    } catch (error) {
        console.error('Error fetching camera stats:', error);
        res.status(500).json({ error: 'Failed to retrieve camera statistics' });
    }
});

// Get single camera by ID
router.get('/:id', authenticateToken, async (req, res) => {
    try {
        const [rows] = await db.query('SELECT * FROM cameras WHERE camera_id = ?', [req.params.id]);
        if (rows.length === 0) {
            return res.status(404).json({ error: 'Camera not found' });
        }
        res.json(rows[0]);
    } catch (error) {
        console.error('Error fetching camera details:', error);
        res.status(500).json({ error: 'Failed to retrieve camera' });
    }
});

// Add new camera (Admin & Supervisor only)
router.post('/', authenticateToken, authorizeRoles('admin', 'supervisor'), async (req, res) => {
    try {
        const { camera_name, location, resolution = '1920x1080', fps = 30 } = req.body;

        if (!camera_name || !location) {
            return res.status(400).json({ error: 'camera_name and location are required' });
        }

        const [result] = await db.query(
            `INSERT INTO cameras (camera_name, location, status, resolution, fps, last_active)
             VALUES (?, ?, 'online', ?, ?, datetime('now', 'localtime'))`,
            [camera_name.trim(), location.trim(), resolution, parseInt(fps) || 30]
        );

        res.status(201).json({
            message: 'Camera registered successfully',
            camera_id: result.insertId
        });
    } catch (error) {
        console.error('Error registering camera:', error);
        res.status(500).json({ error: 'Failed to register camera' });
    }
});

// Update camera status & heartbeat (Can be called by Python AI service or Admin)
router.put('/:id/status', requireApiKeyOrAuth, async (req, res) => {
    try {
        const { status } = req.body;
        const validStatuses = ['online', 'offline'];

        if (!status || !validStatuses.includes(status)) {
            return res.status(400).json({ error: "Invalid status. Must be 'online' or 'offline'" });
        }

        const [result] = await db.query(
            `UPDATE cameras 
             SET status = ?, last_active = datetime('now', 'localtime') 
             WHERE camera_id = ?`,
            [status, req.params.id]
        );

        if (result.affectedRows === 0) {
            return res.status(404).json({ error: 'Camera not found' });
        }

        res.json({ message: 'Camera status updated successfully' });
    } catch (error) {
        console.error('Error updating camera status:', error);
        res.status(500).json({ error: 'Failed to update camera status' });
    }
});

// Delete camera (Admin only)
router.delete('/:id', authenticateToken, authorizeRoles('admin'), async (req, res) => {
    try {
        const [result] = await db.query('DELETE FROM cameras WHERE camera_id = ?', [req.params.id]);

        if (result.affectedRows === 0) {
            return res.status(404).json({ error: 'Camera not found' });
        }

        res.json({ message: 'Camera deleted successfully' });
    } catch (error) {
        console.error('Error deleting camera:', error);
        res.status(500).json({ error: 'Failed to delete camera' });
    }
});

module.exports = router;
