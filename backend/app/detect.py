"""Embedding clustering + spike detection -> Problem drafts."""
import json
from datetime import datetime, timedelta, timezone

import numpy as np

from . import db, llm

FMT = "%Y-%m-%d %H:%M:%S"


async def embed_missing() -> int:
    """Embed every ticket that has no embedding yet."""
    with db.conn() as c:
        rows = c.execute("SELECT id, short_description, description FROM tickets WHERE embedding IS NULL").fetchall()
    if not rows:
        return 0
    vecs = await llm.embed([f"{r['short_description']}. {r['description']}" for r in rows])
    with db.conn() as c:
        c.executemany("UPDATE tickets SET embedding=? WHERE id=?",
                      [(json.dumps(v), r["id"]) for v, r in zip(vecs, rows)])
    return len(rows)


def cluster(rows, threshold: float):
    """Greedy single-pass clustering on cosine similarity (centroids updated as tickets join)."""
    clusters = []  # each: {"ids": [], "sum": np.ndarray, "rows": []}
    for r in rows:
        v = np.array(json.loads(r["embedding"]), dtype=np.float32)
        v /= np.linalg.norm(v) or 1.0
        best, best_sim = None, threshold
        for cl in clusters:
            cen = cl["sum"] / (np.linalg.norm(cl["sum"]) or 1.0)
            sim = float(cen @ v)
            if sim >= best_sim:
                best, best_sim = cl, sim
        if best is None:
            clusters.append({"sum": v.copy(), "rows": [r]})
        else:
            best["sum"] += v
            best["rows"].append(r)
    return clusters


async def detect(window_minutes: int = 60, min_size: int = 5, threshold: float = 0.75) -> dict:
    embedded = await embed_missing()
    since = (datetime.now(timezone.utc) - timedelta(minutes=window_minutes)).strftime(FMT)
    with db.conn() as c:
        rows = c.execute(
            "SELECT * FROM tickets WHERE created_at >= ? AND embedding IS NOT NULL AND problem_id IS NULL ORDER BY created_at",
            (since,)).fetchall()

    spikes = [cl for cl in cluster(rows, threshold) if len(cl["rows"]) >= min_size]
    created = []
    for cl in spikes:
        members = cl["rows"]
        draft_error = None
        samples = [f"{m['short_description']}: {m['description']}" for m in members[:6]]
        try:
            draft = await llm.draft_problem(samples)
            title, cause, actions = draft.title, draft.root_cause, draft.actions
        except Exception as e:
            draft_error = f"{type(e).__name__}: {e}"
            print("draft_problem failed:", draft_error, flush=True)
            title, cause, actions = f"Possible shared issue: {members[0]['short_description']}", "Draft unavailable", []
        times = [m["created_at"] for m in members]
        with db.conn() as c:
            cur = c.execute(
                """INSERT INTO problems (title, root_cause, actions_json, ticket_count, first_seen, last_seen)
                   VALUES (?,?,?,?,?,?)""",
                (title, cause, json.dumps(actions), len(members), min(times), max(times)))
            pid = cur.lastrowid
            c.execute("UPDATE problems SET number=? WHERE id=?", (f"PRB{1000 + pid:07d}", pid))
            c.executemany("UPDATE tickets SET problem_id=? WHERE id=?", [(pid, m["id"]) for m in members])
        created.append({"problem_id": pid, "tickets": len(members), "title": title,
                        "draft_error": draft_error,
                        "scenarios": sorted({m["scenario"] for m in members if m["scenario"]})})
    return {"embedded": embedded, "tickets_considered": len(rows),
            "clusters_found": len(spikes), "problems_created": created}
