// frontend/config.js

// THE CORE LOGIC: Environment Detection
// This checks if the user is running the website on their personal computer ('localhost').
// If they are, it talks to the local Node.js server.
// If they are on the real website (Vercel), it talks to the production Render server.

const IS_LOCAL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

const CONFIG = {
    // Node.js Backend Address
    API_BASE: IS_LOCAL 
        ? 'http://localhost:4000/api' 
        : 'https://your-future-render-app.onrender.com/api',
        
    // Python AI Server 1: CCTV Stream
    AI_CCTV_BASE: IS_LOCAL
        ? 'http://127.0.0.1:7860/cctv'
        : 'https://your-huggingface-space.hf.space/cctv',
        
    // Python AI Server 2: Video Processing
    AI_VIDEO_BASE: IS_LOCAL
        ? 'http://127.0.0.1:7860/video'
        : 'https://your-huggingface-space.hf.space/video',
        
    // Python AI Server 3: Face Recognition
    AI_FACE_BASE: IS_LOCAL
        ? 'http://127.0.0.1:7860/face'
        : 'https://your-huggingface-space.hf.space/face'
};
