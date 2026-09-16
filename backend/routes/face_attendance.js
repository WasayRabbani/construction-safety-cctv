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
        const faceApiUrl = process.env.AI_FACE_API_URL || 'http://127.0.0.1:7860/face';
        const pythonResponse = await fetch(`${faceApiUrl}/recognize`, {
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
