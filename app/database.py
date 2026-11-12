"""SQLite access using the standard-library sqlite3 module (no ORM, easy to explain)."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number TEXT UNIQUE,
    short_description TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Other',
    impact INTEGER NOT NULL DEFAULT 2,
    urgency INTEGER NOT NULL DEFAULT 2,
    priority INTEGER NOT NULL DEFAULT 3,
    status TEXT NOT NULL DEFAULT 'New',
    assignment_group TEXT,
    assigned_to TEXT,
    reporter TEXT NOT NULL DEFAULT 'demo.employee',
    ai_summary TEXT,
    ai_steps TEXT,
    ai_resolution TEXT,
    ai_source TEXT,
    ai_note TEXT,
    sn_number TEXT,
    sn_sys_id TEXT,
    sn_status TEXT,
    sn_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS service_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number TEXT UNIQUE,
    department TEXT NOT NULL,
    request_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    requester TEXT NOT NULL DEFAULT 'demo.employee',
    priority TEXT NOT NULL DEFAULT 'Medium',
    status TEXT NOT NULL DEFAULT 'Submitted',
    assignment_group TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'bundled',
    content TEXT NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    embedded INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    embedding TEXT,
    embedding_model TEXT
);

CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    mode TEXT,
    sources TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON knowledge_chunks(document_id);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def get_conn():
    """Yield a connection; commit on success, roll back on error, always close."""
    path = get_settings().db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
