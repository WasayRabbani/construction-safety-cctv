const express = require('express');
const router = express.Router();
const db = require('../config/database');

// Proxy to the Python Flask server
router.post('/scan', async (req, res) => {
    try {
        const { image, ai_base_url } = req.body;

        if (!image) {
            return res.status(400).json({ success: false, error: 'No image provided' });
        }

        // Using native Node 18+ fetch API instead of node-fetch
        // Ensure Python API is running on port 7860
        const faceApiUrl = ai_base_url || process.env.AI_FACE_API_URL || 'http://127.0.0.1:7860/face';
        const pythonResponse = await fetch(`${faceApiUrl}/recognize`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            },
            body: JSON.stringify({ image: image })
        });

        if (!pythonResponse.ok) {
            throw new Error(`Python API responded with status ${pythonResponse.status}`);
        }

        const data = await pythonResponse.json();

        // 2. Handle the result
        if (data.status === 'match') {
            // The AI returns the worker's folder name (= their full name, e.g. "Abdul Wasay Rabbani").
            // The DB worker_id is a short code like "W001", so we MUST search by name.
            const recognizedName = (data.worker_id || '').trim();
            const confidence = data.confidence;

            // Search by name (case-insensitive, trimmed).
            // Also try matching on first+last name without middle name as a fallback.
            const nameParts = recognizedName.split(/\s+/);
            const shortName = nameParts.length >= 2
                ? `${nameParts[0]} ${nameParts[nameParts.length - 1]}`
                : recognizedName;

            const [workers] = await db.query(
                `SELECT * FROM workers 
                 WHERE LOWER(TRIM(name)) = LOWER(?)
                    OR LOWER(TRIM(name)) = LOWER(?)
                    OR LOWER(TRIM(worker_id)) = LOWER(?)
                 LIMIT 1`,
                [recognizedName, shortName, recognizedName]
            );

            if (workers.length === 0) {
                return res.status(404).json({
                    success: false,
                    message: `Face matched '${recognizedName}', but no worker with this name was found in the database. Please ensure the worker's name in the system matches the folder name in ai_services/employees/.`
                });
            }

            const worker = workers[0];
            const now = new Date();
            const check_in_time = now.toISOString().replace('T', ' ').slice(0, 19);
            const attendance_date = now.toISOString().slice(0, 10);

            // Check if already checked in today using indexed attendance_date
            const [existing] = await db.query(
                'SELECT * FROM attendance WHERE worker_id = ? AND attendance_date = ?',
                [worker.worker_id, attendance_date]
            );

            if (existing.length > 0) {
                return res.json({
                    success: true,
                    message: `${worker.name} is already checked in for today!`,
                    worker: worker,
                    confidence: confidence
                });
            }

            // Determine if late (work starts at 8:30 AM)
            const hour = now.getHours();
            const minute = now.getMinutes();
            const status = (hour > 8 || (hour === 8 && minute > 30)) ? 'late' : 'present';

            // Auto check-in
            await db.query(
                'INSERT INTO attendance (worker_id, check_in_time, status, location, attendance_date) VALUES (?, ?, ?, ?, ?)',
                [worker.worker_id, check_in_time, status, 'Front Gate Camera', attendance_date]
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
