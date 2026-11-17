import time

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import asyncio

from . import db, detect, embedsig, evaluation, kb, llm, pipeline, seed, servicenow, sn_store

_tasks: set = set()

app = FastAPI(title="ProblemLens API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    db.init()
    embedsig.check()
    await sn_store.start()


@app.get("/api/sync")
def sync_status():
    """ServiceNow sync state: rows waiting to be pushed, last push/pull, last error."""
    return sn_store.status()


@app.post("/api/sync/now")
async def sync_now():
    """Push pending changes and refresh the cache from ServiceNow immediately."""
    if not sn_store.live():
        raise HTTPException(409, "SN_MODE is not live")
    if not sn_store.STATE["schema_ok"]:
        await sn_store.ensure_schema()
    return {"push": await sn_store.push_dirty(), "pull": await sn_store.pull(), **sn_store.status()}


class TicketIn(BaseModel):
    short_description: str
    description: str
    requester: str = "Anonymous"


def _get(ticket_id: int) -> dict:
    with db.conn() as c:
        row = c.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Ticket not found")
    return db.row_to_dict(row)


@app.get("/api/health")
async def health():
    return {"api": True, "llm": await llm.llm_status(), "servicenow": await servicenow.check()}


STATUSES = ("open", "in_progress", "resolved", "closed")


def _counts(c) -> dict:
    q = lambda sql: c.execute(sql).fetchone()[0]
    return {"all": q("SELECT COUNT(*) FROM tickets"),
            "pending": q("SELECT COUNT(*) FROM tickets WHERE review_status='pending'"),
            "reviewed": q("SELECT COUNT(*) FROM tickets WHERE review_status IN ('approved','overridden')")}


@app.get("/api/tickets")
def list_tickets(limit: int = 30, offset: int = 0, q: str = "", status: str = "", review: str = "",
                 requester: str = ""):
    """review: pending | reviewed | auto. All filters are optional."""
    where, args = [], []
    if q:
        where.append("(short_description LIKE ? OR description LIKE ? OR requester LIKE ?)")
        args += [f"%{q}%"] * 3
    if status:
        where.append("status=?"); args.append(status)
    if requester:
        where.append("requester=?"); args.append(requester)
    if review == "reviewed":
        where.append("review_status IN ('approved','overridden')")
    elif review:
        where.append("review_status=?"); args.append(review)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    with db.conn() as c:
        rows = c.execute(f"SELECT * FROM tickets {clause} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                         (*args, limit, offset)).fetchall()
        total = c.execute(f"SELECT COUNT(*) FROM tickets {clause}", args).fetchone()[0]
        counts = _counts(c)
    return {"total": total, "counts": counts, "tickets": [db.row_to_dict(r) for r in rows]}


@app.get("/api/tickets/{ticket_id}")
def get_ticket(ticket_id: int):
    return _get(ticket_id)


class TicketPatch(BaseModel):
    status: str | None = None
    resolution_notes: str | None = None


@app.patch("/api/tickets/{ticket_id}")
def patch_ticket(ticket_id: int, p: TicketPatch):
    _get(ticket_id)
    sets, args = [], []
    if p.status is not None:
        if p.status not in STATUSES:
            raise HTTPException(400, f"status must be one of {STATUSES}")
        sets.append("status=?"); args.append(p.status)
        sets.append("resolved_at=?"); args.append(
            time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) if p.status in ("resolved", "closed") else None)
    if p.resolution_notes is not None:
        sets.append("resolution_notes=?"); args.append(p.resolution_notes.strip() or None)
    if sets:
        with db.conn() as c:
            c.execute(f"UPDATE tickets SET {', '.join(sets)} WHERE id=?", (*args, ticket_id))
    return _get(ticket_id)


class ReviewIn(BaseModel):
    action: str                      # approve | override
    category: str | None = None
    priority: str | None = None
    assignment_group: str | None = None


@app.post("/api/tickets/{ticket_id}/review")
def review_ticket(ticket_id: int, r: ReviewIn):
    """A human approves the AI's suggestion or overrides it. Overrides are what the override-rate metric counts."""
    t = _get(ticket_id)
    if not t["ai"]:
        raise HTTPException(400, "This ticket has no AI analysis to review yet")
    now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    if r.action == "approve":
        fields = dict(review_status="approved", reviewed_at=now, final_category=None, final_priority=None, final_group=None)
    elif r.action == "override":
        if r.category and r.category not in llm.CATEGORIES:
            raise HTTPException(400, f"category must be one of {llm.CATEGORIES}")
        if r.priority and r.priority not in llm.PRIORITIES:
            raise HTTPException(400, f"priority must be one of {llm.PRIORITIES}")
        if r.assignment_group and r.assignment_group not in llm.GROUPS:
            raise HTTPException(400, f"assignment_group must be one of {llm.GROUPS}")
        ai = t["ai"]
        changed = (r.category not in (None, ai["category"]) or r.priority not in (None, ai["priority"])
                   or r.assignment_group not in (None, ai["assignment_group"]))
        fields = dict(review_status="overridden" if changed else "approved", reviewed_at=now,
                      final_category=r.category if r.category != ai["category"] else None,
                      final_priority=r.priority if r.priority != ai["priority"] else None,
                      final_group=r.assignment_group if r.assignment_group != ai["assignment_group"] else None)
    else:
        raise HTTPException(400, "action must be 'approve' or 'override'")
    pipeline._set(ticket_id, **fields)
    return _get(ticket_id)


@app.post("/api/tickets")
async def create_ticket(t: TicketIn, auto: bool = True):
    """Create a ticket. With auto=true (default) AI analysis and incident creation start in the background."""
    with db.conn() as c:
        cur = c.execute(
            "INSERT INTO tickets (short_description, description, requester, pipeline) VALUES (?, ?, ?, ?)",
            (t.short_description, t.description, t.requester.strip()[:60] or "Anonymous", "analyzing" if auto else None),
        )
        tid = cur.lastrowid
    if auto:
        task = asyncio.create_task(pipeline.process(tid))
        _tasks.add(task)                      # keep a reference so it is not garbage collected
        task.add_done_callback(_tasks.discard)
    return _get(tid)


@app.post("/api/tickets/{ticket_id}/analyze")
async def analyze(ticket_id: int):
    _get(ticket_id)
    try:
        await pipeline.analyze_ticket(ticket_id)
    except Exception as e:
        raise HTTPException(502, f"AI analysis failed: {e}")
    return _get(ticket_id)


@app.post("/api/tickets/{ticket_id}/push")
async def push(ticket_id: int):
    _get(ticket_id)
    try:
        await pipeline.push_ticket(ticket_id)
    except ValueError as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        raise HTTPException(502, f"ServiceNow push failed: {e}")
    return _get(ticket_id)


@app.post("/api/demo/seed")
def demo_seed(background: int = 280):
    """Load synthetic labelled tickets (replaces earlier synthetic data and problems)."""
    return seed.seed(background)


@app.post("/api/demo/clear")
def demo_clear():
    """Remove synthetic demo tickets and the Problems detected from them (real tickets stay)."""
    with db.conn() as c:
        n = c.execute("DELETE FROM tickets WHERE is_synthetic=1").rowcount
        c.execute("DELETE FROM problems WHERE id NOT IN (SELECT DISTINCT problem_id FROM tickets WHERE problem_id IS NOT NULL)")
    return {"deleted_tickets": n}


@app.post("/api/problems/detect")
async def detect_problems(window_minutes: int = 60, min_size: int = 5, threshold: float | None = None):
    try:
        return await detect.detect(window_minutes, min_size, threshold)
    except Exception as e:
        raise HTTPException(502, f"Detection failed: {e}")


@app.get("/api/problems")
def list_problems():
    with db.conn() as c:
        rows = c.execute("SELECT * FROM problems ORDER BY id DESC").fetchall()
    return [db.row_to_dict(r) for r in rows]


@app.post("/api/evaluation/run")
async def evaluation_run(n: int = 20):
    """Start a background run: AI triage on n labelled synthetic tickets."""
    if evaluation.JOB["running"]:
        raise HTTPException(409, "An evaluation is already running")
    n = max(1, min(n, 100))
    batch = evaluation.pick(n)
    if not batch:
        raise HTTPException(400, "No unevaluated labelled tickets. Click 'Load demo data' on the home page first.")
    asyncio.create_task(evaluation.run(batch))
    return {"started": len(batch)}


@app.get("/api/evaluation")
def evaluation_metrics():
    return evaluation.metrics()


# ---------- Knowledge base (RAG) ----------
class ArticleIn(BaseModel):
    title: str
    category: str = "General"
    body: str


class AskIn(BaseModel):
    question: str


@app.get("/api/kb")
def kb_list():
    with db.conn() as c:
        rows = c.execute("SELECT * FROM kb_articles ORDER BY id DESC").fetchall()
    return [kb.article_dict(r) for r in rows]


@app.post("/api/kb")
async def kb_add(a: ArticleIn):
    try:
        return await kb.add_article(a.title.strip(), a.category.strip() or "General", a.body.strip())
    except Exception as e:
        raise HTTPException(502, f"Could not embed article: {e}")


@app.post("/api/kb/upload")
async def kb_upload(file: UploadFile = File(...), category: str = Form("General")):
    data = await file.read()
    try:
        return await kb.add_file(file.filename or "upload", data, category.strip() or "General")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"Could not process file: {e}")


@app.delete("/api/kb/file")
def kb_delete_file(name: str):
    with db.conn() as c:
        n = c.execute("DELETE FROM kb_articles WHERE source=?", (name,)).rowcount
    return {"deleted_passages": n}


@app.delete("/api/kb/{article_id}")
def kb_delete(article_id: int):
    with db.conn() as c:
        c.execute("DELETE FROM kb_articles WHERE id=?", (article_id,))
    return {"deleted": article_id}


@app.post("/api/kb/seed")
async def kb_seed():
    try:
        return await kb.seed()
    except Exception as e:
        raise HTTPException(502, f"Seeding failed: {e}")


@app.post("/api/kb/ask")
async def kb_ask(q: AskIn):
    try:
        return await kb.ask(q.question)
    except Exception as e:
        raise HTTPException(502, f"Ask failed: {e}")


@app.get("/api/dashboard")
def dashboard():
    with db.conn() as c:
        one = lambda sql, *a: c.execute(sql, a).fetchone()[0]
        rows = lambda sql, *a: [dict(r) for r in c.execute(sql, a).fetchall()]
        eff_cat = "COALESCE(final_category, json_extract(ai_json,'$.category'))"
        eff_pri = "COALESCE(final_priority, json_extract(ai_json,'$.priority'))"
        total = one("SELECT COUNT(*) FROM tickets")
        analysed = one("SELECT COUNT(*) FROM tickets WHERE ai_json IS NOT NULL")
        approved, overridden = one("SELECT COUNT(*) FROM tickets WHERE review_status='approved'"), \
                               one("SELECT COUNT(*) FROM tickets WHERE review_status='overridden'")
        auto = one("SELECT COUNT(*) FROM tickets WHERE review_status='auto'")
        reviewed = approved + overridden
        data = {
            "total": total, "analysed": analysed,
            "by_status": {r["status"]: r["n"] for r in rows("SELECT status, COUNT(*) n FROM tickets GROUP BY status")},
            "pending_review": one("SELECT COUNT(*) FROM tickets WHERE review_status='pending'"),
            "auto_handled": auto, "reviewed": reviewed, "overridden": overridden,
            "override_rate": round(100 * overridden / reviewed, 1) if reviewed else None,
            "avg_ai_seconds": one("SELECT ROUND(AVG(json_extract(ai_json,'$.latency_s')),1) FROM tickets WHERE ai_json IS NOT NULL"),
            "by_category": rows(f"SELECT COALESCE({eff_cat}, 'Not analysed') AS label, COUNT(*) n FROM tickets GROUP BY label ORDER BY (label = 'Not analysed'), n DESC"),
            "by_priority": rows(f"SELECT COALESCE({eff_pri}, 'Not analysed') AS label, COUNT(*) n FROM tickets GROUP BY label"),
            "per_day": rows("SELECT substr(created_at,1,10) AS day, COUNT(*) n FROM tickets GROUP BY day ORDER BY day DESC LIMIT 7")[::-1],
            "problems": rows("SELECT id, number, title, ticket_count, status, last_seen FROM problems ORDER BY id DESC LIMIT 5"),
            "kb": {"articles": one("SELECT COUNT(*) FROM kb_articles WHERE source IS NULL"),
                   "files": one("SELECT COUNT(DISTINCT source) FROM kb_articles WHERE source IS NOT NULL"),
                   "passages": one("SELECT COUNT(*) FROM kb_articles")},
        }
    order = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}
    data["by_priority"].sort(key=lambda r: order.get(r["label"], 9))   # "Not analysed" sorts last
    return data


class ChatIn(BaseModel):
    question: str
    history: list[dict] = []


@app.post("/api/assistant/chat")
async def assistant_chat(body: ChatIn):
    history = [m for m in body.history if m.get("role") in ("user", "assistant") and m.get("content")]
    try:
        return await kb.chat(body.question.strip(), history[-6:])
    except Exception as e:
        raise HTTPException(502, f"Assistant failed: {e}")
