# 🏗️ Construction Site Safety Management System

An advanced, AI-powered computer vision platform designed to ensure safety and compliance on construction sites. This system integrates **Real-Time CCTV Streaming**, **Offline Video Analysis**, **PPE (Personal Protective Equipment) Detection**, and **Facial Recognition** into a unified dashboard for administrators, supervisors, and workers.

---

## ✨ Key Features
- **🚨 Real-Time PPE Detection**: Uses a custom-trained **YOLOv8** model to scan live RTSP CCTV feeds for Hardhats, Safety Vests, Masks, Goggles, and Gloves. It also detects critical dangers like workers falling.
- **👤 Worker Face Recognition**: Scans the CCTV feeds and uploaded videos to automatically identify employees using `dlib/face_recognition`, attaching their names directly to their bounding boxes.
- **🎥 Offline Video Analysis**: Allows supervisors to upload recorded drone or handheld footage. The Python microservice processes the video frame-by-frame (with heavy CPU optimizations) and returns a fully annotated `.mp4` video with compliance statistics.
- **👥 Multi-Role Dashboard**: A Node.js backend providing secure access for Admins, Supervisors, and Workers.
- **💰 Automated Salary & Fines**: Tracks safety compliance across the site and automatically calculates penalties for workers found without proper gear.

---

## 🛠️ Tech Stack
- **Frontend**: HTML5, Vanilla CSS (Glassmorphism design), JavaScript.
- **Backend**: Node.js, Express.js.
- **Database**: MySQL.
- **Computer Vision (AI)**: Python, PyTorch, OpenCV, Ultralytics YOLOv8, Face_Recognition.
- **Media Processing**: FFmpeg (via `imageio-ffmpeg`).

---

## 🚀 Setup Instructions (A to Z)

If you are setting this project up on a new PC, follow these exact steps:

### 1. Prerequisites
You must have the following installed on your machine:
- [Node.js](https://nodejs.org/) (v16+)
- [Python](https://www.python.org/downloads/) (v3.9 - v3.11)
- [MySQL Server](https://dev.mysql.com/downloads/mysql/) (v8+)

### 2. Database Setup
1. Open your MySQL client (e.g., MySQL Workbench).
2. Create a new database named `construction_safety`.
3. Import the provided `construction_safety.sql` file into the database to set up all tables and default users.

### 3. Node.js Backend Setup
1. Open a terminal in the project root directory.
2. Install the Node modules:
   ```bash
   npm install
   ```
3. Create a `.env` file in the root directory and add your database credentials:
   ```env
   DB_HOST=localhost
   DB_USER=root
   DB_PASSWORD=your_mysql_password
   DB_NAME=construction_safety
   API_PORT=4000
   ```

### 4. Python AI Setup
1. Open a terminal in the `Face_recognition` folder.
2. Create a Python virtual environment:
   ```bash
   python -m venv .venv
   ```
3. Activate the virtual environment:
   - **Windows**: `.venv\Scripts\activate`
   - **Mac/Linux**: `source .venv/bin/activate`
4. Install the required AI libraries:
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: Installing `dlib` and `face_recognition` may require CMake and Visual Studio C++ Build Tools on Windows).*

### 5. Setting up the Employee Face Database
To allow the AI to recognize your workers, you must add their photos to the database:
1. Go to `Face_recognition/employees/`.
2. Create a new folder named exactly after the worker (e.g., `John Doe`).
3. Place a clear `.jpg` or `.png` photo of their face inside that folder.

### 6. Running the Project
For Windows users, simply double-click the `start-streaming.bat` file in the root folder. It will automatically spin up the Node.js server, the CCTV streamer, and the Video Processing microservice.

**To run it manually in separate terminals:**
- **Terminal 1 (Node.js):** `npm run dev`
- **Terminal 2 (CCTV API):** `Face_recognition\.venv\Scripts\python.exe Face_recognition\intelligent_cctv.py`
- **Terminal 3 (Video API):** `Face_recognition\.venv\Scripts\python.exe Face_recognition\video_processor.py`

---

## 🔑 Demo Credentials
Once the server is running at `http://localhost:4000`, you can log in using the default credentials:

| Role | Username | Password |
| :--- | :--- | :--- |
| **Admin** | admin | admin123 |
| **Supervisor** | supervisor | super123 |
| **Worker** | worker1 | worker123 |

---

*Built for advanced AI-driven construction safety.*
