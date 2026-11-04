-- Face Recognition Attendance System — SQLite schema

CREATE TABLE IF NOT EXISTS students (
    student_id  TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    department  TEXT NOT NULL,
    semester    TEXT NOT NULL,
    email       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS attendance (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  TEXT NOT NULL,
    att_date    TEXT NOT NULL,
    att_time    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Present',
    period      INTEGER NOT NULL DEFAULT 1,  -- which class period (Hour 1-5), see config.settings.PERIODS
    FOREIGN KEY (student_id) REFERENCES students (student_id) ON DELETE CASCADE,
    UNIQUE (student_id, att_date, period)  -- one record per student, per day, per period
);

CREATE TABLE IF NOT EXISTS embeddings (
    student_id      TEXT PRIMARY KEY,
    encoding_vector BLOB NOT NULL,
    last_trained    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students (student_id) ON DELETE CASCADE
);

-- Indexes on the attendance table are created in Python, AFTER the
-- period-column migration runs (see db_manager._init_schema) — creating
-- an index on `period` here would fail outright on a pre-migration
-- database where that column doesn't exist yet.
