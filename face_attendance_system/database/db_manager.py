"""SQLite data access layer.

All queries for students, attendance, and embeddings go through this
single class so the GUI and core layers never touch SQL directly.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterator, Optional

import numpy as np

from config.settings import DB_PATH
from utils.logger import get_logger

logger = get_logger(__name__)

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


@dataclass
class Student:
    student_id: str
    name: str
    department: str
    semester: str
    email: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class AttendanceRecord:
    id: int
    student_id: str
    name: str
    att_date: str
    att_time: str
    status: str
    period: int


@dataclass
class RosterEntry:
    """One student's attendance status for a specific date + period —
    status is None when nobody has marked them yet either way."""

    student_id: str
    name: str
    department: str
    status: Optional[str]
    att_time: Optional[str]


class DBManager:
    """Thin, explicit wrapper around the SQLite database."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("Database operation failed, rolled back.")
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
            self._migrate_add_period_column(conn)
            # Indexes are created here, not in schema.sql, because the
            # period-column migration above must run first — see that
            # method's docstring.
            conn.execute("CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance (att_date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance (student_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_attendance_period ON attendance (period)")
        logger.info("Database schema ready at %s", self.db_path)

    def _migrate_add_period_column(self, conn: sqlite3.Connection) -> None:
        """One-time migration for databases created before per-period
        attendance existed. schema.sql's CREATE TABLE IF NOT EXISTS is a
        no-op on an existing table, so an old database would otherwise be
        stuck on the old (student_id, att_date) UNIQUE constraint forever.
        SQLite can't ALTER a UNIQUE constraint directly, so this rebuilds
        the table: every pre-migration row is assumed to be Hour 1,
        since the old schema had no concept of periods at all.
        """
        cols = [row[1] for row in conn.execute("PRAGMA table_info(attendance)").fetchall()]
        if "period" in cols:
            return

        logger.info("Migrating attendance table to add per-period tracking")
        conn.execute("ALTER TABLE attendance RENAME TO attendance_old")
        conn.execute("""
            CREATE TABLE attendance (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id  TEXT NOT NULL,
                att_date    TEXT NOT NULL,
                att_time    TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'Present',
                period      INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (student_id) REFERENCES students (student_id) ON DELETE CASCADE,
                UNIQUE (student_id, att_date, period)
            )
        """)
        conn.execute("""
            INSERT INTO attendance (id, student_id, att_date, att_time, status, period)
            SELECT id, student_id, att_date, att_time, status, 1 FROM attendance_old
        """)
        conn.execute("DROP TABLE attendance_old")
        logger.info("Migration complete — existing records assigned to Hour 1")

    # --- Students ---------------------------------------------------

    def add_student(self, student: Student) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO students (student_id, name, department, semester, email)
                   VALUES (?, ?, ?, ?, ?)""",
                (student.student_id, student.name, student.department,
                 student.semester, student.email),
            )
        logger.info("Registered student %s (%s)", student.student_id, student.name)

    def update_student(self, student: Student) -> None:
        with self._connect() as conn:
            conn.execute(
                """UPDATE students SET name=?, department=?, semester=?, email=?
                   WHERE student_id=?""",
                (student.name, student.department, student.semester,
                 student.email, student.student_id),
            )

    def delete_student(self, student_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM students WHERE student_id=?", (student_id,))
        logger.info("Deleted student %s", student_id)

    def get_student(self, student_id: str) -> Optional[Student]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM students WHERE student_id=?", (student_id,)
            ).fetchone()
        return Student(**dict(row)) if row else None

    def list_students(self, department: Optional[str] = None) -> list[Student]:
        query = "SELECT * FROM students"
        params: tuple = ()
        if department:
            query += " WHERE department=?"
            params = (department,)
        query += " ORDER BY name"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [Student(**dict(r)) for r in rows]

    def count_students(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]

    # --- Attendance ---------------------------------------------------

    def mark_attendance(self, student_id: str, period: int, when: Optional[datetime] = None) -> bool:
        """Mark a student present for one period. Returns False if already
        marked Present for that student/date/period (recognition running
        twice, or the same student appearing twice in one photo)."""
        return self.set_attendance(student_id, period, "Present", when)

    def set_attendance(
        self, student_id: str, period: int, status: str, when: Optional[datetime] = None
    ) -> bool:
        """Upsert one student's attendance status for one date + period —
        used both by automatic recognition (status='Present') and by a
        teacher's manual Present/Absent override on the Attendance page.
        Returns True if this call actually changed the stored status,
        False if it already matched (so callers can tell "newly marked"
        apart from "already recorded" without a separate lookup).
        """
        when = when or datetime.now()
        att_date = when.date().isoformat()
        att_time = when.time().strftime("%H:%M:%S")

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT status FROM attendance WHERE student_id=? AND att_date=? AND period=?",
                (student_id, att_date, period),
            ).fetchone()
            if existing and existing["status"] == status:
                return False

            conn.execute(
                """INSERT INTO attendance (student_id, att_date, att_time, status, period)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(student_id, att_date, period) DO UPDATE SET
                       status=excluded.status, att_time=excluded.att_time""",
                (student_id, att_date, att_time, status, period),
            )
            return True

    def get_period_roster(self, att_date: str, period: int) -> list[RosterEntry]:
        """Every registered student with their attendance status for one
        date + period — status is None for anyone nobody has marked yet.
        This is what powers the "mark present/absent for missing
        students" panel: it shows the full roster, not just who has a
        recorded status already.
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.student_id, s.name, s.department, a.status, a.att_time
                FROM students s
                LEFT JOIN attendance a
                    ON a.student_id = s.student_id AND a.att_date = ? AND a.period = ?
                ORDER BY s.name
                """,
                (att_date, period),
            ).fetchall()
        return [RosterEntry(**dict(r)) for r in rows]

    def delete_attendance(self, record_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM attendance WHERE id=?", (record_id,))

    def query_attendance(
        self,
        att_date: Optional[str] = None,
        department: Optional[str] = None,
        student_id: Optional[str] = None,
        search: Optional[str] = None,
        period: Optional[int] = None,
    ) -> list[AttendanceRecord]:
        query = """
            SELECT a.id, a.student_id, s.name, a.att_date, a.att_time, a.status, a.period
            FROM attendance a JOIN students s ON a.student_id = s.student_id
            WHERE 1=1
        """
        params: list = []
        if att_date:
            query += " AND a.att_date=?"
            params.append(att_date)
        if department:
            query += " AND s.department=?"
            params.append(department)
        if student_id:
            query += " AND a.student_id=?"
            params.append(student_id)
        if period is not None:
            query += " AND a.period=?"
            params.append(period)
        if search:
            query += " AND (s.name LIKE ? OR a.student_id LIKE ?)"
            like_term = f"%{search}%"
            params.extend([like_term, like_term])
        query += " ORDER BY a.att_date DESC, a.period ASC, a.att_time DESC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [AttendanceRecord(**dict(r)) for r in rows]

    def count_present_today(self) -> int:
        """Distinct students marked Present in at least one period today
        — a student present in 3 of 5 periods still counts once, matching
        what the Dashboard's "present today" stat means to a viewer."""
        today = date.today().isoformat()
        with self._connect() as conn:
            return conn.execute(
                "SELECT COUNT(DISTINCT student_id) FROM attendance WHERE att_date=? AND status='Present'",
                (today,),
            ).fetchone()[0]

    def last_recognition_time(self) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT att_date, att_time FROM attendance ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return f"{row['att_date']} {row['att_time']}" if row else None

    # --- Embeddings ---------------------------------------------------
    # Vectors are stored as raw float64 bytes (face_recognition encodings
    # are always 128-d), reconstructed with a fixed dtype on read — no
    # pickle involved, so a corrupt/foreign blob can't execute code.

    def save_embedding(self, student_id: str, vector: np.ndarray) -> None:
        blob = np.asarray(vector, dtype=np.float64).tobytes()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO embeddings (student_id, encoding_vector, last_trained)
                   VALUES (?, ?, datetime('now'))
                   ON CONFLICT(student_id) DO UPDATE SET
                       encoding_vector=excluded.encoding_vector,
                       last_trained=excluded.last_trained""",
                (student_id, blob),
            )
        logger.info("Saved embedding for %s", student_id)

    def get_embedding(self, student_id: str) -> Optional[np.ndarray]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT encoding_vector FROM embeddings WHERE student_id=?", (student_id,)
            ).fetchone()
        return np.frombuffer(row["encoding_vector"], dtype=np.float64) if row else None

    def get_all_embeddings(self) -> dict[str, np.ndarray]:
        """Return {student_id: 128-d vector} for every trained student."""
        with self._connect() as conn:
            rows = conn.execute("SELECT student_id, encoding_vector FROM embeddings").fetchall()
        return {r["student_id"]: np.frombuffer(r["encoding_vector"], dtype=np.float64) for r in rows}

    def last_trained_at(self, student_id: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT last_trained FROM embeddings WHERE student_id=?", (student_id,)
            ).fetchone()
        return row["last_trained"] if row else None
