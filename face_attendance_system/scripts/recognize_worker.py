"""Runs detection + recognition + attendance marking for ONE photo, in a
separate process from the GUI.

Why a subprocess: dlib (via face_recognition) and OpenCV's DNN module
are native C/C++ libraries. If either hits a bad state — a malformed
model, an incompatible build, a corrupt image — the failure can be a
hard crash (segfault / access violation) that terminates the process
instantly, with no Python exception to catch. Running the risky work
here means that crash only takes down this worker; gui/recognize_page.py
launches it with subprocess.run() and reads the JSON result (or the
crash's exit code) without the main window ever going down.

Usage: python scripts/recognize_worker.py <image_path> <tolerance> <period>
Prints one JSON object to stdout. All logging goes to stderr/log file,
never stdout, so stdout stays parseable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: E402

from core.attendance_engine import AttendanceEngine  # noqa: E402
from database.db_manager import DBManager  # noqa: E402


def main() -> int:
    if len(sys.argv) != 4:
        print(json.dumps({"error": "Usage: recognize_worker.py <image_path> <tolerance> <period>"}))
        return 1

    image_path, tolerance_str, period_str = sys.argv[1], sys.argv[2], sys.argv[3]

    try:
        tolerance = float(tolerance_str)
    except ValueError:
        print(json.dumps({"error": f"Invalid tolerance value: {tolerance_str}"}))
        return 1

    try:
        period = int(period_str)
    except ValueError:
        print(json.dumps({"error": f"Invalid period value: {period_str}"}))
        return 1

    frame = cv2.imread(image_path)
    if frame is None:
        print(json.dumps({"error": f"Could not read image file: {image_path}"}))
        return 1

    try:
        db = DBManager()
        engine = AttendanceEngine(db)
        outcomes = engine.process_image(frame, period=period, tolerance=tolerance)
    except (FileNotFoundError, ImportError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    payload = {
        "outcomes": [
            {
                "x": o.box.x, "y": o.box.y, "w": o.box.w, "h": o.box.h,
                "student_id": o.student_id,
                "name": o.name,
                "confidence": o.confidence,
                "attendance_marked": o.attendance_marked,
            }
            for o in outcomes
        ]
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
