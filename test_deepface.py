import cv2
import numpy as np
from deepface import DeepFace
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Face_recognition', 'employees')

try:
    print("Testing DeepFace with opencv backend...")
    dummy = np.zeros((160, 160, 3), dtype=np.uint8)
    cv2.imwrite("test_dummy.jpg", dummy)
    DeepFace.find(img_path="test_dummy.jpg", db_path=DB_PATH, model_name="Facenet512", detector_backend='mtcnn', enforce_detection=False, silent=True)
    print("Success!")
except Exception as e:
    print(f"Error: {e}")
