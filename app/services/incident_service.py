"""Incident business logic: priority matrix, AI analysis (LLM or rule-based fallback), persistence."""
import json
from typing import Dict, List, Optional

from pydantic import ValidationError

from ..config import get_settings
from ..database import get_conn, now_iso
from ..schemas import AIAnalysis, IncidentCreate
from . import llm_service, rag_service
from .llm_service import LLMError

PRIORITY_LABELS = {1: "Critical", 2: "High", 3: "Moderate", 4: "Low"}
IMPACT_LABELS = {1: "High", 2: "Medium", 3: "Low"}

GROUP_FOR_CATEGORY = {
    "Network": "Network Support",
    "Hardware": "Hardware Support",
    "Software": "Application Support",
    "Access": "Identity & Access",
    "Other": "Service Desk",
}
TECHNICIAN_FOR_GROUP = {   # demo data only
    "Network Support": "Arjun Mehta",
    "Hardware Support": "Priya Nair",
    "Application Support": "Rahul Sharma",
    "Identity & Access": "Sneha Iyer",
    "Service Desk": "Karthik Raman",
}


def calculate_priority(impact: int, urgency: int) -> int:
    """Priority = f(impact, urgency), 1 (highest) .. 4 (lowest). Same idea as ServiceNow's matrix.

    impact/urgency: 1=High, 2=Medium, 3=Low.  sum 2 -> Critical, 3 -> High, 4 -> Moderate, 5-6 -> Low.
    """
    if impact not in (1, 2, 3) or urgency not in (1, 2, 3):
        raise ValueError("impact and urgency must be 1, 2 or 3")
    total = impact + urgency
    return {2: 1, 3: 2, 4: 3}.get(total, 4)


# --------------------------------------------------------------------------
# Rule-based fallback (NOT AI - plain keyword rules)
# --------------------------------------------------------------------------
KEYWORDS = {
    "Network": ["vpn", "wifi", "wi-fi", "internet", "network", "dns", "ethernet", "connect", "bandwidth", "proxy"],
    "Hardware": ["laptop", "printer", "keyboard", "mouse", "monitor", "battery", "screen", "hardware", "docking",
                 "charger", "overheat", "slow", "fan"],
    "Software": ["install", "software", "application", "app ", "crash", "excel", "outlook", "teams", "update",
                 "license", "error", "freeze", "office"],
    "Access": ["password", "login", "log in", "locked", "account", "permission", "access", "mfa", "sign in",
               "credentials", "unlock"],
}
RULE_STEPS = {
    "Network": ["Check that Wi-Fi/Ethernet is connected and other sites load.",
                "Disconnect and reconnect the VPN client; restart the client if it hangs.",
                "Restart the laptop and the network adapter.",
                "Check the IT status page for a wider network outage."],
    "Hardware": ["Restart the device and check cables, power and battery.",
                 "Check Task Manager / device manager for obvious faults.",
                 "Try the device with another cable, port or power source.",
                 "If the fault persists, arrange a hardware swap or repair."],
    "Software": ["Close and reopen the application; restart the computer.",
                 "Check for pending updates and install them.",
                 "Try Safe Mode or an online/web version to isolate the problem.",
                 "Reinstall or repair the application if the error continues."],
    "Access": ["Confirm the username and that Caps Lock is off.",
               "Wait 15 minutes if the account is locked, or use the self-service password reset portal.",
               "Verify MFA device/time settings.",
               "Ask the Identity & Access team to verify group membership and unlock the account."],
    "Other": ["Gather exact error messages, screenshots and when the problem started.",
              "Check whether other users are affected.",
              "Route to the service desk for triage."],
}


def rule_based_analysis(short_description: str, description: str) -> Dict:
    text = f"{short_description} {description}".lower()
    best, best_hits = "Other", 0
    for cat, words in KEYWORDS.items():
        hits = sum(1 for w in words if w in text)
        if hits > best_hits:
            best, best_hits = cat, hits
    impact = 1 if any(w in text for w in ["everyone", "all users", "whole team", "entire", "outage", "company-wide"]) else \
        (3 if any(w in text for w in ["minor", "cosmetic", "single feature"]) else 2)
    urgency = 1 if any(w in text for w in ["urgent", "cannot work", "can't work", "unable to work", "deadline",
                                           "production", "client", "critical", "asap"]) else \
        (3 if any(w in text for w in ["when possible", "no rush", "low priority"]) else 2)
    summary = short_description.strip()
    if len(summary) < 3:
        summary = description[:120]
    return {
        "summary": f"{summary} (rule-based summary: copied from the title)",
        "category": best,
        "impact": impact,
        "urgency": urgency,
        "troubleshooting_steps": RULE_STEPS[best],
        "recommended_resolution": f"Follow the {best} troubleshooting steps; escalate to {GROUP_FOR_CATEGORY[best]} if unresolved.",
        "ai_source": "rule-based fallback",
        "ai_note": "Generated by simple keyword rules, NOT by an LLM.",
    }


# --------------------------------------------------------------------------
# LLM analysis
# --------------------------------------------------------------------------
ANALYSIS_SYSTEM_PROMPT = (
    "You are an ITSM triage assistant. Analyse the incident and reply with ONE JSON object only, with exactly "
    "these keys: summary (string, max 30 words), category (one of: Network, Hardware, Software, Access, Other), "
    "impact (integer 1=high,2=medium,3=low: how many people/business are affected), urgency (integer 1=high,"
    "2=medium,3=low: how quickly it must be fixed), troubleshooting_steps (array of 3-6 short strings), "
    "recommended_resolution (string). If knowledge base excerpts are supplied, prefer them for the steps."
)


def llm_analysis(short_description: str, description: str) -> Dict:
    context = ""
    try:
        hits = rag_service.retrieve(f"{short_description}. {description}", k=2)["hits"]
        if hits:
            context = "\n\nKnowledge base excerpts:\n" + "\n---\n".join(h["excerpt"] for h in hits)
    except Exception:  # retrieval problems must never block ticket creation
        context = ""
    raw = llm_service.chat_json([
        {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
        {"role": "user", "content": f"Short description: {short_description}\nDescription: {description}{context}"},
    ])
    try:
        parsed = AIAnalysis(**raw)
    except (ValidationError, TypeError) as e:
        raise LLMError(f"The model output failed validation ({type(e).__name__}).")
    out = parsed.model_dump()
    out["ai_source"] = f"LLM ({get_settings().llm_model})"
    out["ai_note"] = "Generated by an LLM; validated against a schema. Review before acting."
    return out


def analyze_incident(short_description: str, description: str) -> Dict:
    if get_settings().llm_configured:
        try:
            return llm_analysis(short_description, description)
        except LLMError as e:
            result = rule_based_analysis(short_description, description)
            result["ai_note"] = f"LLM unavailable ({e}). Rule-based fallback used - NOT AI."
            return result
    result = rule_based_analysis(short_description, description)
    result["ai_note"] = "No LLM API key configured. Rule-based fallback used - NOT AI."
    return result


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------
def _row_to_incident(row) -> Dict:
    d = dict(row)
    d["ai_steps"] = json.loads(d["ai_steps"]) if d.get("ai_steps") else []
    d["priority_label"] = PRIORITY_LABELS.get(d["priority"], "Low")
    return d


def create_incident(data: IncidentCreate) -> Dict:
    analysis = analyze_incident(data.short_description, data.description)
    impact = data.impact or analysis["impact"]
    urgency = data.urgency or analysis["urgency"]
    priority = calculate_priority(impact, urgency)   # deterministic, never left to the LLM
    category = analysis["category"]
    group = GROUP_FOR_CATEGORY[category]
    ts = now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO incidents (short_description, description, category, impact, urgency, priority, status, "
            "assignment_group, assigned_to, reporter, ai_summary, ai_steps, ai_resolution, ai_source, ai_note, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (data.short_description, data.description, category, impact, urgency, priority, "New", group,
             TECHNICIAN_FOR_GROUP[group], data.reporter, analysis["summary"],
             json.dumps(analysis["troubleshooting_steps"]), analysis["recommended_resolution"],
             analysis["ai_source"], analysis["ai_note"], ts, ts),
        )
        iid = cur.lastrowid
        conn.execute("UPDATE incidents SET number = ? WHERE id = ?", (f"INC{1000000 + iid}", iid))
        row = conn.execute("SELECT * FROM incidents WHERE id = ?", (iid,)).fetchone()
    return _row_to_incident(row)


def get_incident(incident_id: int) -> Optional[Dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
    return _row_to_incident(row) if row else None


def list_incidents(status: Optional[str] = None, category: Optional[str] = None,
                   priority: Optional[int] = None, q: Optional[str] = None) -> List[Dict]:
    sql, params = "SELECT * FROM incidents WHERE 1=1", []
    if status:
        sql += " AND status = ?"; params.append(status)
    if category:
        sql += " AND category = ?"; params.append(category)
    if priority:
        sql += " AND priority = ?"; params.append(priority)
    if q:
        sql += " AND (short_description LIKE ? OR description LIKE ? OR number LIKE ?)"
        like = f"%{q}%"; params += [like, like, like]
    sql += " ORDER BY id DESC"
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_incident(r) for r in rows]


def update_incident(incident_id: int, status: Optional[str], assigned_to: Optional[str]) -> Optional[Dict]:
    sets, params = [], []
    if status:
        sets.append("status = ?"); params.append(status)
    if assigned_to is not None:
        sets.append("assigned_to = ?"); params.append(assigned_to.strip() or None)
    if not sets:
        return get_incident(incident_id)
    sets.append("updated_at = ?"); params.append(now_iso())
    params.append(incident_id)
    with get_conn() as conn:
        cur = conn.execute(f"UPDATE incidents SET {', '.join(sets)} WHERE id = ?", params)
        if cur.rowcount == 0:
            return None
    return get_incident(incident_id)
