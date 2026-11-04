"""Application-wide logging setup.

Every module gets a logger via get_logger(__name__) so log lines are
traceable to their source, and everything is written both to console
and to a rotating log file under logs/.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from config.settings import LOGS_DIR, ensure_directories

_CONFIGURED = False


def _configure_root() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    ensure_directories()
    log_file = LOGS_DIR / "app.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger, configuring the root logger on first call."""
    _configure_root()
    return logging.getLogger(name)
