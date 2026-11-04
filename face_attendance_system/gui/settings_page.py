"""Settings page: app info, plus a diagnostics panel for the recognition
dependencies (dlib/face_recognition/OpenCV), since those can fail
silently on a broken install. Full preference persistence is Phase 8.
"""

from __future__ import annotations

import customtkinter as ctk

from config.settings import APP_VERSION, DATASET_DIR, DB_PATH
from gui import theme
from gui.base_page import BasePage
from utils.subprocess_runner import run_diagnostics


class SettingsPage(BasePage):
    def __init__(self, parent, db, app) -> None:
        super().__init__(parent, db, app, title="Settings")

        info_card = ctk.CTkFrame(self, fg_color=theme.CARD, corner_radius=theme.CORNER_RADIUS)
        info_card.grid(row=1, column=0, sticky="new", padx=theme.PAD * 1.5, pady=(0, 12))

        rows = [
            ("Appearance", "Light / dark \u2014 toggle in the sidebar"),
            ("Database location", str(DB_PATH)),
            ("Dataset location", str(DATASET_DIR)),
            ("App version", APP_VERSION),
        ]
        for i, (label, value) in enumerate(rows):
            ctk.CTkLabel(info_card, text=label, font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).grid(
                row=i, column=0, sticky="w", padx=20, pady=(14 if i == 0 else 8, 0))
            ctk.CTkLabel(info_card, text=value, font=theme.FONT_BODY, text_color=theme.TEXT_PRIMARY).grid(
                row=i, column=1, sticky="w", padx=20, pady=(14 if i == 0 else 8, 0))
        ctk.CTkLabel(
            info_card, text="Recognition threshold is on the Recognize page.",
            font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED,
        ).grid(row=len(rows), column=0, columnspan=2, sticky="w", padx=20, pady=(16, 20))

        diag_card = ctk.CTkFrame(self, fg_color=theme.CARD, corner_radius=theme.CORNER_RADIUS)
        diag_card.grid(row=2, column=0, sticky="new", padx=theme.PAD * 1.5, pady=(0, theme.PAD))
        self.grid_rowconfigure(2, weight=0)

        ctk.CTkLabel(
            diag_card, text="Recognition engine diagnostics", font=theme.FONT_HEADING,
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(
            diag_card,
            text=("Checks OpenCV, the detector model files, and face_recognition/dlib "
                  "one at a time \u2014 useful if Recognize or Retrain fails, since it shows "
                  "exactly which dependency is the problem, even if that dependency crashes."),
            font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED, wraplength=560, justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 12))

        self._diag_button = ctk.CTkButton(
            diag_card, text="Run diagnostics", fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            text_color=theme.ON_ACCENT, command=self._run_diagnostics,
        )
        self._diag_button.pack(anchor="w", padx=20, pady=(0, 12))

        self._diag_results = ctk.CTkFrame(diag_card, fg_color="transparent")
        self._diag_results.pack(fill="x", padx=20, pady=(0, 20))

    def _run_diagnostics(self) -> None:
        self._diag_button.configure(state="disabled", text="Running\u2026")
        self.update_idletasks()

        result = run_diagnostics()

        self._diag_button.configure(state="normal", text="Run diagnostics")
        for widget in self._diag_results.winfo_children():
            widget.destroy()

        for check in result["checks"]:
            row = ctk.CTkFrame(self._diag_results, fg_color="transparent")
            row.pack(fill="x", pady=2)
            mark = "\u2713" if check["ok"] else "\u2717"
            color = theme.SUCCESS if check["ok"] else theme.DANGER
            ctk.CTkLabel(row, text=f"{mark}  {check['name']}", font=theme.FONT_BODY,
                        text_color=color, width=220, anchor="w").pack(side="left")
            if check["detail"]:
                ctk.CTkLabel(row, text=check["detail"], font=theme.FONT_SMALL,
                            text_color=theme.TEXT_MUTED, anchor="w").pack(side="left", padx=(8, 0))

        if result["crashed"]:
            ctk.CTkLabel(
                self._diag_results,
                text=f"\u26a0 The diagnostics process itself crashed (code {result['returncode']}) "
                     f"right after the last check above.\n{result['crash_detail']}",
                font=theme.FONT_SMALL, text_color=theme.DANGER, wraplength=560, justify="left",
            ).pack(anchor="w", pady=(8, 0))
        elif not result["checks"]:
            ctk.CTkLabel(
                self._diag_results, text="Diagnostics produced no results \u2014 see logs/app.log.",
                font=theme.FONT_SMALL, text_color=theme.DANGER,
            ).pack(anchor="w", pady=(8, 0))
        elif all(c["ok"] for c in result["checks"]):
            ctk.CTkLabel(
                self._diag_results, text="All checks passed \u2014 recognition should work normally.",
                font=theme.FONT_SMALL, text_color=theme.SUCCESS,
            ).pack(anchor="w", pady=(8, 0))
