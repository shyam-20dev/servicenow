import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import db, detect, llm, seed, servicenow

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
    try:
        result = await llm.triage(t["short_description"], t["description"])
    except Exception as e:
        raise HTTPException(502, f"AI analysis failed: {e}")
    with db.conn() as c:
        c.execute("UPDATE tickets SET ai_json=? WHERE id=?", (json.dumps(result.model_dump()), ticket_id))
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
