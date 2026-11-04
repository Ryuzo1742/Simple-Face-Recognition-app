"""Run once, on a machine with internet access, to fetch the OpenCV DNN
face detector model files into models/. See models/README.md for the
direct download links if you'd rather fetch them by hand.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import DETECTOR_PROTOTXT, DETECTOR_WEIGHTS  # noqa: E402

PROTOTXT_URL = "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt"
WEIGHTS_URL = "https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel"


def _download(url: str, dest: Path) -> None:
    import requests

    print(f"Downloading {dest.name} ...")
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(response.content)
    print(f"Saved to {dest}")


def main() -> None:
    _download(PROTOTXT_URL, DETECTOR_PROTOTXT)
    _download(WEIGHTS_URL, DETECTOR_WEIGHTS)
    print("Done. The face detector is ready to use.")


if __name__ == "__main__":
    main()
