"""Rebuilds embeddings for one student or all students, in a separate
process from the GUI. See recognize_worker.py's docstring for why.

Progress is genuinely saved incrementally: Trainer.train_student()
writes each student's embedding to the database the moment it
succeeds, so if this process crashes partway through train_all(), the
students already processed keep their new embeddings — only the
remainder need a retry.

Usage: python scripts/train_worker.py <student_id | __all__>
Prints one JSON object to stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.trainer import Trainer  # noqa: E402
from database.db_manager import DBManager  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "Usage: train_worker.py <student_id | __all__>"}))
        return 1

    target = sys.argv[1]

    try:
        db = DBManager()
        trainer = Trainer(db)
        if target == "__all__":
            results = trainer.train_all()
        else:
            results = [trainer.train_student(target)]
    except (FileNotFoundError, ImportError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    payload = {
        "results": [
            {
                "student_id": r.student_id,
                "images_used": r.images_used,
                "images_skipped": r.images_skipped,
                "success": r.success,
                "message": r.message,
            }
            for r in results
        ]
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
