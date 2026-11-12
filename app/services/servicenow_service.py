"""Optional ServiceNow integration using the Table REST API.

Rules followed here:
  * Credentials come only from environment variables.
  * We NEVER report success unless ServiceNow answered with HTTP 2xx and a sys_id.
  * No simulation: if not configured or the call fails, the result says so.
  * Passwords are never returned, logged or included in error messages.
"""
from typing import Dict
from urllib.parse import urlparse

import httpx

from ..config import get_settings
from ..database import get_conn, now_iso
from . import incident_service

# ServiceNow's default 'category' choices on the incident table.
SN_CATEGORY = {"Network": "network", "Hardware": "hardware", "Software": "software",
               "Access": "inquiry", "Other": "inquiry"}


def _base_url() -> str:
    """Validated instance URL. Requires https (http only for localhost development)."""
    s = get_settings()
    parsed = urlparse(s.sn_url)
    local = parsed.hostname in ("localhost", "127.0.0.1")
    if not parsed.hostname or parsed.scheme not in ("https", "http") or (parsed.scheme == "http" and not local):
        raise ValueError("SERVICENOW_INSTANCE_URL must look like https://devXXXXXX.service-now.com")
    return f"{parsed.scheme}://{parsed.netloc}"


def status() -> Dict:
    s = get_settings()
    host = urlparse(s.sn_url).hostname if s.sn_url else None
    return {"configured": s.servicenow_configured, "instance_host": host,
            "username_set": bool(s.sn_username), "password_set": bool(s.sn_password)}


def _error_for(resp: httpx.Response) -> str:
    code = resp.status_code
    if code == 401:
        return "ServiceNow rejected the credentials (401). Check SERVICENOW_USERNAME / SERVICENOW_PASSWORD."
    if code == 403:
        return "ServiceNow denied access (403). The user needs the 'itil' role (or table write ACL) on incident."
    if code == 404:
        return "ServiceNow returned 404. Check the instance URL; a hibernating PDI also answers like this."
    if code == 429:
        return "ServiceNow rate limit reached (429). Try again shortly."
    return f"ServiceNow returned HTTP {code}."


def _request(method: str, path: str, **kwargs) -> httpx.Response:
    s = get_settings()
    return httpx.request(
        method, f"{_base_url()}{path}", auth=(s.sn_username, s.sn_password),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=s.sn_timeout, **kwargs,
    )


def test_connection() -> Dict:
    """A real read-only API call. ok=True only if ServiceNow actually answered 200."""
    if not get_settings().servicenow_configured:
        return {"ok": False, "message": "ServiceNow is not configured (set the SERVICENOW_* variables in .env)."}
    try:
        resp = _request("GET", "/api/now/table/incident", params={"sysparm_limit": 1, "sysparm_fields": "number"})
    except ValueError as e:
        return {"ok": False, "message": str(e)}
    except httpx.TimeoutException:
        return {"ok": False, "message": "ServiceNow request timed out."}
    except httpx.HTTPError as e:
        return {"ok": False, "message": f"Could not reach ServiceNow ({type(e).__name__})."}
    if resp.status_code == 200:
        return {"ok": True, "message": "Connected: ServiceNow Table API answered successfully."}
    return {"ok": False, "message": _error_for(resp)}


def create_incident(incident_id: int) -> Dict:
    """Push a local incident into ServiceNow's incident table and store sys_id + number."""
    incident = incident_service.get_incident(incident_id)
    if incident is None:
        return {"ok": False, "not_found": True, "message": "Local incident not found."}
    if incident.get("sn_sys_id"):
        return {"ok": False, "message": f"Already created in ServiceNow as {incident['sn_number']}."}
    if not get_settings().servicenow_configured:
        _save(incident_id, "Not configured", None, None,
              "ServiceNow is not configured; nothing was sent.")
        return {"ok": False, "message": "ServiceNow is not configured. Nothing was sent."}

    description = (f"{incident['description']}\n\n--\nCreated from SmartDesk AI (local ticket {incident['number']}). "
                   f"AI summary: {incident.get('ai_summary') or 'n/a'}")
    payload = {
        "short_description": incident["short_description"],
        "description": description,
        "urgency": str(incident["urgency"]),
        "impact": str(incident["impact"]),
        "category": SN_CATEGORY.get(incident["category"], "inquiry"),
    }
    try:
        resp = _request("POST", "/api/now/table/incident", json=payload)
    except ValueError as e:
        _save(incident_id, "Failed", None, None, str(e))
        return {"ok": False, "message": str(e)}
    except httpx.TimeoutException:
        msg = "ServiceNow request timed out. The incident may or may not exist there; check before retrying."
        _save(incident_id, "Failed", None, None, msg)
        return {"ok": False, "message": msg}
    except httpx.HTTPError as e:
        msg = f"Could not reach ServiceNow ({type(e).__name__})."
        _save(incident_id, "Failed", None, None, msg)
        return {"ok": False, "message": msg}

    if resp.status_code not in (200, 201):
        msg = _error_for(resp)
        _save(incident_id, "Failed", None, None, msg)
        return {"ok": False, "message": msg}
    try:
        result = resp.json()["result"]
        sys_id, number = result["sys_id"], result["number"]
    except (ValueError, KeyError, TypeError):
        msg = "ServiceNow answered, but the response did not contain a sys_id/number. Not marking as created."
        _save(incident_id, "Failed", None, None, msg)
        return {"ok": False, "message": msg}

    msg = f"Created in ServiceNow as {number}."
    _save(incident_id, "Created", number, sys_id, msg)
    return {"ok": True, "message": msg, "sn_number": number, "sn_sys_id": sys_id}


def _save(incident_id: int, state: str, number, sys_id, message: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE incidents SET sn_status=?, sn_number=?, sn_sys_id=?, sn_message=?, updated_at=? WHERE id=?",
            (state, number, sys_id, message, now_iso(), incident_id),
        )
