const express = require('express');
const router = express.Router();
const db = require('../config/database');
const upload = require('../config/upload');
const path = require('path');
const fs = require('fs');

async function saveWorkerPhotosAndInvalidateCache(worker_id, name, photos) {
    if (!photos || photos.length === 0) return null;

    // Use name for Face_recognition employee directory so the AI returns the Name instead of ID
    const safeName = (name || worker_id).toString().replace(/[^a-zA-Z0-9 ]/g, "").trim();
    const dir = path.join(__dirname, '../../Face_recognition/employees', safeName || worker_id);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

    let photoPathToSaveInDB = null;

    // Write all base64 photos to the directory
    for (let i = 0; i < photos.length; i++) {
        const base64Data = photos[i].replace(/^data:image\/\w+;base64,/, "");
        const filePath = path.join(dir, `photo_${i + 1}.jpg`);
        fs.writeFileSync(filePath, base64Data, 'base64');
        
        // Save first photo to uploads so dashboard UI can show it nicely
        if (i === 0) {
            const uploadDir = path.join(__dirname, '../../uploads/workers');
            if (!fs.existsSync(uploadDir)) fs.mkdirSync(uploadDir, { recursive: true });
            
            const dbPhotoName = `${worker_id}_${Date.now()}.jpg`;
            const dbPhotoPath = path.join(uploadDir, dbPhotoName);
            fs.writeFileSync(dbPhotoPath, base64Data, 'base64');
            photoPathToSaveInDB = `/uploads/workers/${dbPhotoName}`;
        }
    }

    // Invalidate DeepFace Cache so next scan automatically reindexes!
    const cacheFile = path.join(__dirname, '../../Face_recognition/employees/representations_facenet512.pkl');
    if (fs.existsSync(cacheFile)) {
        try { fs.unlinkSync(cacheFile); } catch(e) { console.error("Cache clear error:", e); }
    }

    return photoPathToSaveInDB;
}

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
                if(fs.existsSync(oldPhotoPath)) fs.unlinkSync(oldPhotoPath);
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
        // Get worker info before deletion
        const [worker] = await db.query('SELECT name, photo_path FROM workers WHERE worker_id = ?', [req.params.id]);
        
        const [result] = await db.query('DELETE FROM workers WHERE worker_id = ?', [req.params.id]);
        
        if (result.affectedRows === 0) {
            return res.status(404).json({ error: 'Worker not found' });
        }
        
        // Delete photo file in uploads if it exists
        if (worker.length > 0 && worker[0].photo_path) {
            const photoPath = path.join(__dirname, '../../', worker[0].photo_path);
            fs.unlink(photoPath, (err) => {
                if (err) console.error('Error deleting upload photo:', err);
            });
        }
        
        // Delete Face_recognition/employees/{name}/ folder so AI stops recognizing them
        if (worker.length > 0 && worker[0].name) {
            const safeName = (worker[0].name).toString().replace(/[^a-zA-Z0-9 ]/g, "").trim();
            const employeeDir = path.join(__dirname, '../../Face_recognition/employees', safeName);
            if (fs.existsSync(employeeDir)) {
                fs.rmSync(employeeDir, { recursive: true, force: true });
                console.log('[CLEANUP] Deleted employee folder: ' + employeeDir);
            }
            
            // Invalidate DeepFace cache so it re-indexes without this worker
            const cacheDir = path.join(__dirname, '../../Face_recognition/employees');
            try {
                const files = fs.readdirSync(cacheDir);
                files.forEach(f => {
                    if (f.endsWith('.pkl')) {
                        fs.unlinkSync(path.join(cacheDir, f));
                        console.log('[CLEANUP] Deleted cache: ' + f);
                    }
                });
            } catch(e) { console.error('Cache cleanup error:', e); }
        }
        
        res.json({ message: 'Worker deleted successfully' });
    } catch (error) {
        console.error('Error deleting worker:', error);
        res.status(500).json({ error: error.message });
    }
});

module.exports = router;