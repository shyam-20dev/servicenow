"""Embedding clustering + spike detection -> Problem drafts."""
import json
from datetime import datetime, timedelta, timezone

import numpy as np

from . import config, db, llm, pipeline

FMT = "%Y-%m-%d %H:%M:%S"


async def embed_missing(since: str | None = None) -> int:
    """Embed tickets that have no embedding yet (only those created since `since`, if given)."""
    with db.conn() as c:
        if since:
            rows = c.execute("SELECT id, short_description, description FROM tickets WHERE embedding IS NULL AND created_at >= ?", (since,)).fetchall()
        else:
            rows = c.execute("SELECT id, short_description, description FROM tickets WHERE embedding IS NULL").fetchall()
    if not rows:
        return 0
    vecs = await llm.embed([f"{r['short_description']}. {r['description']}" for r in rows])
    with db.conn() as c:
        c.executemany("UPDATE tickets SET embedding=? WHERE id=?",
                      [(json.dumps(v), r["id"]) for v, r in zip(vecs, rows)])
    return len(rows)


def cluster(rows, threshold: float):
    """Average-linkage agglomerative clustering on cosine similarity.

    Two groups merge only while the AVERAGE similarity between their tickets is >= threshold, so one
    chance look-alike pair cannot glue two different incidents together (and the result does not
    depend on ticket order). Cost grows with the cube of the ticket count, which is fine for the
    few hundred tickets in a detection window.
    """
    n = len(rows)
    if n == 0:
        return []
    X = np.array([json.loads(r["embedding"]) for r in rows], dtype=np.float64)
    X /= np.linalg.norm(X, axis=1, keepdims=True).clip(min=1e-12)
    sums = X @ X.T                       # sums[a, b] = total similarity between members of groups a and b
    sizes = np.ones(n)
    active = np.ones(n, dtype=bool)
    members = [[i] for i in range(n)]
    while active.sum() > 1:
        avg = sums / np.outer(sizes, sizes)
        pair_ok = active[:, None] & active[None, :]
        np.fill_diagonal(pair_ok, False)
        avg = np.where(pair_ok, avg, -np.inf)
        i, j = divmod(int(np.argmax(avg)), n)
        if avg[i, j] < threshold:
            break
        merged = sums[i, :] + sums[j, :]
        sums[i, :] = merged
        sums[:, i] = merged
        sizes[i] += sizes[j]
        active[j] = False
        members[i] += members[j]
    return [{"rows": [rows[k] for k in sorted(m)]} for m, a in zip(members, active) if a]


async def detect(window_minutes: int = 60, min_size: int = 5, threshold: float | None = None) -> dict:
    threshold = config.CLUSTER_THRESHOLD if threshold is None else threshold
    since = (datetime.now(timezone.utc) - timedelta(minutes=window_minutes)).strftime(FMT)
    embedded = await embed_missing(since)   # old tickets are not needed for spike detection
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
        pipeline.flag_for_review([m["id"] for m in members], f"Part of incident spike {f'PRB{1000 + pid:07d}'}")
        created.append({"problem_id": pid, "tickets": len(members), "title": title,
                        "draft_error": draft_error,
                        "scenarios": sorted({m["scenario"] for m in members if m["scenario"]})})
    return {"embedded": embedded, "tickets_considered": len(rows),
            "clusters_found": len(spikes), "problems_created": created}
