"""Webcam capture manager used by the registration flow.

Wraps cv2.VideoCapture behind start/read/release so the GUI never
touches OpenCV video I/O directly, and provides a save_face_crop
helper that crops to the detected face with a margin, checks basic
sharpness, and writes numbered images to dataset/<student_id>/.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from config.settings import DATASET_DIR
from core.face_detector import BoundingBox
from utils.logger import get_logger

logger = get_logger(__name__)

# Reject obviously blurry captures (motion blur, out of focus) using the
# variance of the Laplacian — a cheap, well-established sharpness proxy.
BLUR_VARIANCE_THRESHOLD = 60.0
FACE_MARGIN_RATIO = 0.35  # extra context around the detected box
SAVE_SIZE = (300, 300)


class CameraCapture:
    """Thin wrapper around a single webcam device."""

    def __init__(self, device_index: int = 0) -> None:
        self.device_index = device_index
        self._cap: cv2.VideoCapture | None = None

    def start(self) -> None:
        self._cap = cv2.VideoCapture(self.device_index)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"Could not open webcam at index {self.device_index}. "
                "Check that a camera is connected and not in use by another app."
            )
        logger.info("Camera %d opened", self.device_index)

    def read_frame(self) -> np.ndarray | None:
        if self._cap is None:
            raise RuntimeError("Camera not started — call start() first.")
        ok, frame = self._cap.read()
        return frame if ok else None

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Camera %d released", self.device_index)

    def __enter__(self) -> "CameraCapture":
        self.start()
        return self

    def __exit__(self, *_exc) -> None:
        self.release()


def is_sharp_enough(gray_crop: np.ndarray) -> bool:
    """True if the crop isn't blurry, using Laplacian variance."""
    variance = cv2.Laplacian(gray_crop, cv2.CV_64F).var()
    return variance >= BLUR_VARIANCE_THRESHOLD


def crop_with_margin(frame: np.ndarray, box: BoundingBox) -> np.ndarray:
    """Crop the detected face with extra margin, resized to a fixed size."""
    h, w = frame.shape[:2]
    mx = int(box.w * FACE_MARGIN_RATIO)
    my = int(box.h * FACE_MARGIN_RATIO)
    x1, y1 = max(0, box.x - mx), max(0, box.y - my)
    x2, y2 = min(w, box.x + box.w + mx), min(h, box.y + box.h + my)
    crop = frame[y1:y2, x1:x2]
    return cv2.resize(crop, SAVE_SIZE)


def save_face_crop(student_id: str, frame: np.ndarray, box: BoundingBox, index: int) -> Path | None:
    """Crop, quality-check, and save one registration image.

    Returns the saved path, or None if the frame was rejected for being
    too blurry (the caller should simply retry on the next frame).
    """
    crop = crop_with_margin(frame, box)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    if not is_sharp_enough(gray):
        return None

    student_dir = DATASET_DIR / student_id
    student_dir.mkdir(parents=True, exist_ok=True)
    path = student_dir / f"img_{index:03d}.jpg"
    cv2.imwrite(str(path), crop)
    return path


def count_saved_images(student_id: str) -> int:
    student_dir = DATASET_DIR / student_id
    if not student_dir.exists():
        return 0
    return len(list(student_dir.glob("img_*.jpg")))
