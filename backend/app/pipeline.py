"""Ticket pipeline: AI analysis -> incident creation. Used by the buttons and by auto-submit."""
import json
import time

from . import db, kb, llm, servicenow


def get_ticket(ticket_id: int) -> dict | None:
    with db.conn() as c:
        row = c.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    return db.row_to_dict(row) if row else None


def _set(ticket_id: int, **fields) -> None:
    cols = ", ".join(f"{k}=?" for k in fields)
    with db.conn() as c:
        c.execute(f"UPDATE tickets SET {cols} WHERE id=?", (*fields.values(), ticket_id))


def assess(ticket_id: int) -> None:
    """Decide whether a human must evaluate this ticket, and why. (Never auto-closes a human decision.)"""
    t = get_ticket(ticket_id)
    ai = t["ai"]
    reasons = [r for r in t["review_reasons"] if r.startswith("Part of")]   # keep spike flags
    if not ai:
        reasons.append("AI analysis is missing or failed")
    else:
        if ai["priority"] in ("High", "Critical"):
            reasons.append(f"{ai['priority']} priority: a human should confirm")
        if ai.get("corrected"):
            reasons.append("AI gave an invalid value, replaced by a default")
        if ai["category"] == "Other":
            reasons.append("AI could not pick a clear category")
        if not ai.get("sources"):
            reasons.append("No knowledge-base article matched, so the answer is not grounded")
    _set(ticket_id, review_status="pending" if reasons else "auto",
         review_reasons=json.dumps(reasons), final_category=None, final_priority=None,
         final_group=None, reviewed_at=None)


def flag_for_review(ticket_ids: list[int], reason: str) -> None:
    """Add a reason (e.g. part of an incident spike) and put the ticket back in the human queue."""
    for tid in ticket_ids:
        t = get_ticket(tid)
        if not t or t["review_status"] in ("approved", "overridden"):
            continue
        reasons = t["review_reasons"] + ([reason] if reason not in t["review_reasons"] else [])
        _set(tid, review_status="pending", review_reasons=json.dumps(reasons))


async def analyze_ticket(ticket_id: int) -> None:
    """Retrieve matching KB articles, run AI triage, store the result."""
    t = get_ticket(ticket_id)
    t0 = time.time()
    hits = await kb.retrieve(f"{t['short_description']}. {t['description']}")
    result = await llm.triage(t["short_description"], t["description"], context=hits)
    ai = result.model_dump()
    ai["sources"] = [{k: h[k] for k in ("id", "title", "score")} for h in hits]
    ai["latency_s"] = round(time.time() - t0, 1)
    _set(ticket_id, ai_json=json.dumps(ai))
    assess(ticket_id)


async def push_ticket(ticket_id: int) -> None:
    """Create the incident (live ServiceNow or local mock) and store its number."""
    t = get_ticket(ticket_id)
    if t["sn_number"]:
        raise ValueError(f"Already pushed as {t['sn_number']}")
    res = await servicenow.create_incident(t)
    _set(ticket_id, sn_number=res["number"], sn_sys_id=res["sys_id"])


async def process(ticket_id: int) -> None:
    """Auto pipeline run in the background right after a ticket is submitted."""
    stage = "analyzing"
    try:
        _set(ticket_id, pipeline="analyzing", pipeline_error=None)
        await analyze_ticket(ticket_id)
        stage = "creating incident"
        _set(ticket_id, pipeline="creating_incident")
        await push_ticket(ticket_id)
        _set(ticket_id, pipeline="done")
    except Exception as e:
        _set(ticket_id, pipeline="error", pipeline_error=f"{stage} failed: {e}"[:300])
        if stage == "analyzing":
            _set(ticket_id, review_status="pending",
                 review_reasons=json.dumps([f"AI analysis failed: {str(e)[:120]}"]))
