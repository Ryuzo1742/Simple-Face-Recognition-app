"""Builds embeddings from registration images.

For each student, every captured image under dataset/<student_id>/ is
detected, encoded, and the resulting 128-d vectors are averaged into a
single embedding — averaging over 30-50 angles is more robust to any
one bad crop than trusting a single image, and keeps get_embedding()
simple (one vector per student, matching the Phase 2 schema).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from config.settings import DATASET_DIR
from core.face_detector import FaceDetector
from core.face_recognizer import FaceRecognizer
from database.db_manager import DBManager
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TrainResult:
    student_id: str
    images_used: int
    images_skipped: int
    success: bool
    message: str


class Trainer:
    """Rebuilds one or all students' embeddings from their dataset images."""

    def __init__(self, db: DBManager) -> None:
        self.db = db
        self._detector: FaceDetector | None = None
        self._recognizer: FaceRecognizer | None = None

    def _ensure_engines(self) -> None:
        if self._detector is None:
            logger.info("Loading face detector...")
            self._detector = FaceDetector()
            logger.info("Face detector loaded")
        if self._recognizer is None:
            logger.info("Loading face recognizer (imports dlib via face_recognition)...")
            self._recognizer = FaceRecognizer()
            logger.info("Face recognizer loaded")

    def train_student(self, student_id: str) -> TrainResult:
        student_dir = DATASET_DIR / student_id
        image_paths = sorted(student_dir.glob("img_*.jpg"))

        if not image_paths:
            return TrainResult(student_id, 0, 0, False, "No captured images found.")

        self._ensure_engines()
        vectors: list[np.ndarray] = []
        skipped = 0

        for path in image_paths:
            logger.info("Training %s: processing %s", student_id, path.name)
            frame = cv2.imread(str(path))
            if frame is None:
                skipped += 1
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            box = self._detector.largest_face(frame)
            if box is None:
                skipped += 1
                continue

            encodings = self._recognizer.encode_faces(rgb, [box])
            encoding = encodings[0] if encodings else None
            if encoding is None:
                skipped += 1
                continue
            vectors.append(encoding)

        if not vectors:
            return TrainResult(
                student_id, 0, skipped, False,
                "None of the captured images produced a usable encoding.",
            )

        averaged = np.mean(np.array(vectors), axis=0)
        self.db.save_embedding(student_id, averaged)
        logger.info("Trained %s on %d/%d images", student_id, len(vectors), len(image_paths))

        return TrainResult(
            student_id, len(vectors), skipped, True,
            f"Trained on {len(vectors)} of {len(image_paths)} images.",
        )

    def train_all(self, progress_callback=None) -> list[TrainResult]:
        """Retrain every registered student. progress_callback(done, total, result) is optional."""
        students = self.db.list_students()
        results: list[TrainResult] = []
        for i, student in enumerate(students, start=1):
            result = self.train_student(student.student_id)
            results.append(result)
            if progress_callback is not None:
                progress_callback(i, len(students), result)
        return results
