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
