"""Measure the AI against the ground-truth labels of the synthetic tickets."""
import json
import random
import time
from collections import Counter, defaultdict

from . import db, llm, pipeline

JOB = {"running": False, "done": 0, "total": 0, "failed": 0}


def pick(n: int):
    """Sample unevaluated labelled tickets, round-robin over true categories."""
    rng = random.Random(7)
    with db.conn() as c:
        rows = c.execute(
            """SELECT id, short_description, description, label_category FROM tickets
               WHERE is_synthetic=1 AND label_category IS NOT NULL AND ai_json IS NULL""").fetchall()
    by = defaultdict(list)
    for r in rows:
        by[r["label_category"]].append(r)
    for v in by.values():
        rng.shuffle(v)
    out = []
    while len(out) < n and any(by.values()):
        for k in list(by):
            if by[k] and len(out) < n:
                out.append(by[k].pop())
    return out


async def run(batch) -> None:
    JOB.update(running=True, done=0, total=len(batch), failed=0)
    try:
        for r in batch:
            t0 = time.time()
            try:
                res = await llm.triage(r["short_description"], r["description"])
                ai = res.model_dump()
                ai["latency_s"] = round(time.time() - t0, 1)
                with db.conn() as c:
                    c.execute("UPDATE tickets SET ai_json=? WHERE id=?", (json.dumps(ai), r["id"]))
                pipeline.assess(r["id"])
            except Exception:
                JOB["failed"] += 1
            JOB["done"] += 1
    finally:
        JOB["running"] = False


def _pct(a, b):
    return round(100 * a / b, 1) if b else None


def metrics() -> dict:
    with db.conn() as c:
        rows = c.execute(
            """SELECT id, short_description, label_category, label_priority, label_group, ai_json
               FROM tickets WHERE is_synthetic=1 AND label_category IS NOT NULL AND ai_json IS NOT NULL
               ORDER BY id DESC""").fetchall()
        spike = c.execute(
            """SELECT scenario, COUNT(*) n, SUM(problem_id IS NOT NULL) hit FROM tickets
               WHERE is_synthetic=1 AND scenario != 'background' GROUP BY scenario""").fetchall()
        in_problems = c.execute(
            "SELECT problem_id, scenario FROM tickets WHERE is_synthetic=1 AND problem_id IS NOT NULL").fetchall()
        problems = {p["id"]: p for p in c.execute("SELECT id, number, title FROM problems").fetchall()}

    # ---- triage accuracy ----
    n = len(rows)
    ok_cat = ok_pri = ok_grp = corrected = 0
    lat, per_cat, mistakes = [], defaultdict(lambda: [0, 0]), []
    for r in rows:
        ai = json.loads(r["ai_json"])
        c_ok = ai["category"] == r["label_category"]
        ok_cat += c_ok
        ok_pri += ai["priority"] == r["label_priority"]
        ok_grp += ai["assignment_group"] == r["label_group"]
        corrected += bool(ai.get("corrected"))
        if ai.get("latency_s") is not None:
            lat.append(ai["latency_s"])
        per_cat[r["label_category"]][0] += 1
        per_cat[r["label_category"]][1] += c_ok
        if not c_ok and len(mistakes) < 8:
            mistakes.append({"id": r["id"], "text": r["short_description"],
                             "true": r["label_category"], "predicted": ai["category"]})
    triage = {
        "n": n,
        "category_acc": _pct(ok_cat, n), "priority_acc": _pct(ok_pri, n), "group_acc": _pct(ok_grp, n),
        "avg_latency_s": round(sum(lat) / len(lat), 1) if lat else None,
        "corrected_pct": _pct(corrected, n),
        "per_category": [{"category": k, "n": v[0], "correct": v[1], "acc": _pct(v[1], v[0])}
                         for k, v in sorted(per_cat.items())],
        "mistakes": mistakes,
    }

    # ---- clustering quality ----
    spike_total = sum(r["n"] for r in spike)
    spike_hit = sum(r["hit"] or 0 for r in spike)
    grouped = defaultdict(list)
    for r in in_problems:
        grouped[r["problem_id"]].append(r["scenario"])
    plist, pure_total = [], 0
    for pid, scen in grouped.items():
        top, cnt = Counter(scen).most_common(1)[0]
        pure_total += cnt if top != "background" else 0
        p = problems.get(pid)
        plist.append({"number": p["number"] if p else str(pid), "title": p["title"] if p else "",
                      "tickets": len(scen), "dominant": top, "purity": _pct(cnt, len(scen))})
    clustering = {
        "spike_tickets": spike_total, "detected": spike_hit,
        "recall": _pct(spike_hit, spike_total),
        "precision": _pct(pure_total, len(in_problems)) if in_problems else None,
        "problems": plist,
    }
    return {"job": JOB, "triage": triage, "clustering": clustering}
