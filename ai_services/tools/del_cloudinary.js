// delete_cloudinary.js
require('dotenv').config();
const cloudinary = require('cloudinary').v2;

cloudinary.config({
  cloud_name: process.env.CLOUDINARY_CLOUD_NAME,
  api_key:    process.env.CLOUDINARY_API_KEY,
  api_secret: process.env.CLOUDINARY_API_SECRET
});

async function clearCloud() {
  await cloudinary.api.delete_resources_by_prefix('ppe_workers/');
  await cloudinary.api.delete_resources_by_prefix('ppe_faces/');
  console.log('✅ Cloudinary photos deleted.');
}
clearCloud();
