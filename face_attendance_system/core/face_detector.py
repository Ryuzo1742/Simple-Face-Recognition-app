"""Face detection using OpenCV's DNN (SSD + reduced ResNet-10) detector.

This is the Phase 1 decision: bundled with opencv-python's cv2.dnn
module, no separate heavy dependency, fast enough on CPU. See
models/README.md for the one-time model download step.
"""

from __future__ import annotations

from typing import NamedTuple

import cv2
import numpy as np

from config.settings import DETECTOR_CONFIDENCE_THRESHOLD, DETECTOR_PROTOTXT, DETECTOR_WEIGHTS, MIN_FACE_SIZE_PX
from utils.logger import get_logger

logger = get_logger(__name__)


class BoundingBox(NamedTuple):
    """A detected face region in pixel coordinates, top-left origin."""

    x: int
    y: int
    w: int
    h: int
    confidence: float


class FaceDetector:
    """Wraps the OpenCV DNN face detector behind a simple detect() call."""

    def __init__(self) -> None:
        if not (DETECTOR_PROTOTXT.exists() and DETECTOR_WEIGHTS.exists()):
            raise FileNotFoundError(
                "Face detector model files are missing under models/. "
                "See models/README.md for the one-time download step "
                "(or run `python scripts/download_models.py`)."
            )
        self._net = cv2.dnn.readNetFromCaffe(str(DETECTOR_PROTOTXT), str(DETECTOR_WEIGHTS))
        logger.info("Loaded OpenCV DNN face detector")

    def detect(self, frame: np.ndarray) -> list[BoundingBox]:
        """Return a bounding box for every face found in a BGR frame.

        Boxes are clamped to the frame bounds and dropped below
        MIN_FACE_SIZE_PX. That floor isn't just about detection quality —
        handing dlib's encoder a near-degenerate crop (a sliver a few
        pixels wide, common on distant/cut-off faces in classroom photos)
        can trigger a native crash that bypasses Python's exception
        handling entirely, so this filter is what actually keeps the app
        from vanishing mid-recognition.
        """
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0)
        )
        self._net.setInput(blob)
        detections = self._net.forward()

        boxes: list[BoundingBox] = []
        for i in range(detections.shape[2]):
            confidence = float(detections[0, 0, i, 2])
            if confidence < DETECTOR_CONFIDENCE_THRESHOLD:
                continue
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            x1, y1, x2, y2 = box.astype(int)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if (x2 - x1) < MIN_FACE_SIZE_PX or (y2 - y1) < MIN_FACE_SIZE_PX:
                continue
            # box.astype(int) produces numpy.int64, not a native Python
            # int. They behave the same in arithmetic, which is why this
            # slipped through earlier testing, but json.dumps() rejects
            # numpy scalar types outright — cast explicitly here so every
            # BoundingBox this returns is always JSON-serializable.
            boxes.append(BoundingBox(int(x1), int(y1), int(x2 - x1), int(y2 - y1), confidence))
        return boxes

    def largest_face(self, frame: np.ndarray) -> BoundingBox | None:
        """Convenience for capture flows: assume one subject, take the biggest box."""
        boxes = self.detect(frame)
        if not boxes:
            return None
        return max(boxes, key=lambda b: b.w * b.h)
