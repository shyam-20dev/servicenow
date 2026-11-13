import json
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import asyncio

from . import db, detect, evaluation, kb, llm, seed, servicenow

app = FastAPI(title="ProblemLens API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup():
    db.init()


class TicketIn(BaseModel):
    short_description: str
    description: str


def _get(ticket_id: int) -> dict:
    with db.conn() as c:
        row = c.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Ticket not found")
    return db.row_to_dict(row)


@app.get("/api/health")
async def health():
    return {"api": True, "ollama": await llm.ollama_status(), "servicenow": await servicenow.check()}


@app.get("/api/tickets")
def list_tickets(limit: int = 30):
    with db.conn() as c:
        rows = c.execute("SELECT * FROM tickets ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)).fetchall()
        total = c.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
    return {"total": total, "tickets": [db.row_to_dict(r) for r in rows]}


@app.post("/api/tickets")
def create_ticket(t: TicketIn):
    with db.conn() as c:
        cur = c.execute(
            "INSERT INTO tickets (short_description, description) VALUES (?, ?)",
            (t.short_description, t.description),
        )
        tid = cur.lastrowid
    return _get(tid)


@app.post("/api/tickets/{ticket_id}/analyze")
async def analyze(ticket_id: int):
    t = _get(ticket_id)
    t0 = time.time()
    try:
        hits = await kb.retrieve(f"{t['short_description']}. {t['description']}")
        result = await llm.triage(t["short_description"], t["description"], context=hits)
    except Exception as e:
        raise HTTPException(502, f"AI analysis failed: {e}")
    ai = result.model_dump()
    ai["sources"] = [{k: h[k] for k in ("id", "title", "score")} for h in hits]
    ai["latency_s"] = round(time.time() - t0, 1)
    with db.conn() as c:
        c.execute("UPDATE tickets SET ai_json=? WHERE id=?", (json.dumps(ai), ticket_id))
    return _get(ticket_id)


@app.post("/api/tickets/{ticket_id}/push")
async def push(ticket_id: int):
    t = _get(ticket_id)
    if t["sn_number"]:
        raise HTTPException(409, f"Already pushed as {t['sn_number']}")
    try:
        res = await servicenow.create_incident(t)
    except Exception as e:
        raise HTTPException(502, f"ServiceNow push failed: {e}")
    with db.conn() as c:
        c.execute("UPDATE tickets SET sn_number=?, sn_sys_id=? WHERE id=?", (res["number"], res["sys_id"], ticket_id))
    return _get(ticket_id)


@app.post("/api/demo/seed")
def demo_seed(background: int = 280):
    """Load synthetic labelled tickets (replaces earlier synthetic data and problems)."""
    return seed.seed(background)


@app.post("/api/problems/detect")
async def detect_problems(window_minutes: int = 60, min_size: int = 5, threshold: float = 0.75):
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
