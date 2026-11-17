"""ServiceNow as the system of record for tickets (incident table) and Problems (problem table).

SQLite stays as a local cache so the dashboard, filters and clustering stay fast. Writes go
through to ServiceNow: SQL triggers flag changed rows (sn_dirty / sn_ver) and a background worker
pushes them. A periodic pull brings ServiceNow-side changes (e.g. a fulfiller resolving an incident)
back into the cache, and rebuilds the cache if the local database is lost.

Custom columns are created on demand through the Table API. On a scoped-app session ServiceNow
prefixes them (x_<scope>_u_pl_*), so the real column names are looked up at startup.
"""
import asyncio
import json
import time
import uuid

from . import config, db, servicenow

# (urgency, impact): ServiceNow only accepts 1-3 and derives priority 1-5 from the pair
PRIORITY_MAP = {"Critical": ("1", "1"), "High": ("1", "2"), "Medium": ("2", "2"), "Low": ("3", "2")}
STATE_OUT = {"open": "1", "in_progress": "2", "resolved": "6", "closed": "7"}
STATE_IN = {"1": "open", "2": "in_progress", "3": "in_progress", "4": "in_progress", "5": "in_progress",
            "6": "resolved", "7": "closed", "8": "closed"}

# logical name -> max length (all custom columns are strings)
INCIDENT_FIELDS = {"local_id": 20, "ai_json": 8000, "assignment_group": 60, "review_status": 20,
                   "review_reasons": 2000, "final_category": 30, "final_priority": 30, "final_group": 60,
                   "requester": 100, "reviewed_at": 30, "problem": 20}
PROBLEM_FIELDS = {"local_id": 20, "actions_json": 4000, "ticket_count": 10, "status": 20,
                  "first_seen": 30, "last_seen": 30}

COLS: dict[str, dict[str, str]] = {"incident": {}, "problem": {}}   # logical -> real column name
CLOSE_CODE = {"value": config.SN_CLOSE_CODE or "Solved (Permanently)"}   # resolution code sent when a ticket is resolved
STATE = {"schema_ok": False, "schema_error": None, "last_push": None, "last_pull": None, "last_error": None}

_lock = asyncio.Lock()          # one ServiceNow write at a time: no duplicate incidents from racing tasks
_backoff: dict[str, float] = {}
_worker_task: asyncio.Task | None = None


def live() -> bool:
    return not servicenow.is_mock()


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())


# ---------------- schema ----------------
async def ensure_schema() -> None:
    """Create the custom columns that are missing and learn their real names."""
    if not live():
        return
    try:
        async with servicenow._client() as c:
            for table, fields in (("incident", INCIDENT_FIELDS), ("problem", PROBLEM_FIELDS)):
                r = await c.get("/api/now/table/sys_dictionary", params={
                    "sysparm_query": f"name={table}^elementLIKEu_pl_", "sysparm_fields": "element",
                    "sysparm_limit": 200})
                r.raise_for_status()
                found = {}
                for row in r.json()["result"]:
                    el = row["element"]
                    found[el.split("u_pl_", 1)[1]] = el
                for key, size in fields.items():
                    if key not in found:
                        r = await c.post("/api/now/table/sys_dictionary", json={
                            "name": table, "element": f"u_pl_{key}", "column_label": f"ProblemLens {key}",
                            "internal_type": "string", "max_length": str(size)})
                        r.raise_for_status()
                        found[key] = r.json()["result"]["element"]
                COLS[table] = {k: found[k] for k in fields}
            if not config.SN_CLOSE_CODE:   # instances customise this choice list: use a valid "permanent fix" value
                r = await c.get("/api/now/table/sys_choice", params={
                    "sysparm_query": "name=incident^element=close_code^inactive=false", "sysparm_fields": "value"})
                values = [x["value"] for x in r.json().get("result", [])] if r.status_code == 200 else []
                if values:
                    CLOSE_CODE["value"] = next((v for v in values if "permanent" in v.lower()), values[0])
        STATE.update(schema_ok=True, schema_error=None)
    except Exception as e:
        STATE.update(schema_ok=False, schema_error=str(e)[:300])
        print("ServiceNow schema setup failed:", e, flush=True)


def _custom(table: str, values: dict) -> dict:
    """Map logical custom fields to real column names (skipped if the schema is not ready)."""
    cols = COLS[table]
    return {cols[k]: ("" if v is None else str(v)) for k, v in values.items() if k in cols}


# ---------------- tickets -> incident ----------------
def _ticket(c, tid: int) -> dict | None:
    row = c.execute("SELECT * FROM tickets WHERE id=?", (tid,)).fetchone()
    return (db.row_to_dict(row) | {"sn_ver": row["sn_ver"]}) if row else None


def _incident_body(t: dict, problem_number: str | None) -> dict:
    ai, eff = t["ai"], t["effective"]
    category = (eff["category"] if eff else "inquiry").lower()
    body = {
        "short_description": t["short_description"],
        "description": t["description"],
        "category": "inquiry" if category == "other" else category,
        "state": STATE_OUT.get(t["status"], "1"),
    }
    if eff:
        body["urgency"], body["impact"] = PRIORITY_MAP.get(eff["priority"], ("2", "2"))
    if t["status"] in ("resolved", "closed"):
        body["close_code"] = CLOSE_CODE["value"]
        body["close_notes"] = t.get("resolution_notes") or "Resolved via ProblemLens"
    ai_json = json.dumps(ai) if ai else ""
    if len(ai_json) > INCIDENT_FIELDS["ai_json"] and ai:
        ai_json = json.dumps({k: v for k, v in ai.items() if k != "sources"})
    body |= _custom("incident", {
        "local_id": t["id"], "ai_json": ai_json, "assignment_group": eff["assignment_group"] if eff else "",
        "review_status": t.get("review_status"), "review_reasons": json.dumps(t["review_reasons"]),
        "final_category": t.get("final_category"), "final_priority": t.get("final_priority"),
        "final_group": t.get("final_group"), "requester": t.get("requester"),
        "reviewed_at": t.get("reviewed_at"), "problem": problem_number})
    return body


async def sync_ticket(tid: int) -> dict:
    """Create or update the ServiceNow incident for a ticket. Returns {'number', 'sys_id'}."""
    async with _lock:
        with db.conn() as c:
            t = _ticket(c, tid)
        if not t:
            raise ValueError(f"Ticket {tid} not found")
        if not live():                      # simulation: invent a number once, keep everything local
            if not t["sn_sys_id"]:
                res = {"number": f"INC{1000 + tid:07d}", "sys_id": uuid.uuid4().hex}
                with db.conn() as c:
                    c.execute("UPDATE tickets SET sn_number=?, sn_sys_id=? WHERE id=?", (res["number"], res["sys_id"], tid))
                return res
            return {"number": t["sn_number"], "sys_id": t["sn_sys_id"]}

        problem_number = None
        if t["problem_id"]:
            await _sync_problem_locked(t["problem_id"])
            with db.conn() as c:
                row = c.execute("SELECT number FROM problems WHERE id=?", (t["problem_id"],)).fetchone()
            problem_number = row["number"] if row else None
        body = _incident_body(t, problem_number)
        sys_id = t["sn_sys_id"]
        async with servicenow._client() as cl:
            r = None
            if sys_id:
                r = await cl.patch(f"/api/now/table/incident/{sys_id}", json=body)
                if r.status_code == 404:    # record is gone (or the id came from the old simulation)
                    sys_id, r = None, None
            if not sys_id:   # new ticket, or the stored id is gone / came from the old simulation
                body["work_notes"] = ("AI summary (needs human review): " + t["ai"]["summary"]) \
                    if t["ai"] and t["ai"].get("summary") else "Created by ProblemLens"
                r = await cl.post("/api/now/table/incident", json=body)
            if r.status_code >= 400:
                raise RuntimeError(f"ServiceNow {r.status_code}: {r.text[:200]}")
        res = r.json()["result"]
        out = {"number": res["number"], "sys_id": res["sys_id"]}
        with db.conn() as c:
            c.execute("UPDATE tickets SET sn_number=?, sn_sys_id=? WHERE id=?", (out["number"], out["sys_id"], tid))
            c.execute("UPDATE tickets SET sn_dirty=0, sn_error=NULL WHERE id=? AND sn_ver=?", (tid, t["sn_ver"]))
        return out


# ---------------- problems -> problem ----------------
async def _sync_problem_locked(pid: int) -> str | None:
    with db.conn() as c:
        row = c.execute("SELECT * FROM problems WHERE id=?", (pid,)).fetchone()
        if not row:
            return None
        real = c.execute("SELECT COUNT(*) FROM tickets WHERE problem_id=? AND is_synthetic=0", (pid,)).fetchone()[0]
        if not real:                        # clusters of demo tickets are not sent to ServiceNow
            c.execute("UPDATE problems SET sn_dirty=0 WHERE id=?", (pid,))
            return row["number"]
        p, ver = db.row_to_dict(row), row["sn_ver"]
    if not live():
        with db.conn() as c:
            c.execute("UPDATE problems SET sn_dirty=0 WHERE id=? AND sn_ver=?", (pid, ver))
        return p["number"]
    body = {"short_description": p["title"], "description": p["root_cause"] or ""}
    body |= _custom("problem", {"local_id": pid, "actions_json": json.dumps(p["actions"]),
                                "ticket_count": p["ticket_count"], "status": p["status"],
                                "first_seen": p["first_seen"], "last_seen": p["last_seen"]})
    sys_id = p["sn_sys_id"]
    async with servicenow._client() as cl:
        r = None
        if sys_id:
            r = await cl.patch(f"/api/now/table/problem/{sys_id}", json=body)
            if r.status_code == 404:
                sys_id, r = None, None
        if not sys_id:
            if p["actions"]:
                body["work_notes"] = "Proposed actions:\n" + "\n".join(f"- {a}" for a in p["actions"])
            r = await cl.post("/api/now/table/problem", json=body)
        if r.status_code >= 400:
            raise RuntimeError(f"ServiceNow {r.status_code}: {r.text[:200]}")
    res = r.json()["result"]
    with db.conn() as c:
        c.execute("UPDATE problems SET number=?, sn_sys_id=? WHERE id=?", (res["number"], res["sys_id"], pid))
        c.execute("UPDATE problems SET sn_dirty=0, sn_error=NULL WHERE id=? AND sn_ver=?", (pid, ver))
    return res["number"]


async def sync_problem(pid: int) -> str | None:
    """Create or update the ServiceNow problem. Returns its number (ServiceNow's, in live mode)."""
    async with _lock:
        return await _sync_problem_locked(pid)


# ---------------- pull: ServiceNow -> cache ----------------
def _val(v):
    return v.get("value") if isinstance(v, dict) else v


async def pull() -> dict:
    """Refresh the cache from ServiceNow; rebuild rows missing locally. Local unsynced edits win."""
    if not (live() and STATE["schema_ok"]):
        return {"skipped": True}
    stats = {"problems_added": 0, "tickets_added": 0, "tickets_updated": 0}
    async with servicenow._client() as cl:
        pc, ic = COLS["problem"], COLS["incident"]
        r = await cl.get("/api/now/table/problem", params={
            "sysparm_query": f"{pc['local_id']}ISNOTEMPTY", "sysparm_limit": 1000,
            "sysparm_fields": ",".join(["sys_id", "number", "short_description", "description", "sys_created_on", *pc.values()])})
        r.raise_for_status()
        problems = r.json()["result"]
        r = await cl.get("/api/now/table/incident", params={
            "sysparm_query": f"{ic['local_id']}ISNOTEMPTY", "sysparm_limit": 1000,
            "sysparm_fields": ",".join(["sys_id", "number", "short_description", "description", "state",
                                        "close_notes", "sys_created_on", *ic.values()])})
        r.raise_for_status()
        incidents = r.json()["result"]

    with db.conn() as c:
        local_p = {row["sn_sys_id"]: row["id"] for row in c.execute("SELECT id, sn_sys_id FROM problems WHERE sn_sys_id IS NOT NULL")}
        for p in problems:
            if p["sys_id"] in local_p:
                continue
            try:
                actions = json.loads(p.get(pc["actions_json"]) or "[]")
            except ValueError:
                actions = []
            cur = c.execute(
                "INSERT INTO problems (number, title, root_cause, actions_json, status, ticket_count, first_seen, last_seen,"
                " created_at, sn_sys_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (p["number"], p["short_description"], p["description"], json.dumps(actions),
                 p.get(pc["status"]) or "proposed", int(p.get(pc["ticket_count"]) or 0),
                 p.get(pc["first_seen"]), p.get(pc["last_seen"]), p["sys_created_on"], p["sys_id"]))
            c.execute("UPDATE problems SET sn_dirty=0 WHERE id=?", (cur.lastrowid,))
            local_p[p["sys_id"]] = cur.lastrowid
            stats["problems_added"] += 1

        local_p_by_number = {r["number"]: r["id"] for r in c.execute("SELECT id, number FROM problems")}
        local_t = {row["sn_sys_id"]: row for row in c.execute("SELECT id, sn_sys_id, sn_dirty, status, short_description, description FROM tickets WHERE sn_sys_id IS NOT NULL")}
        for i in incidents:
            status = STATE_IN.get(str(i["state"]), "open")
            have = local_t.get(i["sys_id"])
            if have:
                if not have["sn_dirty"] and (have["status"], have["short_description"], have["description"]) != (
                        status, i["short_description"], i["description"]):
                    c.execute("UPDATE tickets SET status=?, short_description=?, description=? WHERE id=?",
                              (status, i["short_description"], i["description"], have["id"]))
                    c.execute("UPDATE tickets SET sn_dirty=0 WHERE id=?", (have["id"],))
                    stats["tickets_updated"] += 1
                continue
            try:
                ai = json.loads(i.get(ic["ai_json"]) or "null")
            except ValueError:
                ai = None
            try:
                reasons = json.loads(i.get(ic["review_reasons"]) or "[]")
            except ValueError:
                reasons = []
            cur = c.execute(
                "INSERT INTO tickets (short_description, description, status, ai_json, sn_number, sn_sys_id, created_at,"
                " requester, review_status, review_reasons, final_category, final_priority, final_group, reviewed_at,"
                " resolution_notes, problem_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (i["short_description"], i["description"], status, json.dumps(ai) if ai else None, i["number"], i["sys_id"],
                 i["sys_created_on"], i.get(ic["requester"]) or "Anonymous", i.get(ic["review_status"]) or None,
                 json.dumps(reasons), i.get(ic["final_category"]) or None, i.get(ic["final_priority"]) or None,
                 i.get(ic["final_group"]) or None, i.get(ic["reviewed_at"]) or None, i.get("close_notes") or None,
                 local_p_by_number.get(i.get(ic["problem"]))))
            c.execute("UPDATE tickets SET sn_dirty=0 WHERE id=?", (cur.lastrowid,))
            stats["tickets_added"] += 1
    STATE["last_pull"] = _now()
    return stats


# ---------------- background push ----------------
async def push_dirty() -> dict:
    """Push every changed row once. Failing rows are retried after a pause."""
    done = failed = 0
    with db.conn() as c:
        tickets = [r["id"] for r in c.execute(
            "SELECT id FROM tickets WHERE sn_dirty=1 AND is_synthetic=0 AND sn_sys_id IS NOT NULL "
            "AND COALESCE(pipeline,'') NOT IN ('analyzing','creating_incident')")]
        problems = [r["id"] for r in c.execute("SELECT id FROM problems WHERE sn_dirty=1")]
    for kind, ids in (("problems", problems), ("tickets", tickets)):
        for i in ids:
            key = f"{kind}:{i}"
            if _backoff.get(key, 0) > time.time():
                continue
            try:
                if kind == "tickets":
                    await sync_ticket(i)
                else:
                    await sync_problem(i)
                _backoff.pop(key, None)
                done += 1
            except Exception as e:
                failed += 1
                _backoff[key] = time.time() + 60
                STATE["last_error"] = f"{kind[:-1]} {i}: {e}"[:300]
                with db.conn() as c:
                    c.execute(f"UPDATE {kind} SET sn_error=? WHERE id=?", (str(e)[:300], i))
    STATE["last_push"] = _now()
    return {"pushed": done, "failed": failed}


async def _worker() -> None:
    last_pull = 0.0
    while True:
        try:
            if live():
                if not STATE["schema_ok"]:
                    await ensure_schema()
                if STATE["schema_ok"]:
                    await push_dirty()
                    if time.time() - last_pull > 60:
                        last_pull = time.time()
                        await pull()
        except Exception as e:
            STATE["last_error"] = str(e)[:300]
            print("sn sync worker:", e, flush=True)
        await asyncio.sleep(5)


async def start() -> None:
    """Called at app startup: set up columns, restore the cache from ServiceNow, start the push worker."""
    global _worker_task
    if live():
        await ensure_schema()
        try:
            print("ServiceNow pull:", await pull(), flush=True)
        except Exception as e:
            print("ServiceNow initial pull failed:", e, flush=True)
    _worker_task = asyncio.create_task(_worker())


def status() -> dict:
    with db.conn() as c:
        q = lambda sql: c.execute(sql).fetchone()[0]
        pending = {"tickets": q("SELECT COUNT(*) FROM tickets WHERE sn_dirty=1 AND is_synthetic=0 AND sn_sys_id IS NOT NULL"),
                   "problems": q("SELECT COUNT(*) FROM problems WHERE sn_dirty=1")}
    return {"mode": "live" if live() else "mock", "pending": pending, **STATE}
