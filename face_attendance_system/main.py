"""Entry point for the Face Recognition Attendance System."""

from __future__ import annotations

from config.settings import ensure_directories
from database.db_manager import DBManager
from gui.app import App
from utils.logger import get_logger

logger = get_logger(__name__)


def main() -> None:
    ensure_directories()
    logger.info("Starting Face Recognition Attendance System")

    db = DBManager()
    app = App(db=db)
    app.mainloop()

    logger.info("Application closed")


if __name__ == "__main__":
    main()
