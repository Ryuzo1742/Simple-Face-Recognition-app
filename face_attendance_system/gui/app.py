"""Main application window.

Owns the sidebar navigation and a content area that swaps between
page frames. Each page is a CTkFrame subclass built lazily on first
visit so startup stays fast.
"""

from __future__ import annotations

import customtkinter as ctk

from database.db_manager import DBManager
from gui import theme
from gui.about_page import AboutPage
from gui.attendance_page import AttendancePage
from gui.dashboard_page import DashboardPage
from gui.recognize_page import RecognizePage
from gui.register_page import RegisterPage
from gui.settings_page import SettingsPage
from gui.students_page import StudentsPage
from utils.logger import get_logger

logger = get_logger(__name__)

NAV_ITEMS = [
    ("Dashboard", "dashboard"),
    ("Register student", "register"),
    ("Recognize faces", "recognize"),
    ("Attendance", "attendance"),
    ("Students", "students"),
    ("Settings", "settings"),
    ("About", "about"),
]

PAGE_CLASSES = {
    "dashboard": DashboardPage,
    "register": RegisterPage,
    "recognize": RecognizePage,
    "attendance": AttendancePage,
    "students": StudentsPage,
    "settings": SettingsPage,
    "about": AboutPage,
}


class App(ctk.CTk):
    """Root window: sidebar + swappable content frame."""

    def __init__(self, db: DBManager) -> None:
        super().__init__()
        self.db = db

        self.title("Attendance — Face Recognition Attendance System")
        self.geometry("1100x700")
        self.minsize(900, 600)
        ctk.set_appearance_mode("light")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._pages: dict[str, ctk.CTkFrame] = {}
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        self._active_key: str | None = None

        self._build_sidebar()
        self._content = ctk.CTkFrame(self, fg_color=theme.PAPER, corner_radius=0)
        self._content.grid(row=0, column=1, sticky="nsew")
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

        self.show_page("dashboard")

    # --- Sidebar ---------------------------------------------------

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(
            self, width=theme.SIDEBAR_WIDTH, fg_color=theme.INK, corner_radius=0
        )
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)

        ctk.CTkLabel(
            sidebar, text="Attendance", font=theme.FONT_TITLE, text_color=theme.TEXT_ON_INK
        ).pack(anchor="w", padx=20, pady=(24, 24))

        for label, key in NAV_ITEMS:
            btn = ctk.CTkButton(
                sidebar,
                text=label,
                font=theme.FONT_NAV,
                anchor="w",
                fg_color="transparent",
                hover_color=theme.INK_HOVER,
                text_color=theme.TEXT_ON_INK,
                corner_radius=theme.CORNER_RADIUS,
                height=38,
                command=lambda k=key: self.show_page(k),
            )
            btn.pack(fill="x", padx=12, pady=2)
            self._nav_buttons[key] = btn

        # --- Light / dark mode toggle, pinned to the bottom of the sidebar ---
        toggle_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        toggle_frame.pack(side="bottom", fill="x", padx=20, pady=20)

        self._dark_mode_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(
            toggle_frame,
            text="Dark mode",
            font=theme.FONT_SMALL,
            text_color=theme.TEXT_ON_INK,
            variable=self._dark_mode_var,
            progress_color=theme.ACCENT,
            command=self._on_toggle_appearance,
        ).pack(anchor="w")

    def _on_toggle_appearance(self) -> None:
        mode = "dark" if self._dark_mode_var.get() else "light"
        ctk.set_appearance_mode(mode)
        logger.info("Switched appearance mode to %s", mode)

    def _set_active_nav(self, key: str) -> None:
        for k, btn in self._nav_buttons.items():
            if k == key:
                btn.configure(fg_color=theme.ACCENT, text_color=theme.ON_ACCENT)
            else:
                btn.configure(fg_color="transparent", text_color=theme.TEXT_ON_INK)

    # --- Page routing ---------------------------------------------------

    def show_page(self, key: str) -> None:
        """Switch the content area to the page identified by key."""
        if key not in PAGE_CLASSES:
            logger.warning("Unknown page key: %s", key)
            return

        if key not in self._pages:
            page_cls = PAGE_CLASSES[key]
            self._pages[key] = page_cls(self._content, db=self.db, app=self)
            self._pages[key].grid(row=0, column=0, sticky="nsew")

        if self._active_key is not None and self._active_key in self._pages:
            self._pages[self._active_key].grid_remove()

        page = self._pages[key]
        page.grid(row=0, column=0, sticky="nsew")
        if hasattr(page, "on_show"):
            page.on_show()

        self._active_key = key
        self._set_active_nav(key)
        logger.info("Navigated to %s page", key)
