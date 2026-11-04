# Face detector model files

The Phase 1 decision was OpenCV's DNN (SSD + reduced ResNet-10) face
detector. It needs two small files that aren't bundled with
`opencv-python` and must be downloaded once, on a machine with internet
access, before webcam capture or recognition will run.

Download these two files into this `models/` folder:

| File | Source |
|---|---|
| `deploy.prototxt` | https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt |
| `res10_300x300_ssd_iter_140000.caffemodel` | https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel |

Or just run the helper script from the project root once you have the
`requests` package installed:

```bash
python scripts/download_models.py
```

`core/face_detector.py` raises a clear `FileNotFoundError` pointing back
to this file if either model is missing, so the app fails fast with a
useful message rather than crashing deep inside OpenCV.
