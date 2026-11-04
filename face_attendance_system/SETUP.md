# Setup on a new device

1. Install Miniconda: https://docs.conda.io/en/latest/miniconda.html
   (conda supplies a prebuilt dlib for Python 3.13, which plain pip cannot.)
2. Open the Miniconda/Anaconda Prompt, cd into this folder, then:

       conda env create -f environment.yml
       conda activate face-attendance

   If the face_recognition_models step fails, run it by hand:

       pip install git+https://github.com/ageitgey/face_recognition_models

3. Download the face detector model files (only if models/ has no .caffemodel):

       python scripts/download_models.py

4. Check everything imports (a pkg_resources deprecation warning is harmless):

       python -c "import dlib, cv2, face_recognition, customtkinter; print('OK')"

5. Run the app, always from the activated environment:

       python main.py

   In the app, Settings -> "Run diagnostics" checks each dependency.

## Version pins and why
- opencv-python < 5.0   OpenCV 5 removed cv2.dnn.readNetFromCaffe, which the detector uses.
- setuptools < 82       setuptools 82 removed pkg_resources, which face_recognition_models imports.
- dlib via conda-forge  PyPI has no prebuilt dlib wheel for Python 3.13.
