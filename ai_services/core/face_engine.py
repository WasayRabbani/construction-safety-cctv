import os
import time
import threading
from typing import List, Tuple, Optional, Dict
import cv2
import numpy as np
import requests
from PIL import Image
import torch

from core.config import EMPLOYEES_DIR, BACKEND_URL

class FaceTracker:
    """Maintains spatial and temporal tracking of identified workers to prevent re-scanning."""

    def __init__(self, match_radius: int = 150, timeout: float = 5.0, cooldown: float = 1.5):
        self.match_radius = match_radius
        self.timeout = timeout
        self.cooldown = cooldown
        self.recognized_faces: List[Dict] = []
        self._lock = threading.Lock()

    def get_cached_identity(self, cx: int, cy: int) -> Tuple[str, float]:
        """Find the closest cached worker name near pixel coordinate (cx, cy)."""
        now = time.time()
        with self._lock:
            best_dist = self.match_radius
            best_entry = None
            for entry in self.recognized_faces:
                if now - entry["time"] > self.timeout:
                    continue
                dist = abs(entry["cx"] - cx) + abs(entry["cy"] - cy)
                if dist < best_dist:
                    best_dist = dist
                    best_entry = entry

            if best_entry:
                return best_entry["name"], best_entry.get("last_scan", 0.0)
            return "", 0.0

    def update_cache(self, cx: int, cy: int, name: str, is_scan_attempt: bool = False):
        """Update or insert an identified face into spatial cache."""
        now = time.time()
        with self._lock:
            for entry in self.recognized_faces:
                dist = abs(entry["cx"] - cx) + abs(entry["cy"] - cy)
                if dist < self.match_radius:
                    if not is_scan_attempt:
                        entry["name"] = name
                        entry["cx"] = cx
                        entry["cy"] = cy
                        entry["time"] = now
                    entry["last_scan"] = now
                    return

            self.recognized_faces.append({
                "cx": cx, "cy": cy, "name": name, "time": now, "last_scan": now
            })
            # Purge stale entries
            self.recognized_faces[:] = [
                e for e in self.recognized_faces if now - e["time"] < (self.timeout * 2)
            ]


class FaceEngine:
    """Unified Face Recognition Engine supporting dlib (local) and facenet-pytorch (cloud fallback)."""

    def __init__(self, employees_dir: str = EMPLOYEES_DIR, backend_url: str = BACKEND_URL):
        self.employees_dir = employees_dir
        self.backend_url = backend_url
        self.backend = None
        self.known_encodings = []
        self.known_names = []
        self.tracker = FaceTracker()
        self._lock = threading.Lock()
        self.is_loaded = False

        self._init_backend()

    def _init_backend(self):
        try:
            import face_recognition
            self.backend = 'dlib'
            self._fr = face_recognition
            print("[INFO] FaceEngine backend: dlib/face_recognition (local/fast)")
        except ImportError:
            try:
                from facenet_pytorch import MTCNN, InceptionResnetV1
                self._mtcnn = MTCNN(image_size=160, margin=20, keep_all=False, device='cpu')
                self._resnet = InceptionResnetV1(pretrained='vggface2').eval()
                self.backend = 'facenet'
                print("[INFO] FaceEngine backend: facenet-pytorch (cloud mode)")
            except ImportError:
                self.backend = None
                print("[WARN] No face recognition library found. Face ID disabled.")

    def _get_facenet_embedding(self, rgb_img):
        try:
            img_pil = Image.fromarray(rgb_img)
            face_tensor = self._mtcnn(img_pil)
            if face_tensor is None:
                return None
            with torch.no_grad():
                embedding = self._resnet(face_tensor.unsqueeze(0))
            return embedding.numpy().flatten()
        except Exception:
            return None

    def load_faces(self) -> int:
        """Load known face encodings from local disk first, fallback to Backend API."""
        with self._lock:
            new_encodings = []
            new_names = []
            total = 0
            start_time = time.time()

            # 1. Local disk scanning
            if os.path.exists(self.employees_dir):
                for root, _, files in os.walk(self.employees_dir):
                    for f in files:
                        if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                            path = os.path.join(root, f)
                            worker_name = os.path.basename(root)
                            try:
                                img = cv2.imread(path)
                                if img is not None:
                                    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                                    if self.backend == 'dlib':
                                        encs = self._fr.face_encodings(rgb)
                                        if len(encs) > 0:
                                            new_encodings.append(encs[0])
                                            new_names.append(worker_name)
                                            total += 1
                                    elif self.backend == 'facenet':
                                        emb = self._get_facenet_embedding(rgb)
                                        if emb is not None:
                                            new_encodings.append(emb)
                                            new_names.append(worker_name)
                                            total += 1
                            except Exception as e:
                                print(f"[WARN] Failed to load local face {path}: {e}")

            if total > 0:
                self.known_encodings = new_encodings
                self.known_names = new_names
                self.is_loaded = True
                elapsed = time.time() - start_time
                print(f"✅ FaceEngine: Loaded {total} photos for {len(set(new_names))} workers from local disk in {elapsed:.2f}s.")
                return total

            # 2. Cloud backend fallback
            print("🔄 FaceEngine: Fetching face database from Cloud Backend...")
            try:
                resp = requests.get(f"{self.backend_url}/api/workers/face-database", timeout=10)
                if resp.ok:
                    workers_data = resp.json()
                    for entry in workers_data:
                        worker_name = entry.get('name') or entry.get('worker_id')
                        photo_url = entry.get('photo_url')
                        if not worker_name or not photo_url:
                            continue
                        try:
                            img_bytes = requests.get(photo_url, timeout=10).content
                            img_array = np.frombuffer(img_bytes, np.uint8)
                            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                            if img is not None:
                                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                                if self.backend == 'dlib':
                                    encs = self._fr.face_encodings(rgb)
                                    if len(encs) > 0:
                                        new_encodings.append(encs[0])
                                        new_names.append(worker_name)
                                        total += 1
                                elif self.backend == 'facenet':
                                    emb = self._get_facenet_embedding(rgb)
                                    if emb is not None:
                                        new_encodings.append(emb)
                                        new_names.append(worker_name)
                                        total += 1
                        except Exception as e:
                            print(f"[WARN] Cloud face encode error for {worker_name}: {e}")

                    if total > 0:
                        self.known_encodings = new_encodings
                        self.known_names = new_names
                        self.is_loaded = True
                        elapsed = time.time() - start_time
                        print(f"✅ FaceEngine: Loaded {total} photos from Cloud API in {elapsed:.2f}s.")
            except Exception as e:
                print(f"[WARN] Could not load faces from backend: {e}")

            return total

    def unload_faces(self):
        """Free face encodings from memory."""
        with self._lock:
            self.known_encodings.clear()
            self.known_names.clear()
            self.is_loaded = False
            print("[INFO] FaceEngine: Unloaded face database from memory.")

    def recognize_crop(self, crop_bgr, threshold: float = 0.50) -> Tuple[str, str, float]:
        """
        Recognize an image crop.
        Returns (status, worker_name, confidence).
        Status is 'match', 'unknown', or 'no_face'.
        """
        if self.backend is None or not self.known_encodings:
            return "unknown", "Unknown Person", 0.0

        rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)

        # Scale down large crops to max 300px for high-speed matching
        max_w = 300
        if rgb.shape[1] > max_w:
            ratio = max_w / float(rgb.shape[1])
            rgb = cv2.resize(rgb, (max_w, int(rgb.shape[0] * ratio)))

        if self.backend == 'dlib':
            locations = self._fr.face_locations(rgb, model="hog")
            if not locations:
                return "no_face", "", 0.0

            encodings = self._fr.face_encodings(rgb, locations)
            if not encodings:
                return "no_face", "", 0.0

            distances = self._fr.face_distance(self.known_encodings, encodings[0])
            if len(distances) == 0:
                return "unknown", "Unknown Person", 0.0

            best_idx = int(np.argmin(distances))
            min_dist = float(distances[best_idx])

            if min_dist < threshold:
                confidence = max(0.0, round((1.0 - min_dist) * 100.0, 1))
                return "match", self.known_names[best_idx], confidence
            return "unknown", "Unknown Person", 0.0

        elif self.backend == 'facenet':
            embedding = self._get_facenet_embedding(rgb)
            if embedding is None:
                return "no_face", "", 0.0

            sims = [
                float(np.dot(embedding, k) / (np.linalg.norm(embedding) * np.linalg.norm(k) + 1e-9))
                for k in self.known_encodings
            ]
            best_idx = int(np.argmax(sims))
            best_sim = sims[best_idx]
            if best_sim > 0.75:
                confidence = round(best_sim * 100.0, 1)
                return "match", self.known_names[best_idx], confidence
            return "unknown", "Unknown Person", 0.0
