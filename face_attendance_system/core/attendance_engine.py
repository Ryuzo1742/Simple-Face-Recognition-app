"""Attendance engine: runs one classroom photo through detection and
recognition, and marks attendance for every match.

This is the module the Recognize page calls. It doesn't touch SQL or
OpenCV/dlib internals directly — it composes FaceDetector,
FaceRecognizer, and DBManager.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from config.settings import RECOGNITION_TOLERANCE_DEFAULT
from core.face_detector import BoundingBox, FaceDetector
from core.face_recognizer import FaceRecognizer, compare_to_known
from database.db_manager import DBManager
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RecognitionOutcome:
    box: BoundingBox
    student_id: str | None
    name: str | None
    confidence: float | None
    attendance_marked: bool  # True only if this call newly marked them present


class AttendanceEngine:
    """Runs detection + recognition + attendance marking for one photo."""

    def __init__(self, db: DBManager) -> None:
        self.db = db
        logger.info("Loading face detector...")
        self.detector = FaceDetector()
        logger.info("Face detector loaded")
        logger.info("Loading face recognizer (imports dlib via face_recognition)...")
        self.recognizer = FaceRecognizer()
        logger.info("Face recognizer loaded")

    def process_image(
        self, bgr_image: np.ndarray, period: int, tolerance: float = RECOGNITION_TOLERANCE_DEFAULT
    ) -> list[RecognitionOutcome]:
        """Detect every face, identify who it is, and mark attendance for
        each match, for the given period (Hour 1-5).

        A student appearing twice in the same photo (or already marked
        Present earlier for this exact period) is only counted once —
        set_attendance()'s UNIQUE(student_id, att_date, period)
        constraint enforces that at the DB level, so this loop just
        reports whether *this call* was the one that marked them.
        """
        boxes = self.detector.detect(bgr_image)
        if not boxes:
            return []

        rgb_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        encodings = self.recognizer.encode_faces(rgb_image, boxes)
        known_embeddings = self.db.get_all_embeddings()
        student_names = {s.student_id: s.name for s in self.db.list_students()}

        outcomes: list[RecognitionOutcome] = []
        already_marked_this_call: set[str] = set()

        for box, encoding in zip(boxes, encodings):
            if encoding is None:
                outcomes.append(RecognitionOutcome(box, None, None, None, False))
                continue

            match = compare_to_known(encoding, known_embeddings, tolerance=tolerance)

            if not match.is_known:
                outcomes.append(RecognitionOutcome(box, None, None, None, False))
                continue

            newly_marked = False
            if match.student_id not in already_marked_this_call:
                newly_marked = self.db.mark_attendance(match.student_id, period=period)
                already_marked_this_call.add(match.student_id)

            outcomes.append(RecognitionOutcome(
                box=box,
                student_id=match.student_id,
                name=student_names.get(match.student_id, match.student_id),
                confidence=match.confidence,
                attendance_marked=newly_marked,
            ))

        logger.info(
            "Processed photo for period %d: %d faces, %d recognized, %d newly marked present",
            period,
            len(boxes),
            sum(1 for o in outcomes if o.student_id is not None),
            sum(1 for o in outcomes if o.attendance_marked),
        )
        return outcomes
