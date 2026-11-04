"""Recognize faces page.

Uploads a classroom photo and runs it through scripts/recognize_worker.py
in a separate process (see utils/subprocess_runner.py) — detection and
recognition use native dlib/OpenCV code that can crash hard, and running
it out-of-process means a crash there can't take the GUI down with it.

Attendance is now taken per class period ("Hour 1" .. "Hour 5"), not
once per day — the Hour selector here decides which period this photo's
recognitions get recorded against. It defaults to whichever period is
currently in progress (config.settings.current_period()), since that's
almost always what a teacher taking attendance right now actually wants.
"""

from __future__ import annotations

from dataclasses import dataclass
from tkinter import filedialog

import cv2
import customtkinter as ctk
from PIL import Image

from config.settings import (
    PERIODS,
    RECOGNITION_TOLERANCE_DEFAULT,
    RECOGNITION_TOLERANCE_MAX,
    RECOGNITION_TOLERANCE_MIN,
    current_period,
)
from gui import theme
from gui.base_page import BasePage
from utils.logger import get_logger
from utils.subprocess_runner import WorkerError, run_worker

logger = get_logger(__name__)

PREVIEW_SIZE = (560, 380)
KNOWN_BOX_COLOR = (61, 126, 217)   # BGR — a calm blue, distinct from the amber accent
UNKNOWN_BOX_COLOR = (59, 67, 180)  # BGR — matches theme.DANGER

_PERIOD_BY_LABEL = {p.label: p.number for p in PERIODS}


@dataclass
class _Box:
    x: int
    y: int
    w: int
    h: int


@dataclass
class _Outcome:
    box: _Box
    student_id: str | None
    name: str | None
    confidence: float | None
    attendance_marked: bool


def _parse_outcomes(payload: dict) -> list[_Outcome]:
    return [
        _Outcome(
            box=_Box(o["x"], o["y"], o["w"], o["h"]),
            student_id=o["student_id"],
            name=o["name"],
            confidence=o["confidence"],
            attendance_marked=o["attendance_marked"],
        )
        for o in payload.get("outcomes", [])
    ]


class RecognizePage(BasePage):
    def __init__(self, parent, db, app) -> None:
        super().__init__(parent, db, app, title="Recognize faces")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=theme.PAD * 1.5, pady=(0, theme.PAD))
        body.grid_columnconfigure(0, weight=2)
        body.grid_columnconfigure(1, weight=1)

        upload_card = ctk.CTkFrame(body, fg_color=theme.CARD, corner_radius=theme.CORNER_RADIUS)
        upload_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # --- Hour selector, front and center — this decides which
        # period's attendance record this photo's results get written to.
        hour_row = ctk.CTkFrame(upload_card, fg_color="transparent")
        hour_row.pack(fill="x", padx=20, pady=(20, 0))
        ctk.CTkLabel(
            hour_row, text="Taking attendance for", font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED
        ).pack(side="left", padx=(0, 10))
        self._hour_menu = ctk.CTkOptionMenu(
            hour_row, values=[p.label for p in PERIODS],
            fg_color=theme.ACCENT, button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
            text_color=theme.ON_ACCENT, dropdown_fg_color=theme.CARD,
        )
        self._hour_menu.pack(side="left")
        default_period = current_period()
        self._hour_menu.set(default_period.label if default_period else PERIODS[0].label)

        self._image_area = ctk.CTkLabel(upload_card, text="No photo selected", fg_color=theme.PAPER,
                                         font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED,
                                         width=PREVIEW_SIZE[0], height=PREVIEW_SIZE[1],
                                         corner_radius=theme.CORNER_RADIUS)
        self._image_area.pack(fill="both", expand=True, padx=20, pady=20)

        controls = ctk.CTkFrame(upload_card, fg_color="transparent")
        controls.pack(fill="x", padx=20, pady=(0, 12))
        ctk.CTkButton(
            controls, text="Upload classroom photo", fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER, text_color=theme.ON_ACCENT, command=self._on_upload,
        ).pack(side="left")
        self._run_button = ctk.CTkButton(
            controls, text="Run recognition", fg_color="transparent",
            border_width=1, border_color=theme.BORDER, text_color=theme.TEXT_PRIMARY,
            hover_color=theme.ACCENT_SOFT, state="disabled", command=self._on_run,
        )
        self._run_button.pack(side="left", padx=(10, 0))

        self._summary_label = ctk.CTkLabel(
            upload_card, text="", font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED, wraplength=520, justify="left"
        )
        self._summary_label.pack(anchor="w", padx=20, pady=(0, 16))

        settings_card = ctk.CTkFrame(body, fg_color=theme.CARD, corner_radius=theme.CORNER_RADIUS)
        settings_card.grid(row=0, column=1, sticky="new", padx=(10, 0))

        ctk.CTkLabel(
            settings_card, text="Confidence threshold", font=theme.FONT_HEADING,
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=20, pady=(16, 4))
        self._tolerance_slider = ctk.CTkSlider(
            settings_card, from_=RECOGNITION_TOLERANCE_MIN, to=RECOGNITION_TOLERANCE_MAX,
            progress_color=theme.ACCENT, button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
        )
        self._tolerance_slider.set(RECOGNITION_TOLERANCE_DEFAULT)
        self._tolerance_slider.pack(fill="x", padx=20, pady=(0, 4))
        ctk.CTkLabel(
            settings_card, text="Stricter \u2014 Looser", font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED
        ).pack(anchor="w", padx=20, pady=(0, 16))

        ctk.CTkLabel(
            settings_card, text="Recognized faces", font=theme.FONT_HEADING, text_color=theme.TEXT_PRIMARY
        ).pack(anchor="w", padx=20, pady=(4, 8))
        self._results_list = ctk.CTkScrollableFrame(settings_card, fg_color="transparent", height=300)
        self._results_list.pack(fill="both", expand=True, padx=10, pady=(0, 16))
        self._render_empty_results("Results appear here after recognition runs.")

        self._selected_path: str | None = None

    def on_show(self) -> None:
        # The current period may have changed since this page was built
        # (e.g. the teacher opened it during Hour 2, comes back during
        # Hour 3) — refresh the default each time the page becomes visible.
        default_period = current_period()
        if default_period is not None:
            self._hour_menu.set(default_period.label)

    # --- Upload ---------------------------------------------------

    def _on_upload(self) -> None:
        path = filedialog.askopenfilename(
            title="Select a classroom photo",
            filetypes=[("Images", "*.jpg *.jpeg *.png")],
        )
        if not path:
            return
        self._selected_path = path
        frame = cv2.imread(path)
        if frame is None:
            self._summary_label.configure(text="Couldn't read that image file.", text_color=theme.DANGER)
            return
        self._show_frame(frame)
        self._run_button.configure(state="normal")
        self._summary_label.configure(text=f"Selected: {path.split('/')[-1]}", text_color=theme.TEXT_MUTED)
        self._render_empty_results("Results appear here after recognition runs.")

    # --- Recognition ---------------------------------------------------

    def _on_run(self) -> None:
        if self._selected_path is None:
            return

        frame = cv2.imread(self._selected_path)
        if frame is None:
            self._summary_label.configure(text="Couldn't read that image file.", text_color=theme.DANGER)
            return

        period = _PERIOD_BY_LABEL[self._hour_menu.get()]

        self._run_button.configure(state="disabled")
        self._summary_label.configure(
            text=f"Running recognition for {self._hour_menu.get()}\u2026", text_color=theme.TEXT_MUTED
        )
        self.update_idletasks()  # paint the "Running..." state before the blocking subprocess call

        tolerance = self._tolerance_slider.get()
        try:
            payload = run_worker(
                "recognize_worker.py", self._selected_path, str(tolerance), str(period)
            )
        except WorkerError as exc:
            logger.error("Recognition worker failed: %s", exc)
            self._summary_label.configure(text=str(exc), text_color=theme.DANGER)
            self._run_button.configure(state="normal")
            return

        self._run_button.configure(state="normal")
        outcomes = _parse_outcomes(payload)

        if not outcomes:
            self._summary_label.configure(text="No faces detected in this photo.", text_color=theme.TEXT_MUTED)
            self._render_empty_results("No faces detected.")
            return

        annotated = frame.copy()
        for outcome in outcomes:
            box = outcome.box
            color = KNOWN_BOX_COLOR if outcome.student_id else UNKNOWN_BOX_COLOR
            cv2.rectangle(annotated, (box.x, box.y), (box.x + box.w, box.y + box.h), color, 2)
            label = outcome.name if outcome.student_id else "Unknown"
            cv2.putText(annotated, label, (box.x, max(0, box.y - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        self._show_frame(annotated)

        recognized = sum(1 for o in outcomes if o.student_id is not None)
        newly_marked = sum(1 for o in outcomes if o.attendance_marked)
        self._summary_label.configure(
            text=(f"{self._hour_menu.get()}: {len(outcomes)} face(s) detected, {recognized} recognized, "
                  f"{newly_marked} newly marked present."),
            text_color=theme.SUCCESS,
        )
        self._render_results(outcomes)

    # --- Rendering ---------------------------------------------------

    def _show_frame(self, bgr_frame) -> None:
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb)
        pil_image.thumbnail(PREVIEW_SIZE)
        ctk_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=pil_image.size)
        self._image_area.configure(image=ctk_image, text="")
        self._image_area.image = ctk_image  # keep a reference alive

    def _render_empty_results(self, text: str) -> None:
        for widget in self._results_list.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self._results_list, text=text, font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED,
            wraplength=220, justify="left",
        ).pack(anchor="w", padx=10, pady=10)

    def _render_results(self, outcomes: list[_Outcome]) -> None:
        for widget in self._results_list.winfo_children():
            widget.destroy()

        for outcome in outcomes:
            row = ctk.CTkFrame(self._results_list, fg_color=theme.PAPER, corner_radius=theme.CORNER_RADIUS)
            row.pack(fill="x", padx=6, pady=4)

            if outcome.student_id:
                title = f"{outcome.name}"
                subtitle = f"{outcome.student_id} \u2022 {round(outcome.confidence * 100)}% confidence"
                if outcome.attendance_marked:
                    subtitle += " \u2022 marked present"
                title_color = theme.TEXT_PRIMARY
            else:
                title = "Unknown"
                subtitle = "No match in the registered students"
                title_color = theme.DANGER

            ctk.CTkLabel(row, text=title, font=theme.FONT_BODY, text_color=title_color).pack(
                anchor="w", padx=12, pady=(8, 0))
            ctk.CTkLabel(row, text=subtitle, font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).pack(
                anchor="w", padx=12, pady=(0, 8))
