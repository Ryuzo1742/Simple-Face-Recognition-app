"""Base class shared by every page frame."""

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from gui import theme

if TYPE_CHECKING:
    from database.db_manager import DBManager
    from gui.app import App


class BasePage(ctk.CTkFrame):
    """Common scaffolding: padded content area with a title row."""

    def __init__(self, parent: ctk.CTkFrame, db: "DBManager", app: "App", title: str) -> None:
        super().__init__(parent, fg_color=theme.PAPER, corner_radius=0)
        self.db = db
        self.app = app

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self, text=title, font=theme.FONT_TITLE, text_color=theme.TEXT_PRIMARY
        ).grid(row=0, column=0, sticky="w", padx=theme.PAD * 1.5, pady=(theme.PAD * 1.5, theme.PAD))

    def on_show(self) -> None:
        """Called each time the page becomes visible. Override to refresh data."""

    def metric_card(self, parent: ctk.CTkFrame, label: str, value: str) -> ctk.CTkFrame:
        """A small stat card matching the Phase 2 dashboard wireframe."""
        card = ctk.CTkFrame(parent, fg_color=theme.CARD, corner_radius=theme.CORNER_RADIUS)
        ctk.CTkLabel(
            card, text=label, font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED
        ).pack(anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(
            card, text=value, font=theme.FONT_STAT, text_color=theme.TEXT_PRIMARY
        ).pack(anchor="w", padx=16, pady=(0, 14))
        return card
