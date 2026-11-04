"""Face recognition using face_recognition (dlib) — the Phase 1 decision.

Separated from face_detector.py on purpose: detection finds *where* a
face is, recognition decides *whose* face it is. The matching math
(compare_to_known) is pure numpy with no dlib dependency, so it's
unit-testable without the heavier library installed — only encoding
actually needs face_recognition/dlib.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from config.settings import RECOGNITION_TOLERANCE_DEFAULT
from core.face_detector import BoundingBox
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Match:
    student_id: str | None  # None means unknown
    distance: float | None
    confidence: float | None  # 1 - distance, clamped to [0, 1]; None if unknown

    @property
    def is_known(self) -> bool:
        return self.student_id is not None


def _box_to_face_recognition_format(box: BoundingBox) -> tuple[int, int, int, int]:
    """Convert our (x, y, w, h) box to face_recognition's (top, right, bottom, left)."""
    top, left = box.y, box.x
    bottom, right = box.y + box.h, box.x + box.w
    return (top, right, bottom, left)


class FaceRecognizer:
    """Encodes detected faces via face_recognition. Matching lives in compare_to_known()."""

    def __init__(self) -> None:
        # Imported lazily so the rest of the app can run (and be tested)
        # even on a machine where dlib/face_recognition isn't installed yet.
        try:
            import face_recognition  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "face_recognition is not installed. It requires dlib, which "
                "needs a C++ build toolchain (CMake) to compile — see "
                "requirements.txt. Then `pip install face_recognition`."
            ) from exc
        self._face_recognition = face_recognition

    def encode_faces(self, rgb_image: np.ndarray, boxes: list[BoundingBox]) -> list[np.ndarray | None]:
        """Return one 128-d encoding per box (None for a box that fails to encode),
        in the same order as boxes."""
        h, w = rgb_image.shape[:2]
        # dlib expects a contiguous uint8 array; cv2.cvtColor already returns
        # one, but this guards against a caller passing a sliced/view array.
        rgb_image = np.ascontiguousarray(rgb_image)

        results: list[np.ndarray | None] = []
        for box in boxes:
            top, right, bottom, left = _box_to_face_recognition_format(box)
            # Extra safety net beyond FaceDetector's own MIN_FACE_SIZE_PX
            # filter: a location outside the image or with near-zero area
            # is exactly what can crash dlib natively rather than raising
            # a catchable Python exception, so we refuse to hand it over.
            if not (0 <= left < right <= w and 0 <= top < bottom <= h):
                logger.warning("Skipping out-of-bounds/degenerate box %s for a %dx%d image", box, w, h)
                results.append(None)
                continue

            location = [(top, right, bottom, left)]
            encodings = self._face_recognition.face_encodings(rgb_image, known_face_locations=location)
            results.append(encodings[0] if encodings else None)
        return results

    def encode_single_image(self, rgb_image: np.ndarray) -> np.ndarray | None:
        """Encode the (assumed single, pre-cropped) face in a registration image."""
        encodings = self._face_recognition.face_encodings(rgb_image)
        return encodings[0] if encodings else None


def compare_to_known(
    encoding: np.ndarray,
    known_embeddings: dict[str, np.ndarray],
    tolerance: float = RECOGNITION_TOLERANCE_DEFAULT,
) -> Match:
    """Find the closest known student to `encoding`, or report unknown.

    Pure numpy — the same Euclidean-distance math face_recognition uses
    internally — so this is testable without dlib installed.
    """
    if not known_embeddings:
        return Match(student_id=None, distance=None, confidence=None)

    student_ids = list(known_embeddings.keys())
    vectors = np.array([known_embeddings[sid] for sid in student_ids])
    distances = np.linalg.norm(vectors - encoding, axis=1)

    best_idx = int(np.argmin(distances))
    best_distance = float(distances[best_idx])

    if best_distance > tolerance:
        return Match(student_id=None, distance=best_distance, confidence=None)

    confidence = max(0.0, min(1.0, 1.0 - best_distance))
    return Match(student_id=student_ids[best_idx], distance=best_distance, confidence=confidence)
