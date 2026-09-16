import os
import time
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
import cv2
import numpy as np

try:
    import face_recognition
except ImportError:
    print("[ERROR] face_recognition library is not installed. Please wait for installation.")

# ── DEVICE DETECTION ─────────────────────────────────────────────────────────
print("\n🔍 Checking Hardware...")
# face_recognition runs extremely fast on CPU using HOG + dlib
print("🚀 Face Recognition will use high-speed C++ CPU processing (dlib HOG).")
print("────────────────────────────────────────────────\n")

app = Flask(__name__)
CORS(app)

import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'employees')
MATCH_THRESHOLD = 0.50 # face_recognition uses distance < 0.6 for match. 0.5 is strict.

# ── LAZY LOADING ──────────────────────────────────────────────────────────────
# Face encodings are NOT loaded at startup. They load when the user opens the
# Face Recognition tab and unload when they leave to free memory.
KNOWN_ENCODINGS = []
KNOWN_NAMES = []
face_db_loaded = False

def load_known_faces():
    global KNOWN_ENCODINGS, KNOWN_NAMES, face_db_loaded
    if face_db_loaded:
        return  # Already loaded, skip
    KNOWN_ENCODINGS = []
    KNOWN_NAMES = []
    
    total_images = 0
    start_time = time.time()
    
    print(f"🔄 Loading Employee Face Database into Memory...")
    
    for root, dirs, files in os.walk(DB_PATH):
        for f in files:
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                total_images += 1
                path = os.path.join(root, f)
                worker_id = os.path.basename(root)
                
                try:
                    img = cv2.imread(path)
                    if img is not None:
                        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        encodings = face_recognition.face_encodings(rgb_img)
                        if len(encodings) > 0:
                            KNOWN_ENCODINGS.append(encodings[0])
                            KNOWN_NAMES.append(worker_id)
                except Exception as e:
                    print(f"[WARN] Failed to process {path}: {e}")
                    
    elapsed = time.time() - start_time
    face_db_loaded = True
    print(f"✅ Face Database ({total_images} images) loaded in {elapsed:.2f}s.")

def unload_known_faces():
    global KNOWN_ENCODINGS, KNOWN_NAMES, face_db_loaded
    if not face_db_loaded:
        return
    KNOWN_ENCODINGS = []
    KNOWN_NAMES = []
    face_db_loaded = False
    print("[INFO] Face database unloaded from memory.")

def get_confidence(distance):
    return max(0, round((1 - distance) * 100, 1))

@app.route('/recognize', methods=['POST'])
def recognize_face():
    try:
        data = request.json
        if not data or 'image' not in data:
            return jsonify({"error": "No image data provided"}), 400

        image_data = data['image']
        if ',' in image_data:
            image_data = image_data.split(',')[1]
            
        img_bytes = base64.b64decode(image_data)
        
        # Instant decoding in memory, no disk I/O!
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Convert BGR (OpenCV) to RGB (face_recognition)
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # HOG model is insanely fast
        face_locations = face_recognition.face_locations(rgb_img, model="hog")
        if not face_locations:
            return jsonify({"status": "no_face", "message": "No face detected in image"})
            
        unknown_encodings = face_recognition.face_encodings(rgb_img, face_locations)
        unknown_encoding = unknown_encodings[0]
        
        distances = face_recognition.face_distance(KNOWN_ENCODINGS, unknown_encoding)
        
        if len(distances) == 0:
             return jsonify({"status": "unknown", "message": "Database is empty."})
             
        best_match_index = np.argmin(distances)
        min_distance = distances[best_match_index]
        
        if min_distance < MATCH_THRESHOLD:
            worker_id = KNOWN_NAMES[best_match_index]
            confidence = get_confidence(min_distance)
            
            return jsonify({
                "status": "match",
                "worker_id": worker_id,
                "confidence": confidence,
                "distance": min_distance
            })
        else:
            return jsonify({
                "status": "unknown",
                "message": "Face detected, but unverified."
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Tab-based model lifecycle ─────────────────────────────────────────────────
@app.route('/load-model', methods=['POST'])
def load_model_endpoint():
    """Called when user opens the Face Recognition tab."""
    load_known_faces()
    return jsonify({"status": "ok", "message": "Face database loaded."})

@app.route('/unload-model', methods=['POST'])
def unload_model_endpoint():
    """Called when user leaves the Face Recognition tab."""
    unload_known_faces()
    return jsonify({"status": "ok", "message": "Face database unloaded."})

@app.route('/health')
def health():
    return jsonify({"status": "ok", "loaded": face_db_loaded, "faces": len(KNOWN_ENCODINGS)})

if __name__ == '__main__':
    # Server starts lightweight — NO model loaded until user opens the tab
    print(f"🚀 Face Recognition API listening on port 5000 (model will load on-demand)")
    app.run(host='0.0.0.0', port=5000, debug=False)
