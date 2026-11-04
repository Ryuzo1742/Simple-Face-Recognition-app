"""Student management page: view, edit, delete, and retrain embeddings."""

from __future__ import annotations

import customtkinter as ctk

from database.db_manager import Student
from gui import theme
from gui.base_page import BasePage
from utils.logger import get_logger
from utils.subprocess_runner import WorkerError, run_worker

logger = get_logger(__name__)


class StudentsPage(BasePage):
    def __init__(self, parent, db, app) -> None:
        super().__init__(parent, db, app, title="Students")

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=1, column=0, sticky="w", padx=theme.PAD * 1.5, pady=(0, 8))
        self._retrain_button = ctk.CTkButton(
            toolbar, text="Retrain embeddings", fg_color="transparent", border_width=1,
            border_color=theme.BORDER, text_color=theme.TEXT_PRIMARY, hover_color=theme.ACCENT_SOFT,
            command=self._retrain,
        )
        self._retrain_button.pack(side="left")
        self._status = ctk.CTkLabel(toolbar, text="", font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED)
        self._status.pack(side="left", padx=12)

        self._table = ctk.CTkScrollableFrame(self, fg_color=theme.CARD, corner_radius=theme.CORNER_RADIUS)
        self._table.grid(row=2, column=0, sticky="nsew", padx=theme.PAD * 1.5, pady=(0, theme.PAD))
        self.grid_rowconfigure(2, weight=1)
        for col, weight in enumerate([2, 3, 2, 2, 1]):
            self._table.grid_columnconfigure(col, weight=weight)

        self._render_header()
        self._refresh()

    def on_show(self) -> None:
        self._refresh()

    def _render_header(self) -> None:
        for col, text in enumerate(["Student ID", "Name", "Department", "Semester", ""]):
            ctk.CTkLabel(
                self._table, text=text, font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED
            ).grid(row=0, column=col, sticky="w", padx=10, pady=(10, 6))

    def _refresh(self) -> None:
        for widget in self._table.winfo_children():
            widget.destroy()
        self._render_header()

        students = self.db.list_students()
        if not students:
            ctk.CTkLabel(
                self._table, text="No students registered yet.",
                font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED,
            ).grid(row=1, column=0, columnspan=5, sticky="w", padx=10, pady=10)
            return

        for row, s in enumerate(students, start=1):
            ctk.CTkLabel(self._table, text=s.student_id, font=theme.FONT_MONO,
                        text_color=theme.TEXT_PRIMARY).grid(row=row, column=0, sticky="w", padx=10, pady=4)
            ctk.CTkLabel(self._table, text=s.name, font=theme.FONT_BODY,
                        text_color=theme.TEXT_PRIMARY).grid(row=row, column=1, sticky="w", padx=10, pady=4)
            ctk.CTkLabel(self._table, text=s.department, font=theme.FONT_BODY,
                        text_color=theme.TEXT_PRIMARY).grid(row=row, column=2, sticky="w", padx=10, pady=4)
            ctk.CTkLabel(self._table, text=s.semester, font=theme.FONT_BODY,
                        text_color=theme.TEXT_PRIMARY).grid(row=row, column=3, sticky="w", padx=10, pady=4)
            ctk.CTkButton(
                self._table, text="Delete", width=64, height=24, font=theme.FONT_SMALL,
                fg_color="transparent", border_width=1, border_color=theme.DANGER,
                text_color=theme.DANGER, hover_color=theme.DANGER_SOFT,
                command=lambda sid=s.student_id: self._delete(sid),
            ).grid(row=row, column=4, sticky="w", padx=10, pady=4)

    def _delete(self, student_id: str) -> None:
        self.db.delete_student(student_id)
        logger.info("Deleted student %s", student_id)
        self._refresh()

    def _retrain(self) -> None:
        self._retrain_button.configure(state="disabled")
        self._status.configure(text="Retraining\u2026", text_color=theme.TEXT_MUTED)
        self.update_idletasks()  # paint the "Retraining..." state before the blocking subprocess call

        # Runs in a separate process — see utils/subprocess_runner.py and
        # scripts/train_worker.py. dlib/OpenCV are native libraries that can
        # crash hard rather than raise a catchable Python exception; doing
        # this out-of-process means that crash can't take the GUI down.
        try:
            payload = run_worker("train_worker.py", "__all__")
        except WorkerError as exc:
            logger.error("Retrain worker failed: %s", exc)
            self._status.configure(text=str(exc), text_color=theme.DANGER)
            self._retrain_button.configure(state="normal")
            return

        results = payload.get("results", [])
        self._retrain_button.configure(state="normal")

        if not results:
            self._status.configure(text="No registered students to train.", text_color=theme.TEXT_MUTED)
            return

        succeeded = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]
        message = f"Retrained {len(succeeded)}/{len(results)} students."
        if failed:
            names = ", ".join(r["student_id"] for r in failed)
            message += f" Failed: {names} (see logs)."
            logger.warning("Retrain failures: %s", failed)

        self._status.configure(text=message, text_color=theme.SUCCESS if not failed else theme.DANGER)
