from fastapi import APIRouter, HTTPException

from ..database import get_conn
from ..schemas import ChatRequest
from ..services import rag_service

router = APIRouter(prefix="/api/assistant", tags=["AI Knowledge Assistant"])


@router.post("/chat")
def chat(body: ChatRequest):
    return rag_service.answer_question(body.message.strip(), body.session_id)


@router.get("/history")
def history(session_id: str = "demo-session", limit: int = 30):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content, mode, sources, created_at FROM chat_history "
            "WHERE session_id = ? ORDER BY id DESC LIMIT ?", (session_id, min(max(limit, 1), 100))).fetchall()
    return [dict(r) for r in reversed(rows)]
