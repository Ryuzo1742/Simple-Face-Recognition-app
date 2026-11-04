"""Register student page.

The form saves the student record immediately. Once saved, "Start
capture" opens the webcam, overlays the detected face, auto-saves
sharp crops via core.camera_capture, and stops once enough images
are collected. The recognition engine that turns these images into
embeddings is built in Phase 5 (see StudentsPage's "Retrain" action).
"""

from __future__ import annotations

import cv2
import customtkinter as ctk
from PIL import Image

from config.settings import IMAGES_PER_STUDENT_MAX, IMAGES_PER_STUDENT_MIN
from core.camera_capture import CameraCapture, count_saved_images, save_face_crop
from core.face_detector import FaceDetector
from database.db_manager import Student
from gui import theme
from gui.base_page import BasePage
from utils.logger import get_logger

logger = get_logger(__name__)

CAPTURE_TARGET = 40  # within IMAGES_PER_STUDENT_MIN..MAX
FRAME_INTERVAL_MS = 30  # ~33 fps preview polling
SAVE_EVERY_N_FRAMES = 5  # don't save every single frame — vary the angle a bit


class RegisterPage(BasePage):
    def __init__(self, parent, db, app) -> None:
        super().__init__(parent, db, app, title="Register student")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=theme.PAD * 1.5, pady=(0, theme.PAD))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        # --- Form -------------------------------------------------------
        form_card = ctk.CTkFrame(body, fg_color=theme.CARD, corner_radius=theme.CORNER_RADIUS)
        form_card.grid(row=0, column=0, sticky="new", padx=(0, 10))

        # (label, placeholder example) — the placeholder sits inside the box
        # itself so the expected input is legible in both light and dark mode,
        # not just in the small label above it.
        field_specs = [
            ("Student ID", "e.g. STU2024001"),
            ("Name", "e.g. Asha Menon"),
            ("Department", "e.g. CSE"),
            ("Semester", "e.g. 5"),
            ("Email (optional)", "e.g. asha@example.com"),
        ]

        self._fields: dict[str, ctk.CTkEntry] = {}
        for i, (field, placeholder) in enumerate(field_specs):
            ctk.CTkLabel(
                form_card, text=field, font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED
            ).grid(row=i * 2, column=0, sticky="w", padx=20, pady=(14 if i == 0 else 10, 0))
            entry = ctk.CTkEntry(
                form_card, width=280, placeholder_text=placeholder,
                text_color=theme.TEXT_PRIMARY,
            )
            entry.grid(row=i * 2 + 1, column=0, sticky="w", padx=20, pady=(2, 0))
            self._fields[field] = entry

        self._status_label = ctk.CTkLabel(
            form_card, text="", font=theme.FONT_SMALL, text_color=theme.DANGER, wraplength=280, justify="left"
        )
        self._status_label.grid(row=len(field_specs) * 2, column=0, sticky="w", padx=20, pady=(14, 0))

        self._save_button = ctk.CTkButton(
            form_card, text="Save and start capture", fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER, text_color=theme.ON_ACCENT, command=self._on_save,
        )
        self._save_button.grid(row=len(field_specs) * 2 + 1, column=0, sticky="w", padx=20, pady=20)

        # --- Capture -------------------------------------------------------
        capture_card = ctk.CTkFrame(body, fg_color=theme.CARD, corner_radius=theme.CORNER_RADIUS)
        capture_card.grid(row=0, column=1, sticky="new", padx=(10, 0))

        ctk.CTkLabel(
            capture_card, text="Webcam capture", font=theme.FONT_HEADING, text_color=theme.TEXT_PRIMARY
        ).pack(anchor="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(
            capture_card,
            text=(f"Captures {IMAGES_PER_STUDENT_MIN}\u2013{IMAGES_PER_STUDENT_MAX} images from "
                  "different angles. Move your head slowly left, right, up, and down."),
            font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED, wraplength=280, justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 12))

        self._preview = ctk.CTkLabel(capture_card, text="", fg_color=theme.PAPER,
                                      width=280, height=210, corner_radius=theme.CORNER_RADIUS)
        self._preview.pack(padx=20, pady=(0, 12))
        self._set_preview_text("Camera preview appears here")

        self._progress = ctk.CTkProgressBar(capture_card, width=280, progress_color=theme.ACCENT)
        self._progress.set(0)
        self._progress.pack(padx=20, pady=(0, 6))
        self._progress_label = ctk.CTkLabel(
            capture_card, text=f"0 / {CAPTURE_TARGET} images captured",
            font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED,
        )
        self._progress_label.pack(anchor="w", padx=20, pady=(0, 12))

        self._stop_button = ctk.CTkButton(
            capture_card, text="Stop capture", fg_color="transparent", border_width=1,
            border_color=theme.BORDER, text_color=theme.TEXT_PRIMARY, hover_color=theme.ACCENT_SOFT,
            state="disabled", command=self._stop_capture,
        )
        self._stop_button.pack(anchor="w", padx=20, pady=(0, 16))

        # --- Capture session state ---------------------------------------
        self._camera: CameraCapture | None = None
        self._detector: FaceDetector | None = None
        self._current_student_id: str | None = None
        self._saved_count = 0
        self._frame_counter = 0
        self._capture_job: str | None = None

    # --- Form handling ---------------------------------------------------

    def _on_save(self) -> None:
        values = {k: v.get().strip() for k, v in self._fields.items()}
        if not values["Student ID"] or not values["Name"]:
            self._status_label.configure(text="Student ID and name are required.", text_color=theme.DANGER)
            return

        student = Student(
            student_id=values["Student ID"],
            name=values["Name"],
            department=values["Department"] or "Unassigned",
            semester=values["Semester"] or "N/A",
            email=values["Email (optional)"] or None,
        )
        try:
            self.db.add_student(student)
        except Exception as exc:  # noqa: BLE001 — surface any DB error to the user
            self._status_label.configure(text=f"Couldn't save: {exc}", text_color=theme.DANGER)
            return

        self._status_label.configure(text="Student saved. Starting capture...", text_color=theme.SUCCESS)
        self._current_student_id = student.student_id
        self._start_capture()

    # --- Capture lifecycle ---------------------------------------------------

    def _start_capture(self) -> None:
        if self._detector is None:
            try:
                self._detector = FaceDetector()
            except FileNotFoundError as exc:
                self._set_preview_text("Detector model files missing\nSee models/README.md")
                self._status_label.configure(text=str(exc), text_color=theme.DANGER)
                return

        self._camera = CameraCapture()
        try:
            self._camera.start()
        except RuntimeError as exc:
            self._set_preview_text("Could not open webcam")
            self._status_label.configure(text=str(exc), text_color=theme.DANGER)
            self._camera = None
            return

        self._saved_count = count_saved_images(self._current_student_id)
        self._frame_counter = 0
        self._save_button.configure(state="disabled")
        self._stop_button.configure(state="normal")
        self._update_progress()
        self._capture_job = self.after(FRAME_INTERVAL_MS, self._capture_tick)

    def _capture_tick(self) -> None:
        if self._camera is None or self._detector is None:
            return

        frame = self._camera.read_frame()
        if frame is None:
            self._capture_job = self.after(FRAME_INTERVAL_MS, self._capture_tick)
            return

        box = self._detector.largest_face(frame)
        display_frame = frame.copy()

        if box is not None:
            cv2.rectangle(display_frame, (box.x, box.y), (box.x + box.w, box.y + box.h), (61, 126, 217), 2)

            self._frame_counter += 1
            if self._frame_counter % SAVE_EVERY_N_FRAMES == 0 and self._saved_count < CAPTURE_TARGET:
                saved_path = save_face_crop(
                    self._current_student_id, frame, box, self._saved_count + 1
                )
                if saved_path is not None:
                    self._saved_count += 1
                    self._update_progress()

        self._render_frame(display_frame)

        if self._saved_count >= CAPTURE_TARGET:
            self._finish_capture(success=True)
            return

        self._capture_job = self.after(FRAME_INTERVAL_MS, self._capture_tick)

    def _stop_capture(self) -> None:
        self._finish_capture(success=False)

    def _finish_capture(self, success: bool) -> None:
        if self._capture_job is not None:
            self.after_cancel(self._capture_job)
            self._capture_job = None
        if self._camera is not None:
            self._camera.release()
            self._camera = None

        self._save_button.configure(state="normal")
        self._stop_button.configure(state="disabled")

        if success:
            self._set_preview_text(f"Capture complete \u2014 {self._saved_count} images saved")
            self._status_label.configure(
                text="Capture complete. Run \u2018Retrain embeddings\u2019 on the Students "
                     "page once the recognition engine is connected in Phase 5.",
                text_color=theme.SUCCESS,
            )
        else:
            self._set_preview_text(f"Capture stopped \u2014 {self._saved_count} images saved")
            self._status_label.configure(
                text=f"Stopped early with {self._saved_count} images. You can resume by saving again.",
                text_color=theme.TEXT_MUTED,
            )

    def on_show(self) -> None:
        # Safety net: release the camera if the user navigates away mid-capture.
        if self._camera is not None:
            self._finish_capture(success=False)

    # --- Preview rendering ---------------------------------------------------

    def _set_preview_text(self, text: str) -> None:
        self._preview.configure(image=None, text=text, font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED)

    def _render_frame(self, bgr_frame) -> None:
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb).resize((280, 210))
        ctk_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(280, 210))
        self._preview.configure(image=ctk_image, text="")
        self._preview.image = ctk_image  # keep a reference alive

    def _update_progress(self) -> None:
        self._progress.set(min(self._saved_count / CAPTURE_TARGET, 1.0))
        self._progress_label.configure(text=f"{self._saved_count} / {CAPTURE_TARGET} images captured")
