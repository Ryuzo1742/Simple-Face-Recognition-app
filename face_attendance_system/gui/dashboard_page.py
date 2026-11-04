"""Dashboard page: student count, today's attendance, last recognition, quick actions."""

from __future__ import annotations

import customtkinter as ctk

from gui import theme
from gui.base_page import BasePage


class DashboardPage(BasePage):
    def __init__(self, parent, db, app) -> None:
        super().__init__(parent, db, app, title="Dashboard")

        self._stats_row = ctk.CTkFrame(self, fg_color="transparent")
        self._stats_row.grid(row=1, column=0, sticky="ew", padx=theme.PAD * 1.5)
        for i in range(4):
            self._stats_row.grid_columnconfigure(i, weight=1, uniform="stats")

        actions_label = ctk.CTkLabel(
            self, text="Quick actions", font=theme.FONT_HEADING, text_color=theme.TEXT_PRIMARY
        )
        actions_label.grid(row=2, column=0, sticky="w", padx=theme.PAD * 1.5, pady=(theme.PAD * 1.5, 8))

        actions_row = ctk.CTkFrame(self, fg_color="transparent")
        actions_row.grid(row=3, column=0, sticky="w", padx=theme.PAD * 1.5)

        ctk.CTkButton(
            actions_row, text="Register student", fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER, command=lambda: app.show_page("register"),
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            actions_row, text="Take attendance", fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER, command=lambda: app.show_page("recognize"),
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            actions_row, text="View today's log", fg_color="transparent",
            border_width=1, border_color=theme.BORDER, text_color=theme.TEXT_PRIMARY,
            hover_color=theme.ACCENT_SOFT, command=lambda: app.show_page("attendance"),
        ).pack(side="left")

        self._render_stats()

    def on_show(self) -> None:
        self._render_stats()

    def _render_stats(self) -> None:
        for widget in self._stats_row.winfo_children():
            widget.destroy()

        total_students = self.db.count_students()
        present_today = self.db.count_present_today()
        rate = f"{round(present_today / total_students * 100)}%" if total_students else "—"
        last_seen = self.db.last_recognition_time() or "No recognitions yet"

        stats = [
            ("Total students", str(total_students)),
            ("Present today", str(present_today)),
            ("Attendance rate", rate),
            ("Last recognition", last_seen),
        ]
        for col, (label, value) in enumerate(stats):
            card = self.metric_card(self._stats_row, label, value)
            card.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0))
