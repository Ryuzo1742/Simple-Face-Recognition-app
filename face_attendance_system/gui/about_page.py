"""About page: project and stack information."""

from __future__ import annotations

import customtkinter as ctk

from config.settings import APP_VERSION
from gui import theme
from gui.base_page import BasePage


class AboutPage(BasePage):
    def __init__(self, parent, db, app) -> None:
        super().__init__(parent, db, app, title="About")

        card = ctk.CTkFrame(self, fg_color=theme.CARD, corner_radius=theme.CORNER_RADIUS)
        card.grid(row=1, column=0, sticky="new", padx=theme.PAD * 1.5, pady=(0, theme.PAD))

        ctk.CTkLabel(
            card, text="Face Recognition Attendance System", font=theme.FONT_HEADING,
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(
            card, text=f"Version {APP_VERSION}", font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=20)

        stack = (
            "Detection: OpenCV DNN\n"
            "Recognition: face_recognition (dlib)\n"
            "GUI: CustomTkinter\n"
            "Storage: SQLite\n"
        )
        ctk.CTkLabel(
            card, text=stack, font=theme.FONT_BODY, text_color=theme.TEXT_PRIMARY, justify="left",
        ).pack(anchor="w", padx=20, pady=(16, 20))
