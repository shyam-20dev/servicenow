import uuid

import httpx

from . import config

PRIORITY_MAP = {"Critical": "1", "High": "2", "Medium": "3", "Low": "4"}


def _client() -> httpx.AsyncClient:
    if not (config.SN_INSTANCE and config.SN_USER and config.SN_PASSWORD):
        raise RuntimeError("ServiceNow credentials missing in .env")
    return httpx.AsyncClient(
        base_url=config.SN_INSTANCE,
        auth=(config.SN_USER, config.SN_PASSWORD),
        headers={"Accept": "application/json"},
        timeout=30,
    )


def is_mock() -> bool:
    return config.SN_MODE != "live"


async def check() -> dict:
    """Connectivity test: read one incident."""
    if is_mock():
        return {"ok": True, "mode": "mock"}
    try:
        async with _client() as c:
            r = await c.get("/api/now/table/incident", params={"sysparm_limit": 1})
        if r.status_code == 401:
            return {"ok": False, "error": "401 unauthorized: check SN_USER/SN_PASSWORD"}
        r.raise_for_status()
        return {"ok": True, "mode": "live", "instance": config.SN_INSTANCE}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def create_incident(ticket: dict) -> dict:
    if is_mock():
        # Simulation: no ServiceNow call; generate an INC-style number locally.
        return {"number": f"INC{1000 + ticket['id']:07d}", "sys_id": uuid.uuid4().hex}
    ai = ticket.get("ai") or {}
    body = {
        "short_description": ticket["short_description"],
        "description": ticket["description"],
        "category": (ai.get("category") or "inquiry").lower(),
    }
    if ai.get("priority"):
        body["urgency"] = body["impact"] = PRIORITY_MAP.get(ai["priority"], "3")
    if ai.get("summary"):
        body["work_notes"] = f"AI summary (needs human review): {ai['summary']}"
    async with _client() as c:
        r = await c.post("/api/now/table/incident", json=body)
        r.raise_for_status()
    res = r.json()["result"]
    return {"number": res["number"], "sys_id": res["sys_id"]}
