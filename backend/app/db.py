import json
import sqlite3
from contextlib import contextmanager

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    short_description TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    ai_json TEXT,
    sn_number TEXT,
    sn_sys_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS problems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number TEXT,
    title TEXT NOT NULL,
    root_cause TEXT,
    actions_json TEXT,
    status TEXT NOT NULL DEFAULT 'proposed',
    ticket_count INTEGER NOT NULL DEFAULT 0,
    first_seen TEXT,
    last_seen TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

# Columns added after the first version; applied to existing databases.
TICKET_COLUMNS = {
    "label_category": "TEXT",   # ground truth for evaluation (synthetic data only)
    "label_priority": "TEXT",
    "label_group": "TEXT",
    "scenario": "TEXT",         # hidden ground-truth incident scenario (synthetic data only)
    "is_synthetic": "INTEGER NOT NULL DEFAULT 0",
    "embedding": "TEXT",
    "problem_id": "INTEGER",
}


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    with conn() as c:
        c.executescript(SCHEMA)
        have = {r["name"] for r in c.execute("PRAGMA table_info(tickets)")}
        for name, ddl in TICKET_COLUMNS.items():
            if name not in have:
                c.execute(f"ALTER TABLE tickets ADD COLUMN {name} {ddl}")


def row_to_dict(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["ai"] = json.loads(d.pop("ai_json")) if d.get("ai_json") else None
    d["has_embedding"] = bool(d.pop("embedding", None))
    if "actions_json" in d:
        d["actions"] = json.loads(d.pop("actions_json") or "[]")
    return d
