"""Aggregations for the dashboard (plain SQL GROUP BY queries)."""
from typing import Dict

from ..database import get_conn
from .incident_service import PRIORITY_LABELS, list_incidents


def _count(conn, sql: str, params=()) -> int:
    return conn.execute(sql, params).fetchone()[0]


def get_dashboard() -> Dict:
    with get_conn() as conn:
        total = _count(conn, "SELECT COUNT(*) FROM incidents")
        open_ = _count(conn, "SELECT COUNT(*) FROM incidents WHERE status IN ('New','In Progress')")
        resolved = _count(conn, "SELECT COUNT(*) FROM incidents WHERE status IN ('Resolved','Closed')")
        pending_req = _count(conn, "SELECT COUNT(*) FROM service_requests WHERE status IN ('Submitted','Approved','In Progress')")
        total_req = _count(conn, "SELECT COUNT(*) FROM service_requests")
        prio = {PRIORITY_LABELS[p]: 0 for p in sorted(PRIORITY_LABELS)}
        for r in conn.execute("SELECT priority, COUNT(*) c FROM incidents GROUP BY priority"):
            prio[PRIORITY_LABELS.get(r["priority"], "Low")] += r["c"]
        by_category = {r["category"]: r["c"] for r in
                       conn.execute("SELECT category, COUNT(*) c FROM incidents GROUP BY category")}
        by_status = {r["status"]: r["c"] for r in
                     conn.execute("SELECT status, COUNT(*) c FROM incidents GROUP BY status")}
        by_dept = {r["department"]: r["c"] for r in
                   conn.execute("SELECT department, COUNT(*) c FROM service_requests GROUP BY department")}
        kb_docs = _count(conn, "SELECT COUNT(*) FROM knowledge_documents")
    return {
        "totals": {"incidents": total, "open_incidents": open_, "resolved_incidents": resolved,
                   "pending_requests": pending_req, "total_requests": total_req, "knowledge_documents": kb_docs},
        "priority_breakdown": prio,
        "category_breakdown": by_category,
        "status_breakdown": by_status,
        "requests_by_department": by_dept,
        "recent_incidents": list_incidents()[:6],
    }
