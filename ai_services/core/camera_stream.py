"""
CameraStream — Background Frame Capture Engine
===============================================
Supports two ingestion modes:
  1. Local webcam / USB camera via OpenCV VideoCapture.
  2. IP / RTSP camera via low-latency FFmpeg subprocess with
     a non-blocking single-slot queue (always delivers latest frame).

Usage:
    stream = CameraStream()
    stream.set_source(0)          # or "rtsp://..."
    stream.start()
    frame = stream.get_frame()    # np.ndarray (BGR) or None
    stream.stop()
"""

import os
import queue
import subprocess
import threading
import time
from typing import Optional, Union

import cv2
import imageio_ffmpeg
import numpy as np

# Default frame size (1280×720 = HD)
DEFAULT_WIDTH  = 1280
DEFAULT_HEIGHT = 720


class CameraStream:
    """
    Continuous background frame grabber supporting local webcam and RTSP/IP cameras.
    Thread-safe. Always returns the most recent frame (stale frames are dropped).
    """

    def __init__(self, default_source: Union[int, str] = 0):
        self._source: Optional[Union[int, str]] = default_source
        self._active = False
        self._frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()

        self._cam_thread: Optional[threading.Thread] = None
        self._ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

        # RTSP-specific: frame queue with maxsize=1 (drop stale frames)
        self._frame_queue: queue.Queue = queue.Queue(maxsize=1)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_source(self, source: Union[int, str]):
        """Change camera source. Takes effect on the next start() or immediately if running."""
        self._source = source

    def start(self):
        """Activate frame capture. Non-blocking — capture runs in a background daemon thread."""
        if self._active:
            return
        # Wait for any previously running thread to finish (up to 1 second)
        if self._cam_thread is not None and self._cam_thread.is_alive():
            self._cam_thread.join(timeout=1.0)
        self._active = True
        self._cam_thread = threading.Thread(target=self._camera_worker, daemon=True)
        self._cam_thread.start()

    def stop(self):
        """Deactivate frame capture and release all camera resources."""
        self._active = False
        with self._frame_lock:
            self._frame = self._make_standby_frame()

    def get_frame(self) -> Optional[np.ndarray]:
        """Return the latest camera frame (BGR numpy array), or None if not yet available."""
        with self._frame_lock:
            return self._frame

    @property
    def is_active(self) -> bool:
        return self._active

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _make_standby_frame(message: str = "CAMERA STANDBY (TAB INACTIVE)") -> np.ndarray:
        frame = np.zeros((DEFAULT_HEIGHT, DEFAULT_WIDTH, 3), dtype=np.uint8)
        cv2.putText(frame, message, (200, DEFAULT_HEIGHT // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (150, 150, 150), 2)
        return frame

    @staticmethod
    def _is_rtsp(source) -> bool:
        return isinstance(source, str) and source.lower().startswith("rtsp")

    # ── Background worker ─────────────────────────────────────────────────────

    def _camera_worker(self):
        """Main loop: manages connection, reconnection, and frame delivery."""
        current_source = None
        cap = None
        pipe = None
        pipe_reader_thread = None

        while self._active:
            source = self._source

            # ── Source changed or connection lost: reconnect ──────────────────
            if source != current_source or (pipe is None and cap is None):
                # Tear down old connection
                if cap:
                    cap.release()
                    cap = None
                if pipe:
                    try:
                        pipe.kill()
                    except Exception:
                        pass
                    pipe = None

                current_source = source

                if source is None:
                    with self._frame_lock:
                        self._frame = self._make_standby_frame()
                    time.sleep(0.5)
                    continue

                if self._is_rtsp(source):
                    pipe = self._open_rtsp(source)
                    if pipe:
                        pipe_reader_thread = self._start_pipe_reader(pipe)
                    else:
                        self._set_offline_frame()
                        time.sleep(2)
                        continue
                else:
                    cap = self._open_webcam(source)
                    if not cap:
                        self._set_offline_frame()
                        time.sleep(2)
                        continue

            # ── Consume frames ────────────────────────────────────────────────
            if pipe:
                if pipe.poll() is not None:
                    # FFmpeg process died
                    print("[INFO] FFmpeg process ended. Reconnecting...")
                    pipe = None
                    continue
                try:
                    raw = self._frame_queue.get(timeout=0.1)
                    frame = np.frombuffer(raw, dtype="uint8").reshape(
                        (DEFAULT_HEIGHT, DEFAULT_WIDTH, 3)
                    ).copy()
                    with self._frame_lock:
                        self._frame = frame
                except queue.Empty:
                    pass  # FFmpeg is alive but queue is empty — just wait

            elif cap and cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    with self._frame_lock:
                        self._frame = frame
                else:
                    time.sleep(0.01)
            else:
                # Connection lost mid-run
                cap = None
                pipe = None
                self._set_offline_frame()
                time.sleep(2)

        # ── Cleanup on stop() ─────────────────────────────────────────────────
        if cap:
            cap.release()
        if pipe:
            try:
                pipe.kill()
            except Exception:
                pass

    def _open_webcam(self, source: int) -> Optional[cv2.VideoCapture]:
        """Open a local webcam via OpenCV. Returns VideoCapture or None on failure."""
        print(f"[INFO] Launching Local Webcam Capture (Device {source})...")
        cap = cv2.VideoCapture(source)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, DEFAULT_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, DEFAULT_HEIGHT)
        if not cap.isOpened():
            print(f"[ERROR] Cannot open webcam {source}.")
            return None
        return cap

    def _open_rtsp(self, source: str) -> Optional[subprocess.Popen]:
        """
        Launch FFmpeg subprocess for low-latency RTSP ingestion.
        Returns Popen process or None on launch failure.
        """
        frame_size = DEFAULT_WIDTH * DEFAULT_HEIGHT * 3
        ffmpeg_cmd = [
            self._ffmpeg_path,
            "-loglevel", "error",
            "-rtsp_transport", "tcp",
            "-timeout", "5000000",
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-nostdin",
            "-i", source,
            "-vf", f"scale={DEFAULT_WIDTH}:{DEFAULT_HEIGHT}",
            "-f", "image2pipe",
            "-pix_fmt", "bgr24",
            "-vcodec", "rawvideo",
            "-an", "-",
        ]
        print(f"[INFO] Launching FFmpeg RTSP capture: {source}")
        try:
            pipe = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=frame_size * 2,
            )
            # Log stderr in background
            def _log_stderr():
                while pipe and pipe.poll() is None:
                    line = pipe.stderr.readline()
                    if line:
                        print(f"[FFMPEG] {line.decode(errors='ignore').strip()}")
                    else:
                        break
            threading.Thread(target=_log_stderr, daemon=True).start()
            return pipe
        except Exception as e:
            print(f"[ERROR] FFmpeg launch error: {e}")
            return None

    def _start_pipe_reader(self, pipe: subprocess.Popen) -> threading.Thread:
        """Start a daemon thread that reads raw frames from FFmpeg stdout into the queue."""
        frame_size = DEFAULT_WIDTH * DEFAULT_HEIGHT * 3

        def _reader():
            while pipe and pipe.poll() is None:
                try:
                    data = pipe.stdout.read(frame_size)
                    if not data or len(data) != frame_size:
                        break
                    # Drop stale frame, keep only latest
                    if self._frame_queue.full():
                        try:
                            self._frame_queue.get_nowait()
                        except queue.Empty:
                            pass
                    self._frame_queue.put(data)
                except Exception:
                    break

        t = threading.Thread(target=_reader, daemon=True)
        t.start()
        return t

    def _set_offline_frame(self):
        with self._frame_lock:
            self._frame = self._make_standby_frame("CAMERA OFFLINE")
