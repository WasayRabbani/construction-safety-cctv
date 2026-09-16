const multer = require('multer');
const { CloudinaryStorage } = require('multer-storage-cloudinary');
const cloudinary = require('cloudinary').v2;

// Boilerplate: Authenticate with your .env secrets
cloudinary.config({
    cloud_name: process.env.CLOUDINARY_CLOUD_NAME,
    api_key: process.env.CLOUDINARY_API_KEY,
    api_secret: process.env.CLOUDINARY_API_SECRET
});

// Core Logic: Tell Multer to send files to Cloudinary instead of the hard drive
const storage = new CloudinaryStorage({
    cloudinary: cloudinary,
    params: {
        folder: 'ppe_workers', // The folder name inside your Cloudinary account
        allowed_formats: ['jpg', 'png', 'jpeg'],
        public_id: (req, file) => {
            const workerId = req.body.worker_id || 'temp';
            return `${workerId}_${Date.now()}`;
        }
    }
});

// Configure Multer
const upload = multer({
    storage: storage,
    limits: { fileSize: 5 * 1024 * 1024 } // 5MB limit
});

module.exports = upload;
