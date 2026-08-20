@echo off
echo Starting Dual-Threaded Artificial Intelligence CCTV MJPEG Server...
cd Face_recognition

:: Launch the main Facial Recognition API in a new background window using the virtual environment python exactly
start "Facial Recognition API" cmd /c ".venv\Scripts\python.exe app.py"

:: Launch the Intelligent CCTV Streamer in this current window using the virtual environment python exactly
.venv\Scripts\python.exe intelligent_cctv.py
pause