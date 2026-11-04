"""Checks each recognition dependency separately, in an isolated process
— same crash-containment reasoning as the other workers, but here it's
the whole point: if one import crashes the process natively, we still
want to know every check that passed *before* it, to pinpoint exactly
which dependency is broken.

Prints the full JSON state after every single check (not just once at
the end), so if the process dies mid-run, whatever was printed last is
still the accurate list of what passed and what didn't.

Usage: python scripts/diagnostics_worker.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_checks: list[dict] = []


def _record(name: str, ok: bool, detail: str = "") -> None:
    _checks.append({"name": name, "ok": ok, "detail": detail})
    print(json.dumps({"checks": _checks}), flush=True)


def main() -> int:
    try:
        import cv2
        _record("OpenCV", True, f"version {cv2.__version__}")
    except Exception as exc:  # noqa: BLE001 — this is a diagnostic, report anything
        _record("OpenCV", False, str(exc))
        return 0

    try:
        from config.settings import DETECTOR_PROTOTXT, DETECTOR_WEIGHTS
        models_ok = DETECTOR_PROTOTXT.exists() and DETECTOR_WEIGHTS.exists()
        _record(
            "Face detector model files", models_ok,
            "" if models_ok else "Missing — see models/README.md",
        )
    except Exception as exc:  # noqa: BLE001
        _record("Face detector model files", False, str(exc))

    try:
        import numpy
        _record("NumPy", True, f"version {numpy.__version__}")
    except Exception as exc:  # noqa: BLE001
        _record("NumPy", False, str(exc))

    # The check that matters most: this is the exact import that can crash
    # natively on a broken dlib install (missing VC++ Redistributable,
    # wrong Python version/architecture for the wheel, etc.). If the
    # process dies here, everything printed above this point already
    # reached the caller — that's what pinpoints the failure.
    try:
        import face_recognition  # noqa: F401
        _record("face_recognition (dlib)", True, "Imported and loaded successfully")
    except Exception as exc:  # noqa: BLE001
        _record("face_recognition (dlib)", False, str(exc))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
