"""
Face Recognition API — Thin HTTP Controller
============================================
Port  : 5000
Routes: POST /recognize, POST /load-model, POST /unload-model, GET /health

All logic is handled by core.FaceEngine.
This file is a thin Flask routing layer only.
"""

import os
import sys
import base64
import logging

import cv2
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS

# Make core/ importable when this service is run standalone or via app.py
_AI_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AI_ROOT not in sys.path:
    sys.path.insert(0, _AI_ROOT)

from core.face_engine import FaceEngine  # noqa: E402

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)
logging.getLogger("werkzeug").setLevel(logging.ERROR)

# Single shared FaceEngine instance for this service
_engine = FaceEngine()

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/load-model", methods=["POST"])
def load_model():
    """Called when the user opens the Face Recognition tab."""
    count = _engine.load_faces()
    return jsonify({"status": "ok", "message": "Face database loaded.", "faces": count})


@app.route("/unload-model", methods=["POST"])
def unload_model():
    """Called when the user leaves the Face Recognition tab."""
    _engine.unload_faces()
    return jsonify({"status": "ok", "message": "Face database unloaded."})


@app.route("/recognize", methods=["POST"])
def recognize():
    """Accept a base64-encoded image and return recognition result."""
    try:
        data = request.json
        if not data or "image" not in data:
            return jsonify({"error": "No image data provided"}), 400

        image_data = data["image"]
        if "," in image_data:
            image_data = image_data.split(",")[1]

        img_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img_bgr is None:
            return jsonify({"error": "Could not decode image"}), 400

        status, worker_name, confidence = _engine.recognize_crop(img_bgr)

        if status == "no_face":
            return jsonify({"status": "no_face", "message": "No face detected in image"})
        if status == "match":
            return jsonify({
                "status": "match",
                "worker_id": worker_name,
                "confidence": confidence,
            })
        return jsonify({"status": "unknown", "message": "Face detected, but unverified."})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "loaded": _engine.is_loaded,
        "faces": len(_engine.known_names),
    })


if __name__ == "__main__":
    print("🚀 Face Recognition API listening on port 5000 (model loads on-demand)")
    app.run(host="0.0.0.0", port=5000, debug=False)
