const express = require('express');
const router = express.Router();
const db = require('../config/database');
const path = require('path');
const fs = require('fs');
const { authenticateToken, authorizeRoles } = require('../middleware/auth');

// Boilerplate: Import Cloudinary
const cloudinary = require('cloudinary').v2;

// Boilerplate: Configure Cloudinary with .env credentials
cloudinary.config({
    cloud_name: process.env.CLOUDINARY_CLOUD_NAME,
    api_key:    process.env.CLOUDINARY_API_KEY,
    api_secret: process.env.CLOUDINARY_API_SECRET
});

// Helper: Save Base64 face photos to local disk (ai_services/employees/<Worker Name>/)
function savePhotosToLocalDisk(workerName, photos) {
    if (!photos || !Array.isArray(photos) || photos.length === 0 || !workerName) return [];

    const safeName = workerName.trim().replace(/[\\/:*?"<>|]/g, '');
    const targetDir = path.join(__dirname, '..', '..', 'ai_services', 'employees', safeName);

    if (!fs.existsSync(targetDir)) {
        fs.mkdirSync(targetDir, { recursive: true });
    }

    const savedLocalPaths = [];
    photos.forEach((base64Str, idx) => {
        try {
            const matches = base64Str.match(/^data:([A-Za-z-+\/]+);base64,(.+)$/);
            const imageBuffer = matches ? Buffer.from(matches[2], 'base64') : Buffer.from(base64Str, 'base64');
            const fileName = `photo_${Date.now()}_${idx}.jpg`;
            const filePath = path.join(targetDir, fileName);
            fs.writeFileSync(filePath, imageBuffer);
            savedLocalPaths.push(filePath);
        } catch (err) {
            console.error(`Failed to write local face image ${idx} for ${safeName}:`, err);
        }
    });

    console.log(`💾 Saved ${savedLocalPaths.length} photo(s) to local disk: ${targetDir}`);
    return savedLocalPaths;
}

// Core Logic: Dual storage - local disk + Cloudinary
async function saveWorkerPhotosAndInvalidateCache(worker_id, name, photos) {
    if (!photos || photos.length === 0) return null;

    // 1. Save all burst photos to local disk immediately
    savePhotosToLocalDisk(name, photos);

    let avatarUrl = null;

    try {
        // 2. Upload first photo as main worker profile avatar
        const uploadResponse = await cloudinary.uploader.upload(photos[0], {
            folder: 'ppe_workers',
            public_id: `${worker_id}_${Date.now()}`
        });
        avatarUrl = uploadResponse.secure_url;
        console.log("Successfully uploaded avatar to Cloudinary:", avatarUrl);

        // 3. Upload all photos to face_photos table for CCTV face database sync
        for (let i = 0; i < photos.length; i++) {
            const faceUpload = await cloudinary.uploader.upload(photos[i], {
                folder: 'ppe_faces',
                public_id: `${worker_id}_face_${Date.now()}_${i}`
            });
            await db.query(
                'INSERT INTO face_photos (worker_id, photo_url) VALUES (?, ?)',
                [worker_id, faceUpload.secure_url]
            );
        }
        console.log(`☁️ Uploaded ${photos.length} photos to Cloudinary face_photos`);
    } catch (error) {
        console.error("Cloudinary Upload Error:", error);
    }

    return avatarUrl;
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
router.post('/:id/face-photos', authenticateToken, authorizeRoles('admin', 'supervisor', 'hr'), async (req, res) => {
    try {
        const worker_id = req.params.id;
        const { photos } = req.body;

        if (!photos || !Array.isArray(photos) || photos.length === 0) {
            return res.status(400).json({ error: 'Valid array of photos is required' });
        }

        // Retrieve worker name for disk storage
        const [workers] = await db.query('SELECT name FROM workers WHERE worker_id = ?', [worker_id]);
        if (workers.length === 0) {
            return res.status(404).json({ error: 'Worker not found' });
        }
        const workerName = workers[0].name;

        // 1. Save to local disk in ai_services/employees/<workerName>/
        savePhotosToLocalDisk(workerName, photos);

        // 2. Upload to Cloudinary and save into face_photos table
        const uploadedUrls = [];
        for (let i = 0; i < photos.length; i++) {
            const uploadResponse = await cloudinary.uploader.upload(photos[i], {
                folder: 'ppe_faces',
                public_id: `${worker_id}_face_${Date.now()}_${i}`
            });
            uploadedUrls.push(uploadResponse.secure_url);

            await db.query(
                'INSERT INTO face_photos (worker_id, photo_url) VALUES (?, ?)',
                [worker_id, uploadResponse.secure_url]
            );
        }

        res.status(201).json({
            message: `${uploadedUrls.length} face photos saved locally and uploaded to cloud`,
            urls: uploadedUrls
        });
    } catch (error) {
        console.error('Error uploading face photos:', error);
        res.status(500).json({ error: 'Internal server error while uploading photos' });
    }
});

// Get worker stats — MUST be before :id
router.get('/stats/summary', authenticateToken, async (req, res) => {
    try {
        const [stats] = await db.query(`
            SELECT 
                COUNT(*) as total_workers,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_workers,
                SUM(CASE WHEN status = 'inactive' THEN 1 ELSE 0 END) as inactive_workers,
                SUM(CASE WHEN strftime('%m', join_date) = strftime('%m', 'now') AND strftime('%Y', join_date) = strftime('%Y', 'now') THEN 1 ELSE 0 END) as new_this_month
            FROM workers
        `);
        res.json(stats[0] || {});
    } catch (error) {
        console.error('Error fetching stats:', error);
        res.status(500).json({ error: 'Failed to retrieve worker statistics' });
    }
});

// Get all workers (Paginated to prevent memory exhaustion - Rule 8 & 9)
router.get('/', authenticateToken, async (req, res) => {
    try {
        const limit = Math.min(Math.max(parseInt(req.query.limit) || 50, 1), 100);
        const offset = Math.max(parseInt(req.query.offset) || 0, 0);

        const [rows] = await db.query(
            'SELECT * FROM workers ORDER BY worker_id ASC LIMIT ? OFFSET ?',
            [limit, offset]
        );
        res.json(rows);
    } catch (error) {
        console.error('Error fetching workers:', error);
        res.status(500).json({ error: 'Failed to retrieve workers list' });
    }
});

// Get single worker
router.get('/:id', authenticateToken, async (req, res) => {
    try {
        const [rows] = await db.query('SELECT * FROM workers WHERE worker_id = ?', [req.params.id]);
        if (rows.length === 0) {
            return res.status(404).json({ error: 'Worker not found' });
        }
        res.json(rows[0]);
    } catch (error) {
        console.error('Error fetching worker:', error);
        res.status(500).json({ error: 'Failed to retrieve worker details' });
    }
});

// Create new worker with auto photo sync
router.post('/', authenticateToken, authorizeRoles('admin', 'supervisor', 'hr'), async (req, res) => {
    try {
        const { worker_id, name, cnic, phone, department, wage_type, wage_rate, join_date, photos } = req.body;

        // Rule 4: Validate inputs
        if (!worker_id || !name || !cnic || !wage_type || !wage_rate || !join_date) {
            return res.status(400).json({ error: 'Missing required fields: worker_id, name, cnic, wage_type, wage_rate, join_date' });
        }

        if (!['hourly', 'daily'].includes(wage_type)) {
            return res.status(400).json({ error: "wage_type must be either 'hourly' or 'daily'" });
        }

        let photo_path = null;
        if (photos && photos.length > 0) {
            photo_path = await saveWorkerPhotosAndInvalidateCache(worker_id, name, photos);
        }

        await db.query(
            `INSERT INTO workers (worker_id, name, cnic, phone, department, wage_type, wage_rate, join_date, photo_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
            [worker_id, name, cnic, phone || null, department || null, wage_type, parseFloat(wage_rate), join_date, photo_path]
        );

        res.status(201).json({ message: 'Worker created successfully', worker_id, photo_path });
    } catch (error) {
        console.error('Error creating worker:', error);
        if (error.message && error.message.includes('UNIQUE constraint failed')) {
            return res.status(409).json({ error: 'Worker ID or CNIC already exists' });
        }
        res.status(500).json({ error: 'Internal server error while creating worker' });
    }
});

// Update worker
router.put('/:id', authenticateToken, authorizeRoles('admin', 'supervisor', 'hr'), async (req, res) => {
    try {
        const { name, cnic, phone, department, wage_type, wage_rate, status, photos, existing_photo_path } = req.body;
        const worker_id = req.params.id;

        const [existing] = await db.query('SELECT photo_path FROM workers WHERE worker_id = ?', [worker_id]);
        if (existing.length === 0) return res.status(404).json({ error: 'Worker not found' });

        let photo_path = existing_photo_path || existing[0].photo_path;

        if (photos && photos.length > 0) {
            photo_path = await saveWorkerPhotosAndInvalidateCache(worker_id, name, photos);

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
        res.status(500).json({ error: 'Internal server error while updating worker' });
    }
});

// Helper: Extract Cloudinary public_id from secure URL
function getCloudinaryPublicId(url) {
    if (!url || typeof url !== 'string' || !url.includes('cloudinary.com')) return null;
    try {
        const parts = url.split('/upload/');
        if (parts.length < 2) return null;
        let pathWithExt = parts[1].replace(/^v\d+\//, '');
        const lastDotIdx = pathWithExt.lastIndexOf('.');
        return lastDotIdx !== -1 ? pathWithExt.substring(0, lastDotIdx) : pathWithExt;
    } catch {
        return null;
    }
}

// Delete worker (cleans up Cloudinary, local disk folder, and database records)
router.delete('/:id', authenticateToken, authorizeRoles('admin'), async (req, res) => {
    const workerId = req.params.id;
    try {
        // 1. Fetch worker and face photos before deletion
        const [workers] = await db.query('SELECT name, photo_path FROM workers WHERE worker_id = ?', [workerId]);
        if (workers.length === 0) {
            return res.status(404).json({ error: 'Worker not found' });
        }
        const worker = workers[0];
        const [facePhotos] = await db.query('SELECT photo_url FROM face_photos WHERE worker_id = ?', [workerId]);

        // 2. Delete face images and avatar from Cloudinary
        const cloudinaryUrls = [
            worker.photo_path,
            ...facePhotos.map(p => p.photo_url)
        ].filter(Boolean);

        for (const url of cloudinaryUrls) {
            const publicId = getCloudinaryPublicId(url);
            if (publicId) {
                try {
                    await cloudinary.uploader.destroy(publicId);
                    console.log(`☁️ Cloudinary image deleted: ${publicId}`);
                } catch (cErr) {
                    console.warn(`Failed to delete Cloudinary asset (${publicId}):`, cErr.message);
                }
            }
        }

        // 3. Delete worker's photos folder from local disk (ai_services/employees/<Worker Name>)
        if (worker.name) {
            const safeName = worker.name.trim().replace(/[\\/:*?"<>|]/g, '');
            const targetDir = path.join(__dirname, '..', '..', 'ai_services', 'employees', safeName);
            if (fs.existsSync(targetDir)) {
                try {
                    fs.rmSync(targetDir, { recursive: true, force: true });
                    console.log(`💾 Local disk folder deleted: ${targetDir}`);
                } catch (fErr) {
                    console.warn(`Failed to delete local folder (${targetDir}):`, fErr.message);
                }
            }
        }

        // 4. Delete records from database
        await db.query('DELETE FROM face_photos WHERE worker_id = ?', [workerId]);
        const [result] = await db.query('DELETE FROM workers WHERE worker_id = ?', [workerId]);

        if (result.affectedRows === 0) {
            return res.status(404).json({ error: 'Worker not found' });
        }

        res.json({ message: 'Worker, local face photos, and cloud data deleted successfully' });
    } catch (error) {
        console.error('Error deleting worker:', error);
        res.status(500).json({ error: 'Internal server error while deleting worker' });
    }
});

module.exports = router;