# Intelligent Construction Safety & CCTV Monitoring System

![Project Banner](https://img.shields.io/badge/AI-Powered%20Monitoring-blue?style=for-the-badge) ![YOLOv8](https://img.shields.io/badge/YOLOv8-PPE%20Detection-orange?style=for-the-badge) ![dlib](https://img.shields.io/badge/dlib-Face%20Recognition-success?style=for-the-badge)

A state-of-the-art AI monitoring system designed for construction sites. It uses ultra-fast AI inference to monitor live CCTV feeds for Personal Protective Equipment (PPE) compliance and authenticates construction workers on-site using high-speed Facial Recognition.

## 🚀 Key Features

*   **Lightning-Fast Facial Recognition**: Upgraded from deep-learning backend to a highly optimized `dlib` C++ HOG architecture for instantaneous sub-30ms face identification in pure RAM.
*   **Real-time AI CCTV Feed**: High-performance, multi-threaded MJPEG streaming running YOLOv8 object detection without artificial framerate caps.
*   **Dynamic Resource Management**: AI camera feeds automatically suspend processing and release hardware resources the moment you switch browser tabs, ensuring 0% idle CPU usage.
*   **Full Worker Dashboard**: Comprehensive Node.js/Express backend with a beautiful frontend to manage employee details, attendance, and safety metrics.

## 🛠️ Technology Stack

*   **Frontend**: HTML, CSS (Modern Glassmorphism UI), Vanilla JavaScript
*   **Backend Server**: Node.js, Express, MySQL (Database)
*   **AI Engine**: Python 3.10, Flask (Microservices)
*   **Computer Vision**: OpenCV, Ultralytics YOLOv8, `face_recognition`, `dlib`

## ⚙️ Installation & Setup

### 1. Database Setup
1. Ensure you have **MySQL** or **XAMPP** running.
2. Create a database named `construction_safety`.
3. Import the provided `construction_safety.sql` file to populate the tables.

### 2. Node.js Backend Setup
Open a terminal in the root directory and install the Node dependencies:
```bash
npm install
npm run dev
```
*The web dashboard will start on `http://localhost:4000`.*

### 3. Python AI Engine Setup
It is highly recommended to use a virtual environment (`.venv`) for the AI module.
```bash
cd Face_recognition
python -m venv .venv
.\.venv\Scripts\activate
```

**⚠️ Important Windows Note for `dlib`:**
To avoid complex Visual Studio C++ Compiler errors when installing the facial recognition libraries on Windows, please install the pre-compiled `dlib` wheel and downgrade `numpy` BEFORE installing `requirements.txt`:
```bash
# Force downgrade numpy to 1.x to maintain C++ ABI compatibility with dlib
pip install numpy==1.26.4

# Download and install the precompiled dlib wheel for Python 3.10
Invoke-WebRequest -Uri "https://github.com/Murtaza-Saeed/Dlib-Precompiled-Wheels-for-Python-on-Windows-x64-Easy-Installation/raw/main/dlib-19.22.99-cp310-cp310-win_amd64.whl" -OutFile "dlib.whl"
pip install dlib.whl

# Install the remaining requirements
pip install -r requirements.txt
```

## 🖥️ Running the Application

Once everything is installed, you need to run three separate services to power the full architecture:

1.  **Node Dashboard**: Run `npm run dev` in the root folder.
2.  **Face Recognition API**: Inside the `Face_recognition` folder with your `.venv` active, run `python app.py`. This boots the fast Auth API on port 5000.
3.  **CCTV AI Server**: Inside the `Face_recognition` folder with your `.venv` active, run `python intelligent_cctv.py`. This starts the YOLOv8 and Face Tracking feed on port 5001.

## 📂 Project Architecture
*   `/backend` - Node.js routes and server configurations.
*   `/frontend` - HTML/JS dashboards (login, employee management, CCTV).
*   `/Face_recognition` - Python microservices and neural network models (`best.pt`).
*   `/uploads` - Database storage for employee photos.

## 👤 Default Demo Credentials
*   **Admin**: `admin` / `admin123`
*   **Supervisor**: `supervisor` / `super123`
*   **Worker**: `worker1` / `worker123`
