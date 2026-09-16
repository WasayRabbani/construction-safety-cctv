import os
import sys
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple
from flask import Flask, jsonify
from flask_cors import CORS

print("=====================================================")
print("🤖 BOOTING UP MASTER AI SERVER (PORT 7860)")
print("=====================================================")

# 1. Import the Flask apps from the other files
print("\n[1/3] Initializing Face Recognition AI...")
from face_api import app as face_app

print("\n[2/3] Initializing CCTV AI...")
from intelligent_cctv import app as cctv_app

print("\n[3/3] Initializing Video Processor AI...")
from video_processor import app as video_app

# 2. Create a Root Master App
master_app = Flask(__name__)
CORS(master_app)

@master_app.route('/')
def index():
    return jsonify({
        "status": "online",
        "message": "AI Master Server is running on Port 7860",
        "endpoints": {
            "face_recognition": "/face",
            "cctv_stream": "/cctv",
            "video_processing": "/video"
        }
    })

# 3. Mount the other apps onto specific URL paths using Werkzeug Dispatcher
master_app.wsgi_app = DispatcherMiddleware(master_app.wsgi_app, {
    '/face': face_app.wsgi_app,
    '/cctv': cctv_app.wsgi_app,
    '/video': video_app.wsgi_app
})

if __name__ == '__main__':
    print("\n=====================================================")
    print("🚀 ALL SYSTEMS GO! LISTENING ON http://0.0.0.0:7860")
    print("   - Face API:  http://127.0.0.1:7860/face")
    print("   - CCTV API:  http://127.0.0.1:7860/cctv")
    print("   - Video API: http://127.0.0.1:7860/video")
    print("=====================================================")
    
    # Port 7860 is Hugging Face's default required port!
    run_simple('0.0.0.0', 7860, master_app, use_reloader=False, use_debugger=False)
