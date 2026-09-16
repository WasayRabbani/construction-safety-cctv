const express = require('express');
const router = express.Router();
const db = require('../config/database');
const path = require('path');
const fs = require('fs');

// Boilerplate: Import Cloudinary
const cloudinary = require('cloudinary').v2;

// Core Logic: Upload to Cloudinary instead of Local Disk
async function saveWorkerPhotosAndInvalidateCache(worker_id, name, photos) {
    if (!photos || photos.length === 0) return null;

    let photoPathToSaveInDB = null;

    try {
        // Upload the first photo to Cloudinary directly from the Base64 string!
        const uploadResponse = await cloudinary.uploader.upload(photos[0], {
            folder: 'ppe_workers',
            public_id: `${worker_id}_${Date.now()}`
        });

        // Save the public internet URL to your database!
        photoPathToSaveInDB = uploadResponse.secure_url;
        console.log("Successfully uploaded to Cloudinary:", photoPathToSaveInDB);

    } catch (error) {
        console.error("Cloudinary Upload Error:", error);
    }

    // TODO: Later, we will add code here to send a ping to Hugging Face
    // so it knows a new worker was added!

    return photoPathToSaveInDB;
}


// Get face database for Python AI — returns all face photos joined with worker info
router.get('/face-database', async (req, res) => {
    try {
        const [rows] = await db.query(`
            SELECT fp.worker_id, w.name, fp.photo_url
            FROM face_photos fp
            JOIN workers w ON fp.worker_id = w.worker_id
            ORDER BY fp.worker_id
        `);
        res.json(rows);
    } catch (error) {
        console.error('Error fetching face database:', error);
        res.status(500).json({ error: error.message });
    }
});

// Upload multiple face photos for a worker
router.post('/:id/face-photos', async (req, res) => {
    try {
        const worker_id = req.params.id;
        const { photos } = req.body; // array of base64 strings

        if (!photos || photos.length === 0) {
            return res.status(400).json({ error: 'No photos provided' });
        }

        const uploadedUrls = [];
        for (let i = 0; i < photos.length; i++) {
            const uploadResponse = await cloudinary.uploader.upload(photos[i], {
                folder: 'ppe_faces',
                public_id: `${worker_id}_face_${Date.now()}_${i}`
            });
            uploadedUrls.push(uploadResponse.secure_url);

            // Insert each URL into face_photos table
            await db.query(
                'INSERT INTO face_photos (worker_id, photo_url) VALUES (?, ?)',
                [worker_id, uploadResponse.secure_url]
            );
        }

        res.status(201).json({
            message: `${uploadedUrls.length} face photos uploaded successfully`,
            urls: uploadedUrls
        });
    } catch (error) {
        console.error('Error uploading face photos:', error);
        res.status(500).json({ error: error.message });
    }
});

// Get worker stats — MUST be before :id
router.get('/stats/summary', async (req, res) => {
    try {
        const [stats] = await db.query(`
            SELECT 
                COUNT(*) as total_workers,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_workers,
                SUM(CASE WHEN status = 'inactive' THEN 1 ELSE 0 END) as inactive_workers,
                SUM(CASE WHEN MONTH(join_date) = MONTH(NOW()) AND YEAR(join_date) = YEAR(NOW()) THEN 1 ELSE 0 END) as new_this_month
            FROM workers
        `);
        res.json(stats[0]);
    } catch (error) {
        console.error('Error fetching stats:', error);
        res.status(500).json({ error: error.message });
    }
});

// Get all workers
router.get('/', async (req, res) => {
    try {
        const [rows] = await db.query('SELECT * FROM workers ORDER BY worker_id ASC');
        res.json(rows);
    } catch (error) {
        console.error('Error fetching workers:', error);
        res.status(500).json({ error: error.message });
    }
});

// Get single worker
router.get('/:id', async (req, res) => {
    try {
        const [rows] = await db.query('SELECT * FROM workers WHERE worker_id = ?', [req.params.id]);
        if (rows.length === 0) {
            return res.status(404).json({ error: 'Worker not found' });
        }
        res.json(rows[0]);
    } catch (error) {
        console.error('Error fetching worker:', error);
        res.status(500).json({ error: error.message });
    }
});

// Create new worker with auto photo sync
router.post('/', async (req, res) => {
    try {
        const { worker_id, name, cnic, phone, department, wage_type, wage_rate, join_date, photos } = req.body;

        if (!worker_id || !name || !cnic || !wage_type || !wage_rate || !join_date) {
            return res.status(400).json({ error: 'Missing required fields' });
        }

        let photo_path = null;
        if (photos && photos.length > 0) {
            photo_path = await saveWorkerPhotosAndInvalidateCache(worker_id, name, photos);
        }

        const [result] = await db.query(
            `INSERT INTO workers (worker_id, name, cnic, phone, department, wage_type, wage_rate, join_date, photo_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
            [worker_id, name, cnic, phone, department, wage_type, wage_rate, join_date, photo_path]
        );

        res.status(201).json({ message: 'Worker created successfully', worker_id, photo_path });
    } catch (error) {
        console.error('Error creating worker:', error);
        if (error.code === 'ER_DUP_ENTRY') {
            res.status(400).json({ error: 'Worker ID or CNIC already exists' });
        } else {
            res.status(500).json({ error: error.message });
        }
    }
});

// Update worker with optional photo upload
router.put('/:id', async (req, res) => {
    try {
        const { name, cnic, phone, department, wage_type, wage_rate, status, photos, existing_photo_path } = req.body;
        const worker_id = req.params.id;

        const [existing] = await db.query('SELECT photo_path FROM workers WHERE worker_id = ?', [worker_id]);
        if (existing.length === 0) return res.status(404).json({ error: 'Worker not found' });

        let photo_path = existing_photo_path || existing[0].photo_path;

        if (photos && photos.length > 0) {
            photo_path = await saveWorkerPhotosAndInvalidateCache(worker_id, name, photos);

            // Delete old photo in uploads if we generated a new one
            if (existing[0].photo_path && photo_path && photo_path !== existing[0].photo_path) {
                const oldPhotoPath = path.join(__dirname, '../../', existing[0].photo_path);
                if (fs.existsSync(oldPhotoPath)) fs.unlinkSync(oldPhotoPath);
            }
        }

        const [result] = await db.query(
            `UPDATE workers SET name = ?, cnic = ?, phone = ?, department = ?, wage_type = ?, wage_rate = ?, status = ?, photo_path = ? WHERE worker_id = ?`,
            [name, cnic, phone, department, wage_type, wage_rate, status || 'active', photo_path, worker_id]
        );

        if (result.affectedRows === 0) return res.status(404).json({ error: 'Worker not found' });
        res.json({ message: 'Worker updated successfully', photo_path });
    } catch (error) {
        console.error('Error updating worker:', error);
        res.status(500).json({ error: error.message });
    }
});

// Delete worker
router.delete('/:id', async (req, res) => {
    try {
        // Also delete associated face photos from DB (Cloudinary URLs)
        await db.query('DELETE FROM face_photos WHERE worker_id = ?', [req.params.id]);

        const [result] = await db.query('DELETE FROM workers WHERE worker_id = ?', [req.params.id]);

        if (result.affectedRows === 0) {
            return res.status(404).json({ error: 'Worker not found' });
        }

        res.json({ message: 'Worker deleted successfully' });
    } catch (error) {
        console.error('Error deleting worker:', error);
        res.status(500).json({ error: error.message });
    }
});

module.exports = router;