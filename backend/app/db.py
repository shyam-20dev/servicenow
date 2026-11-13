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

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS kb_articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'General',
    body TEXT NOT NULL,
    embedding TEXT,
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
    "pipeline": "TEXT",         # analyzing | creating_incident | done | error (auto-submit progress)
    "pipeline_error": "TEXT",
    "requester": "TEXT",          # who raised the ticket
    "review_status": "TEXT",      # NULL (not analysed) | auto | pending | approved | overridden
    "review_reasons": "TEXT",     # JSON list: why a human should look at it
    "final_category": "TEXT",     # human override (NULL = AI value stands)
    "final_priority": "TEXT",
    "final_group": "TEXT",
    "reviewed_at": "TEXT",
    "resolution_notes": "TEXT",
    "resolved_at": "TEXT",
}


KB_COLUMNS = {
    "source": "TEXT",         # uploaded file name (NULL for manually written articles)
    "chunk_idx": "INTEGER",
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
        have_kb = {r["name"] for r in c.execute("PRAGMA table_info(kb_articles)")}
        for name, ddl in KB_COLUMNS.items():
            if name not in have_kb:
                c.execute(f"ALTER TABLE kb_articles ADD COLUMN {name} {ddl}")


def row_to_dict(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["ai"] = json.loads(d.pop("ai_json")) if d.get("ai_json") else None
    d["has_embedding"] = bool(d.pop("embedding", None))
    if "review_reasons" in d:   # ticket rows
        d["review_reasons"] = json.loads(d["review_reasons"]) if d["review_reasons"] else []
        ai = d["ai"]
        d["effective"] = {
            "category": d.get("final_category") or ai["category"],
            "priority": d.get("final_priority") or ai["priority"],
            "assignment_group": d.get("final_group") or ai["assignment_group"],
        } if ai else None
    if "actions_json" in d:
        d["actions"] = json.loads(d.pop("actions_json") or "[]")
    return d
