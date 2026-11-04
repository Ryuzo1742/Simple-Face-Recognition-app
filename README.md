# Face Recognition Attendance System

A desktop application that automates classroom attendance using face recognition.
A teacher uploads a group photo, and the system detects every face, identifies
registered students, and marks attendance for the selected hour.

## Features
- Register students with ~40 webcam photos from different angles
- Detect and recognize multiple faces in one classroom photo
- Unknown faces are labelled "Unknown"
- Hourly attendance across five periods per day, with the current hour picked automatically
- Manual Present/Absent toggle for students the photo missed
- Search and filter by name, ID, date, department and hour
- Export attendance to CSV
- Light and dark mode
- Works fully offline after installation

## Tech stack
| Area | Technology |
|---|---|
| Language | Python 3.13 |
| GUI | CustomTkinter |
| Face detection | OpenCV DNN (SSD with ResNet-10) |
| Face recognition | face_recognition (dlib), 128-d embeddings |
| Database | SQLite |

## How it works
1. Each student is registered with webcam photos, and their face encodings are averaged into one 128-d embedding.
2. For a class photo, faces are detected and each is compared to the stored embeddings by Euclidean distance.
3. A match within the tolerance (default 0.5) marks the student present for that hour. Otherwise the face is labelled Unknown.
4. The database allows one record per student, date and hour, so duplicates can't occur.

## Setup
See [SETUP.md](SETUP.md) for installation steps.

## Authors
Ryuzo1742
