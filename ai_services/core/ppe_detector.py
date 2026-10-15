import threading
from dataclasses import dataclass
from typing import List, Tuple, Optional
import cv2
import torch
from ultralytics import YOLO

from core.config import (
    MODEL_PATH, DEVICE, VIOLATIONS, HEAD_CLASSES,
    COLOR_VIOLATION, COLOR_SAFE, COLOR_NAME, FONT
)

@dataclass
class Detection:
    cls_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    is_violation: bool
    is_head: bool
    person_name: str = ""

    @property
    def center(self) -> Tuple[int, int]:
        x1, y1, x2, y2 = self.bbox
        return (x1 + x2) // 2, (y1 + y2) // 2


class PPEDetector:
    """Encapsulates YOLOv8 model loading, unloading, and thread-safe inference."""

    def __init__(self, model_path: str = MODEL_PATH, device=DEVICE):
        self.model_path = model_path
        self.device = device
        self._model: Optional[YOLO] = None
        self._lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        with self._lock:
            return self._model is not None

    def load(self):
        with self._lock:
            if self._model is None:
                print(f"[INFO] Loading YOLO model: {self.model_path}")
                self._model = YOLO(self.model_path)
                self._model.overrides['verbose'] = False
                print("[INFO] YOLO model loaded and ready.")

    def unload(self):
        with self._lock:
            if self._model is not None:
                print("[INFO] Unloading YOLO model to free memory...")
                del self._model
                self._model = None
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                print("[INFO] YOLO model unloaded. Memory freed.")

    def detect(self, frame, conf: float = 0.35, iou: float = 0.45, imgsz: int = 640) -> List[Detection]:
        """Runs inference inside torch.inference_mode() and returns structured detections."""
        with self._lock:
            local_model = self._model

        if local_model is None:
            return []

        detections: List[Detection] = []

        with torch.inference_mode():
            results = local_model(
                frame,
                imgsz=imgsz,
                conf=conf,
                iou=iou,
                agnostic_nms=True,
                device=self.device,
                verbose=False
            )

        for result in results:
            for box in result.boxes:
                cls_idx = int(box.cls)
                cls_name = local_model.names.get(cls_idx, str(cls_idx))
                conf_val = float(box.conf)
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                is_viol = cls_name in VIOLATIONS
                is_head = cls_name in HEAD_CLASSES

                detections.append(Detection(
                    cls_name=cls_name,
                    confidence=conf_val,
                    bbox=(x1, y1, x2, y2),
                    is_violation=is_viol,
                    is_head=is_head
                ))

        return detections

    @staticmethod
    def draw_overlays(frame, detections: List[Detection]):
        """Draws bounding boxes, labels, and worker names onto the frame."""
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            color = COLOR_VIOLATION if det.is_violation else COLOR_SAFE

            # Draw detection bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Draw PPE label (Class + Confidence)
            label = f"{det.cls_name} {det.confidence:.2f}"
            (tw, th), _ = cv2.getTextSize(label, FONT, 0.55, 1)
            cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
            cv2.putText(frame, label, (x1 + 2, y1 - 4), FONT, 0.55, (0, 0, 0), 1, cv2.LINE_AA)

            # Draw worker name above the box if identified
            if det.person_name and det.person_name not in ("", "Unknown Person"):
                (nw, nh), _ = cv2.getTextSize(det.person_name, FONT, 0.6, 2)
                cv2.rectangle(frame, (x1, y1 - th - nh - 20), (x1 + nw + 6, y1 - th - 10), (0, 0, 0), -1)
                cv2.putText(frame, det.person_name, (x1 + 3, y1 - th - 14), FONT, 0.6, COLOR_NAME, 2, cv2.LINE_AA)
