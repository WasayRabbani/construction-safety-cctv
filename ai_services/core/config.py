import os
import sys

# Ensure core and parent are discoverable
AI_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if AI_ROOT_DIR not in sys.path:
    sys.path.insert(0, AI_ROOT_DIR)

# Path definitions
MODEL_PATH = os.path.join(AI_ROOT_DIR, 'best.pt')
EMPLOYEES_DIR = os.path.join(AI_ROOT_DIR, 'employees')
PROCESSED_VIDEOS_DIR = os.path.join(AI_ROOT_DIR, 'processed_videos')
UPLOAD_DIR = os.path.join(PROCESSED_VIDEOS_DIR, 'uploads')
OUTPUT_DIR = os.path.join(PROCESSED_VIDEOS_DIR, 'outputs')

os.makedirs(EMPLOYEES_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Node.js backend integration URL
BACKEND_URL = os.environ.get('BACKEND_URL', 'http://localhost:4000')
INTERNAL_API_KEY = os.environ.get('INTERNAL_API_KEY', 'dev-internal-key-change-in-prod')

# IMOU / RTSP Camera configuration
DEFAULT_RTSP_URL = os.environ.get('RTSP_CAMERA_URL', '0')


# Standard PPE violations
VIOLATIONS = {
    'NO-Hardhat', 'NO-Gloves', 'NO-Mask',
    'NO-Goggles', 'NO-Safety Vest', 'Fall-Detected'
}

HEAD_CLASSES = {'Person', 'NO-Hardhat', 'Hardhat', 'Mask', 'NO-Mask'}

# Visual styling
COLOR_VIOLATION = (0, 0, 255)    # Red
COLOR_SAFE      = (0, 200, 80)   # Green
COLOR_INFO      = (255, 255, 255)# White
COLOR_NAME      = (0, 220, 255)  # Cyan
FONT            = 0              # cv2.FONT_HERSHEY_SIMPLEX

# Device detection (CUDA GPU vs CPU)
import torch
if torch.cuda.is_available():
    DEVICE = 0
    torch.backends.cudnn.benchmark = True
else:
    DEVICE = 'cpu'
