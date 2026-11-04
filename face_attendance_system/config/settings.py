"""
Central configuration for the Face Recognition Attendance System.

Keeping every path, threshold, and tunable constant in one module means
no other file should ever hard-code a path or magic number directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from typing import NamedTuple, Optional

# --- Base paths -------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "dataset"
MODELS_DIR = BASE_DIR / "models"
EXPORTS_DIR = BASE_DIR / "exports"
LOGS_DIR = BASE_DIR / "logs"
DB_PATH = BASE_DIR / "database" / "attendance.db"
EMBEDDINGS_CACHE = BASE_DIR / "database" / "embeddings_cache.pkl"

# --- Registration -------------------------------------------------------
IMAGES_PER_STUDENT_MIN = 30
IMAGES_PER_STUDENT_MAX = 50

# --- Recognition -------------------------------------------------------
# Lower = stricter match. face_recognition's default distance threshold.
RECOGNITION_TOLERANCE_DEFAULT = 0.5
RECOGNITION_TOLERANCE_MIN = 0.3
RECOGNITION_TOLERANCE_MAX = 0.7

# --- Detection model files (OpenCV DNN) ---------------------------------
DETECTOR_PROTOTXT = MODELS_DIR / "deploy.prototxt"
DETECTOR_WEIGHTS = MODELS_DIR / "res10_300x300_ssd_iter_140000.caffemodel"
DETECTOR_CONFIDENCE_THRESHOLD = 0.6
MIN_FACE_SIZE_PX = 40  # boxes smaller than this are dropped — see face_detector.detect()

# --- App metadata -------------------------------------------------------
APP_NAME = "Attendance"
APP_VERSION = "0.1.0"


class Period(NamedTuple):
    """One class period. Attendance is tracked per period, not per day."""

    number: int
    label: str
    start: time
    end: time


# Attendance is taken once per period, not once per day — a student can
# be Present in Hour 2 and Absent in Hour 4 on the same date. Edit this
# list to match your school's actual period timings.
PERIODS: list[Period] = [
    Period(1, "Hour 1", time(8, 30), time(9, 20)),
    Period(2, "Hour 2", time(9, 25), time(10, 15)),
    Period(3, "Hour 3", time(10, 20), time(11, 10)),
    Period(4, "Hour 4", time(11, 50), time(12, 35)),
    Period(5, "Hour 5", time(12, 40), time(13, 30)),
]


def period_by_number(number: int) -> Optional[Period]:
    """Look up a period by its number (1-5). Returns None if out of range."""
    for period in PERIODS:
        if period.number == number:
            return period
    return None


def period_label(number: int) -> str:
    """Display label for a period number, falling back gracefully for old data."""
    period = period_by_number(number)
    return period.label if period else f"Hour {number}"


def current_period(now: Optional[datetime] = None) -> Optional[Period]:
    """The period active right now, or None if outside every period's window
    (e.g. lunch break, before/after school). Used to default the Recognize
    page's Hour selector to whichever period is actually in progress.
    """
    now = now or datetime.now()
    current_time = now.time()
    for period in PERIODS:
        if period.start <= current_time <= period.end:
            return period
    return None


@dataclass(frozen=True)
class AppTheme:
    """Design tokens for the CustomTkinter GUI. See gui/theme.py for usage."""

    appearance_mode: str = "light"  # "light" | "dark" | "system"
    color_theme: str = "blue"  # base CTk theme, overridden by custom tokens


def ensure_directories() -> None:
    """Create all required directories on first run if they don't exist."""
    for directory in (DATASET_DIR, MODELS_DIR, EXPORTS_DIR, LOGS_DIR, DB_PATH.parent):
        directory.mkdir(parents=True, exist_ok=True)
