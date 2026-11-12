"""Service requests (the USM idea): one workflow, many departments."""
from typing import Dict, List, Optional

from ..database import get_conn, now_iso
from ..schemas import RequestCreate

GROUP_FOR_DEPARTMENT = {
    "IT": "IT Service Desk",
    "HR": "HR Operations",
    "Finance": "Finance Shared Services",
    "Facilities": "Facilities Management",
}


def create_request(data: RequestCreate) -> Dict:
    ts = now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO service_requests (department, request_type, title, description, requester, priority, "
            "status, assignment_group, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (data.department, data.request_type, data.title, data.description, data.requester, data.priority,
             "Submitted", GROUP_FOR_DEPARTMENT[data.department], ts, ts),
        )
        rid = cur.lastrowid
        conn.execute("UPDATE service_requests SET number=? WHERE id=?", (f"REQ{2000000 + rid}", rid))
        row = conn.execute("SELECT * FROM service_requests WHERE id=?", (rid,)).fetchone()
    return dict(row)


def list_requests(department: Optional[str] = None, status: Optional[str] = None) -> List[Dict]:
    sql, params = "SELECT * FROM service_requests WHERE 1=1", []
    if department:
        sql += " AND department = ?"; params.append(department)
    if status:
        sql += " AND status = ?"; params.append(status)
    sql += " ORDER BY id DESC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def update_request(request_id: int, status: str) -> Optional[Dict]:
    with get_conn() as conn:
        cur = conn.execute("UPDATE service_requests SET status=?, updated_at=? WHERE id=?",
                           (status, now_iso(), request_id))
        if cur.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM service_requests WHERE id=?", (request_id,)).fetchone()
    return dict(row)
