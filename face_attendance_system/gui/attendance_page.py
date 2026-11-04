"""Attendance management page: view, search, filter, export, delete —
plus, new: filter by class period ("Hour 1".."Hour 5"), and a roster
panel where a teacher can mark Present/Absent for students the automatic
recognition didn't catch for a given period (missed photo, absent, etc).
"""

from __future__ import annotations

import csv
from datetime import date
from tkinter import filedialog, messagebox

import customtkinter as ctk

from config.settings import EXPORTS_DIR, PERIODS
from gui import theme
from gui.base_page import BasePage
from utils.logger import get_logger

logger = get_logger(__name__)

_ALL_HOURS = "All hours"
_PERIOD_BY_LABEL = {p.label: p.number for p in PERIODS}
_LABEL_BY_PERIOD = {p.number: p.label for p in PERIODS}


class AttendancePage(BasePage):
    def __init__(self, parent, db, app) -> None:
        super().__init__(parent, db, app, title="Attendance")

        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.grid(row=1, column=0, sticky="w", padx=theme.PAD * 1.5, pady=(0, 4))

        ctk.CTkLabel(filters, text="Search", font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).pack(
            side="left", padx=(0, 6))
        self._search_entry = ctk.CTkEntry(filters, width=150, placeholder_text="Name or student ID")
        self._search_entry.pack(side="left", padx=(0, 14))
        self._search_entry.bind("<Return>", lambda _e: self._refresh())

        ctk.CTkLabel(filters, text="Date", font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).pack(
            side="left", padx=(0, 6))
        self._date_entry = ctk.CTkEntry(filters, width=100, placeholder_text="YYYY-MM-DD")
        self._date_entry.pack(side="left", padx=(0, 14))
        self._date_entry.bind("<Return>", lambda _e: self._refresh())

        ctk.CTkLabel(filters, text="Department", font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).pack(
            side="left", padx=(0, 6))
        self._dept_entry = ctk.CTkEntry(filters, width=110, placeholder_text="e.g. CSE")
        self._dept_entry.pack(side="left", padx=(0, 14))
        self._dept_entry.bind("<Return>", lambda _e: self._refresh())

        ctk.CTkLabel(filters, text="Hour", font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED).pack(
            side="left", padx=(0, 6))
        self._hour_menu = ctk.CTkOptionMenu(
            filters, values=[_ALL_HOURS] + [p.label for p in PERIODS], width=110,
            fg_color=theme.CARD, button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
            text_color=theme.TEXT_PRIMARY, dropdown_fg_color=theme.CARD,
            command=lambda _v: self._refresh(),
        )
        self._hour_menu.set(_ALL_HOURS)
        self._hour_menu.pack(side="left", padx=(0, 14))

        ctk.CTkButton(filters, text="Apply", fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      text_color=theme.ON_ACCENT, width=60, command=self._refresh).pack(side="left", padx=(0, 6))
        ctk.CTkButton(filters, text="Clear", fg_color="transparent", border_width=1,
                      border_color=theme.BORDER, text_color=theme.TEXT_PRIMARY, width=60,
                      hover_color=theme.ACCENT_SOFT, command=self._clear_filters).pack(side="left", padx=(0, 6))
        ctk.CTkButton(filters, text="Export CSV", fg_color="transparent", border_width=1,
                      border_color=theme.BORDER, text_color=theme.TEXT_PRIMARY,
                      hover_color=theme.ACCENT_SOFT, command=self._export_csv).pack(side="left")

        # --- Roster toggle row ---------------------------------------------------
        roster_row = ctk.CTkFrame(self, fg_color="transparent")
        roster_row.grid(row=2, column=0, sticky="w", padx=theme.PAD * 1.5, pady=(0, 4))
        self._roster_button = ctk.CTkButton(
            roster_row, text="Manage attendance for this hour", fg_color="transparent",
            border_width=1, border_color=theme.BORDER, text_color=theme.TEXT_PRIMARY,
            hover_color=theme.ACCENT_SOFT, command=self._toggle_roster_mode,
        )
        self._roster_button.pack(side="left")
        self._roster_hint = ctk.CTkLabel(
            roster_row, text="Pick a specific date and hour to mark present/absent for missing students.",
            font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED,
        )
        self._roster_hint.pack(side="left", padx=(10, 0))

        self._count_label = ctk.CTkLabel(self, text="", font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED)
        self._count_label.grid(row=3, column=0, sticky="w", padx=theme.PAD * 1.5, pady=(0, 6))

        self._table = ctk.CTkScrollableFrame(self, fg_color=theme.CARD, corner_radius=theme.CORNER_RADIUS)
        self._table.grid(row=4, column=0, sticky="nsew", padx=theme.PAD * 1.5, pady=(0, theme.PAD))
        self.grid_rowconfigure(4, weight=1)

        self._roster_mode = False
        self._render_records_header()
        self._refresh()

    def on_show(self) -> None:
        self._refresh()

    # --- Filter helpers ---------------------------------------------------

    def _selected_period(self) -> int | None:
        label = self._hour_menu.get()
        return _PERIOD_BY_LABEL.get(label)  # None for "All hours"

    def _current_filters(self) -> dict:
        return dict(
            att_date=self._date_entry.get().strip() or None,
            department=self._dept_entry.get().strip() or None,
            search=self._search_entry.get().strip() or None,
            period=self._selected_period(),
        )

    def _clear_filters(self) -> None:
        self._search_entry.delete(0, "end")
        self._date_entry.delete(0, "end")
        self._dept_entry.delete(0, "end")
        self._hour_menu.set(_ALL_HOURS)
        if self._roster_mode:
            self._toggle_roster_mode()
        else:
            self._refresh()

    def _update_roster_availability(self) -> None:
        # The button used to disable itself here with no explanation when
        # date/hour weren't set — which just looked like it did nothing.
        # It now stays clickable always; _toggle_roster_mode() explains why
        # if it can't proceed.
        pass

    # --- Records view (default) ---------------------------------------------------

    def _render_records_header(self) -> None:
        for widget in self._table.winfo_children():
            widget.destroy()
        for col, weight in enumerate([2, 3, 2, 1, 2, 1, 1]):
            self._table.grid_columnconfigure(col, weight=weight)
        headers = ["Student ID", "Name", "Date", "Hour", "Time", "Status", ""]
        for col, text in enumerate(headers):
            ctk.CTkLabel(
                self._table, text=text, font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED
            ).grid(row=0, column=col, sticky="w", padx=10, pady=(10, 6))

    def _refresh(self) -> None:
        self._update_roster_availability()
        if self._roster_mode:
            self._render_roster()
            return

        self._render_records_header()
        records = self.db.query_attendance(**self._current_filters())
        self._count_label.configure(text=f"{len(records)} record{'s' if len(records) != 1 else ''}")

        if not records:
            ctk.CTkLabel(
                self._table, text="No attendance records match these filters.",
                font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED,
            ).grid(row=1, column=0, columnspan=7, sticky="w", padx=10, pady=10)
            return

        for row, rec in enumerate(records, start=1):
            hour_label = _LABEL_BY_PERIOD.get(rec.period, f"Hour {rec.period}")
            values = [rec.student_id, rec.name, rec.att_date, hour_label, rec.att_time, rec.status]
            fonts = [theme.FONT_MONO, theme.FONT_BODY, theme.FONT_BODY, theme.FONT_BODY, theme.FONT_BODY, theme.FONT_BODY]
            colors = [theme.TEXT_PRIMARY, theme.TEXT_PRIMARY, theme.TEXT_PRIMARY, theme.TEXT_PRIMARY,
                      theme.TEXT_PRIMARY, theme.SUCCESS if rec.status == "Present" else theme.DANGER]
            for col, (value, font, color) in enumerate(zip(values, fonts, colors)):
                ctk.CTkLabel(self._table, text=value, font=font, text_color=color).grid(
                    row=row, column=col, sticky="w", padx=10, pady=4)
            ctk.CTkButton(
                self._table, text="Delete", width=64, height=24, font=theme.FONT_SMALL,
                fg_color="transparent", border_width=1, border_color=theme.DANGER,
                text_color=theme.DANGER, hover_color=theme.DANGER_SOFT,
                command=lambda rid=rec.id, name=rec.name, d=rec.att_date, h=hour_label: self._confirm_delete(rid, name, d, h),
            ).grid(row=row, column=6, sticky="w", padx=10, pady=4)

    def _confirm_delete(self, record_id: int, name: str, att_date: str, hour_label: str) -> None:
        confirmed = messagebox.askyesno(
            "Delete attendance record",
            f"Delete the attendance record for {name} on {att_date} ({hour_label})?\nThis can't be undone.",
        )
        if confirmed:
            self.db.delete_attendance(record_id)
            logger.info("Deleted attendance record %s (%s, %s, %s)", record_id, name, att_date, hour_label)
            self._refresh()

    def _export_csv(self) -> None:
        records = self.db.query_attendance(**self._current_filters())
        if not records:
            messagebox.showinfo("Export CSV", "No records match the current filters — nothing to export.")
            return

        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        default_name = f"attendance_{date.today().isoformat()}.csv"
        path = filedialog.asksaveasfilename(
            initialdir=str(EXPORTS_DIR), initialfile=default_name,
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Student ID", "Name", "Date", "Hour", "Time", "Status"])
            for rec in records:
                hour_label = _LABEL_BY_PERIOD.get(rec.period, f"Hour {rec.period}")
                writer.writerow([rec.student_id, rec.name, rec.att_date, hour_label, rec.att_time, rec.status])
        logger.info("Exported %d records to %s", len(records), path)

    # --- Roster view (manual Present/Absent marking) ---------------------------------------------------

    def _toggle_roster_mode(self) -> None:
        if not self._roster_mode:
            missing = []
            if not self._date_entry.get().strip():
                missing.append("a date")
            if self._selected_period() is None:
                missing.append("a specific hour (not \u2018All hours\u2019)")
            if missing:
                self._roster_hint.configure(
                    text=f"Pick {' and '.join(missing)} above first, then click this button again.",
                    text_color=theme.DANGER,
                )
                return

        self._roster_mode = not self._roster_mode
        self._roster_button.configure(
            text="Back to records" if self._roster_mode else "Manage attendance for this hour"
        )
        self._roster_hint.configure(
            text="Pick a specific date and hour to mark present/absent for missing students.",
            text_color=theme.TEXT_MUTED,
        )
        self._refresh()

    def _render_roster(self) -> None:
        for widget in self._table.winfo_children():
            widget.destroy()
        for col, weight in enumerate([2, 3, 2, 2, 2]):
            self._table.grid_columnconfigure(col, weight=weight)

        att_date = self._date_entry.get().strip()
        period = self._selected_period()
        hour_label = _LABEL_BY_PERIOD.get(period, f"Hour {period}")

        headers = ["Student ID", "Name", "Department", "Status", "Mark as"]
        for col, text in enumerate(headers):
            ctk.CTkLabel(
                self._table, text=text, font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED
            ).grid(row=0, column=col, sticky="w", padx=10, pady=(10, 6))

        roster = self.db.get_period_roster(att_date=att_date, period=period)
        self._count_label.configure(
            text=f"{att_date} \u2014 {hour_label} \u2014 {len(roster)} student(s) on roster"
        )

        if not roster:
            ctk.CTkLabel(
                self._table, text="No registered students.",
                font=theme.FONT_SMALL, text_color=theme.TEXT_MUTED,
            ).grid(row=1, column=0, columnspan=5, sticky="w", padx=10, pady=10)
            return

        for row, entry in enumerate(roster, start=1):
            if entry.status == "Present":
                status_text, status_color = "Present", theme.SUCCESS
            elif entry.status == "Absent":
                status_text, status_color = "Absent", theme.DANGER
            else:
                status_text, status_color = "Not marked", theme.TEXT_MUTED

            ctk.CTkLabel(self._table, text=entry.student_id, font=theme.FONT_MONO,
                        text_color=theme.TEXT_PRIMARY).grid(row=row, column=0, sticky="w", padx=10, pady=4)
            ctk.CTkLabel(self._table, text=entry.name, font=theme.FONT_BODY,
                        text_color=theme.TEXT_PRIMARY).grid(row=row, column=1, sticky="w", padx=10, pady=4)
            ctk.CTkLabel(self._table, text=entry.department, font=theme.FONT_BODY,
                        text_color=theme.TEXT_PRIMARY).grid(row=row, column=2, sticky="w", padx=10, pady=4)
            ctk.CTkLabel(self._table, text=status_text, font=theme.FONT_BODY,
                        text_color=status_color).grid(row=row, column=3, sticky="w", padx=10, pady=4)

            actions = ctk.CTkFrame(self._table, fg_color="transparent")
            actions.grid(row=row, column=4, sticky="w", padx=10, pady=2)

            # A single toggle instead of two separate buttons — one control
            # that flips between Present/Absent, colored to match whichever
            # side is currently selected. Unmarked students default the
            # toggle to "Absent" purely as a display starting point (.set()
            # doesn't fire the command callback), matching the still-honest
            # "Not marked" label in the Status column until the teacher
            # actually clicks something.
            current_choice = entry.status or "Absent"
            toggle_color = theme.SUCCESS if current_choice == "Present" else theme.DANGER
            toggle = ctk.CTkSegmentedButton(
                actions, values=["Present", "Absent"], width=140, height=26,
                font=theme.FONT_SMALL,
                selected_color=toggle_color, selected_hover_color=toggle_color,
                unselected_color=theme.CARD, unselected_hover_color=theme.ACCENT_SOFT,
                text_color=theme.TEXT_PRIMARY,
                command=lambda choice, sid=entry.student_id: self._mark(sid, att_date, period, choice),
            )
            toggle.set(current_choice)
            toggle.pack(side="left")

    def _mark(self, student_id: str, att_date: str, period: int, status: str) -> None:
        from datetime import datetime
        when = datetime.combine(date.fromisoformat(att_date), datetime.now().time())
        self.db.set_attendance(student_id, period=period, status=status, when=when)
        logger.info("Manually marked %s as %s for period %d on %s", student_id, status, period, att_date)
        self._refresh()
