import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    instruction TEXT NOT NULL,
    source_path TEXT,
    output_dir TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error TEXT,
    recovery_attempts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    timestamp TEXT NOT NULL,
    checkpoint_name TEXT NOT NULL,
    data_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id, id);
"""


class ClosingConnection(sqlite3.Connection):
    """Commit/rollback via context manager, then always close connection."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class TaskDatabase:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript(SCHEMA)

    def connect(self):
        con = sqlite3.connect(
            str(self.path),
            timeout=10,
            factory=ClosingConnection,
        )
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con
