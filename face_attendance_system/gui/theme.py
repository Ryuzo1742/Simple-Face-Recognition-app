"""Design tokens for the GUI — the 'Slate & Amber' identity.

Every color is a (light, dark) tuple. CustomTkinter resolves tuples
against the current appearance mode automatically and re-renders
already-built widgets the moment ctk.set_appearance_mode() is called
— so switching themes at runtime needs no manual widget refresh, as
long as every widget is built with these tokens instead of raw hex.

Replaces the earlier teal-based palette: a slate sidebar stays constant
in feel across modes, paired with a warm amber accent (a "class register
stamp" feel) instead of the previous teal.
"""

from __future__ import annotations

# --- Palette: (light mode, dark mode) --------------------------------
INK = ("#20242B", "#15171C")          # sidebar background
INK_HOVER = ("#2B313B", "#1F232A")
PAPER = ("#F5F3EE", "#121319")        # main content background
CARD = ("#FFFFFF", "#1C1E26")
ACCENT = ("#B8823D", "#D9A653")       # amber — primary actions, active nav
ACCENT_HOVER = ("#9C6C2F", "#C79246")
ACCENT_SOFT = ("#F3E6D2", "#3A2E1A")  # accent tint for badges / active bg
ON_ACCENT = ("#FFFFFF", "#241C0C")    # text placed on top of ACCENT
TEXT_PRIMARY = ("#1E2328", "#E8E6E0")
TEXT_ON_INK = ("#EDEEEC", "#E8E6E0")
TEXT_MUTED = ("#6B7076", "#9A9790")
BORDER = ("#DEDBD3", "#2B2D35")
DANGER = ("#B4433B", "#E0685E")
DANGER_SOFT = ("#F6E4E2", "#3A2422")
SUCCESS = ("#3E7C56", "#6FBE8C")

# --- Typography ------------------------------------------------------------
FONT_FAMILY = "Segoe UI"
FONT_TITLE = (FONT_FAMILY, 20, "bold")
FONT_HEADING = (FONT_FAMILY, 15, "bold")
FONT_BODY = (FONT_FAMILY, 13, "normal")
FONT_SMALL = (FONT_FAMILY, 11, "normal")
FONT_STAT = (FONT_FAMILY, 26, "bold")
FONT_NAV = (FONT_FAMILY, 13, "normal")
FONT_MONO = ("Consolas", 12, "normal")

# --- Layout ------------------------------------------------------------
SIDEBAR_WIDTH = 200
CORNER_RADIUS = 8
PAD = 16
