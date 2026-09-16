@echo off
echo ==========================================================
echo  Intelligent Construction Safety - Full System Startup
echo ==========================================================
echo.
cd Face_recognition

:: Launch Face Recognition Auth API (Port 5000)
echo [1/3] Starting Face Recognition API (Port 5000)...
start "Face Recognition API - Port 5000" cmd /c ".venv\Scripts\python.exe app.py"
timeout /t 2 /nobreak >nul

:: Launch Video Analysis Processor (Port 5002)
echo [2/3] Starting Video Analysis Processor (Port 5002)...
start "Video Analysis Processor - Port 5002" cmd /c ".venv\Scripts\python.exe video_processor.py"
timeout /t 2 /nobreak >nul

:: Launch Intelligent CCTV Streamer (Port 5001) - runs in this window
echo [3/3] Starting Intelligent CCTV Streamer (Port 5001)...
echo.
echo All services started! Dashboard: http://localhost:4000
echo (Start Node.js dashboard separately with: npm run dev)
echo.
.venv\Scripts\python.exe intelligent_cctv.py
pause