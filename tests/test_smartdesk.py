import json

import httpx
import pytest

from app.schemas import IncidentCreate
from app.services import incident_service, llm_service, rag_service, servicenow_service


# ---------- priority ----------
@pytest.mark.parametrize("impact,urgency,expected", [(1, 1, 1), (1, 2, 2), (2, 1, 2), (2, 2, 3), (3, 1, 3), (3, 3, 4), (2, 3, 4)])
def test_priority_matrix(impact, urgency, expected):
    assert incident_service.calculate_priority(impact, urgency) == expected


def test_priority_rejects_bad_values():
    with pytest.raises(ValueError):
        incident_service.calculate_priority(0, 2)


# ---------- fallback AI ----------
def test_rule_based_fallback_is_labelled_and_classifies():
    r = incident_service.analyze_incident("VPN will not connect", "Cannot connect to VPN from home, urgent client deadline")
    assert r["category"] == "Network"
    assert "fallback" in r["ai_source"] and "NOT AI" in r["ai_note"]
    assert r["urgency"] == 1 and r["troubleshooting_steps"]


def test_fallback_other_category():
    assert incident_service.rule_based_analysis("Something odd", "Strange thing happened yesterday")["category"] == "Other"


# ---------- incidents API ----------
def test_create_incident_and_fetch(client):
    r = client.post("/api/incidents", json={"short_description": "Laptop battery drains fast",
                                            "description": "The laptop battery goes from 100 to 0 in one hour."})
    assert r.status_code == 201
    inc = r.json()
    assert inc["number"].startswith("INC") and inc["status"] == "New"
    assert inc["category"] == "Hardware" and inc["assigned_to"]
    assert inc["ai_source"] == "rule-based fallback"
    assert client.get(f"/api/incidents/{inc['id']}").json()["number"] == inc["number"]


def test_manual_impact_urgency_drive_priority(client):
    r = client.post("/api/incidents", json={"short_description": "Email down for all", "description": "Nobody can send email at all.",
                                            "impact": 1, "urgency": 1}).json()
    assert r["priority"] == 1 and r["priority_label"] == "Critical"


def test_update_status_filter_and_search(client):
    inc = client.post("/api/incidents", json={"short_description": "Printer jam floor 4", "description": "Printer on floor 4 has a paper jam."}).json()
    p = client.patch(f"/api/incidents/{inc['id']}", json={"status": "Resolved"})
    assert p.status_code == 200 and p.json()["status"] == "Resolved"
    assert any(i["id"] == inc["id"] for i in client.get("/api/incidents?status=Resolved&q=jam").json())
    assert client.patch("/api/incidents/99999", json={"status": "Closed"}).status_code == 404


# ---------- validation ----------
def test_validation_errors(client):
    assert client.post("/api/incidents", json={"short_description": "x", "description": "short"}).status_code == 422
    assert client.post("/api/incidents", json={"short_description": "Valid title", "description": "Valid long description", "impact": 9}).status_code == 422
    assert client.patch("/api/incidents/1", json={"status": "Exploded"}).status_code == 422
    assert client.get("/api/incidents?status=Bogus").status_code == 422
    assert client.post("/api/assistant/chat", json={"message": "x"}).status_code == 422


# ---------- service requests ----------
def test_service_request_departments(client):
    r = client.post("/api/requests", json={"department": "HR", "request_type": "Employment letter",
                                           "title": "Letter for visa", "description": "Need an employment letter for a visa."})
    assert r.status_code == 201 and r.json()["assignment_group"] == "HR Operations"
    bad = client.post("/api/requests", json={"department": "HR", "request_type": "Hardware request",
                                             "title": "Wrong catalog", "description": "This type belongs to IT only."})
    assert bad.status_code == 422
    rid = r.json()["id"]
    assert client.patch(f"/api/requests/{rid}", json={"status": "Approved"}).json()["status"] == "Approved"


# ---------- RAG ----------
def test_chunking_splits_long_text():
    text = "\n\n".join(f"Paragraph {i} " + "word " * 80 for i in range(10))
    chunks = rag_service.chunk_text(text, size=700)
    assert len(chunks) > 1 and all(len(c) <= 760 for c in chunks)


def test_knowledge_base_loaded(client):
    docs = client.get("/api/knowledge").json()
    assert len(docs) >= 7 and all(d["chunk_count"] > 0 for d in docs)


@pytest.mark.parametrize("question,expected_doc", [
    ("My VPN is not connecting.", "vpn_troubleshooting.md"),
    ("How do I reset my password?", "password_reset.md"),
    ("My laptop is running slowly.", "laptop_performance.md"),
    ("The printer is offline", "printer_issues.md"),
    ("My account is locked out", "account_lockout.md"),
])
def test_retrieval_finds_right_document(client, question, expected_doc):
    hits = rag_service.retrieve(question)["hits"]
    assert hits and hits[0]["document"] == expected_doc


def test_no_knowledge_is_honest(client):
    r = client.post("/api/assistant/chat", json={"message": "What is the capital of France?"}).json()
    assert r["answer_mode"] == "no-knowledge" and r["sources"] == []
    assert "does not contain" in r["answer"]


def test_assistant_without_llm_is_labelled_fallback(client):
    r = client.post("/api/assistant/chat", json={"message": "My VPN is not connecting."}).json()
    assert r["answer_mode"] == "extractive-fallback" and r["retrieval_mode"] == "keyword"
    assert "NOT a generated answer" in r["answer"] and r["sources"][0]["document"] == "vpn_troubleshooting.md"


def test_upload_txt_and_retrieve(client):
    files = {"file": ("badge_policy.txt", b"Lost badge policy. If you lose your access badge, report it to Facilities within 24 hours so the old badge can be deactivated.", "text/plain")}
    assert client.post("/api/knowledge/upload", files=files).status_code == 201
    assert rag_service.retrieve("I lost my access badge")["hits"][0]["document"] == "badge_policy.txt"


def test_upload_rejects_bad_type(client):
    assert client.post("/api/knowledge/upload", files={"file": ("x.exe", b"MZ....", "application/octet-stream")}).status_code == 400


def test_cosine_similarity():
    assert rag_service.cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert rag_service.cosine([1, 0], [0, 1]) == pytest.approx(0.0)


def test_semantic_retrieval_with_mocked_embeddings(client, monkeypatch):
    """Semantic path: fake embedding vectors, check ranking by cosine similarity."""
    monkeypatch.setenv("EMBEDDING_API_KEY", "fake")
    def fake_embed(texts):
        return [[1.0, 0.0] if ("vpn" in t.lower() or "VPN" in t) else [0.0, 1.0] for t in texts]
    monkeypatch.setattr(llm_service, "embed", fake_embed)
    rag_service.reindex_all()
    out = rag_service.retrieve("vpn problem")
    docs = {h["document"] for h in out["hits"]}
    assert out["mode"] == "semantic"
    assert "vpn_troubleshooting.md" in docs          # vectors pointing the same way are retrieved
    assert "printer_issues.md" not in docs           # orthogonal vectors (cosine 0) are filtered out


# ---------- mocked LLM ----------
def test_llm_incident_analysis_validated(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fake")
    good = {"summary": "VPN drops", "category": "network", "impact": 2, "urgency": 1,
            "troubleshooting_steps": ["Restart client", "Flush DNS"], "recommended_resolution": "Reconnect VPN"}
    monkeypatch.setattr(llm_service, "chat", lambda *a, **k: "```json\n" + json.dumps(good) + "\n```")
    r = client.post("/api/incidents", json={"short_description": "VPN drops", "description": "VPN drops every few minutes."}).json()
    assert r["category"] == "Network" and r["ai_source"].startswith("LLM") and r["priority"] == 2


def test_malformed_llm_output_falls_back(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fake")
    monkeypatch.setattr(llm_service, "chat", lambda *a, **k: "Sorry, I cannot do that")
    r = client.post("/api/incidents", json={"short_description": "VPN drops", "description": "VPN drops every few minutes."}).json()
    assert r["ai_source"] == "rule-based fallback" and "LLM unavailable" in r["ai_note"]


def test_llm_error_message_hides_key(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-super-secret")
    def boom(*a, **k):
        raise httpx.ConnectError("boom sk-super-secret")
    monkeypatch.setattr(httpx, "post", boom)
    with pytest.raises(llm_service.LLMError) as e:
        llm_service.chat([{"role": "user", "content": "hi"}])
    assert "sk-super-secret" not in str(e.value)


def test_parse_json_variants():
    assert llm_service.parse_json_object('Here: {"a": 1} thanks') == {"a": 1}
    with pytest.raises(llm_service.LLMError):
        llm_service.parse_json_object("no json here")


# ---------- ServiceNow ----------
def test_servicenow_missing_credentials_graceful(client):
    inc = client.post("/api/incidents", json={"short_description": "VPN drops", "description": "VPN drops every few minutes."}).json()
    r = client.post("/api/servicenow/incidents", json={"incident_id": inc["id"]}).json()
    assert r["ok"] is False and "not configured" in r["message"]
    assert client.get(f"/api/incidents/{inc['id']}").json()["sn_sys_id"] is None
    assert client.post("/api/servicenow/test").json()["ok"] is False
    assert client.get("/api/servicenow/status").json()["configured"] is False
    assert client.post("/api/servicenow/incidents", json={"incident_id": 99999}).status_code == 404


def _configure_sn(monkeypatch):
    monkeypatch.setenv("SERVICENOW_INSTANCE_URL", "https://dev000000.service-now.com")
    monkeypatch.setenv("SERVICENOW_USERNAME", "api.user")
    monkeypatch.setenv("SERVICENOW_PASSWORD", "pw-secret")


def test_servicenow_success_stores_sys_id(client, monkeypatch):
    _configure_sn(monkeypatch)
    seen = {}
    def fake_request(method, url, **kw):
        seen.update(method=method, url=url, json=kw.get("json"))
        return httpx.Response(201, json={"result": {"sys_id": "abc123", "number": "INC0010099"}}, request=httpx.Request(method, url))
    monkeypatch.setattr(httpx, "request", fake_request)
    inc = client.post("/api/incidents", json={"short_description": "VPN drops", "description": "VPN drops every few minutes."}).json()
    r = client.post("/api/servicenow/incidents", json={"incident_id": inc["id"]}).json()
    assert r["ok"] and r["sn_number"] == "INC0010099"
    assert seen["url"].endswith("/api/now/table/incident")
    assert {"short_description", "description", "urgency", "impact", "category"} <= set(seen["json"])
    stored = client.get(f"/api/incidents/{inc['id']}").json()
    assert stored["sn_sys_id"] == "abc123" and stored["sn_number"] == "INC0010099"


def test_servicenow_failure_never_claims_success(client, monkeypatch):
    _configure_sn(monkeypatch)
    monkeypatch.setattr(httpx, "request", lambda m, u, **kw: httpx.Response(401, json={}, request=httpx.Request(m, u)))
    inc = client.post("/api/incidents", json={"short_description": "VPN drops", "description": "VPN drops every few minutes."}).json()
    r = client.post("/api/servicenow/incidents", json={"incident_id": inc["id"]}).json()
    assert r["ok"] is False and "401" in r["message"] and "pw-secret" not in r["message"]
    stored = client.get(f"/api/incidents/{inc['id']}").json()
    assert stored["sn_sys_id"] is None and stored["sn_status"] == "Failed"


def test_servicenow_timeout_handled(client, monkeypatch):
    _configure_sn(monkeypatch)
    def timeout(*a, **k):
        raise httpx.ConnectTimeout("t")
    monkeypatch.setattr(httpx, "request", timeout)
    inc = client.post("/api/incidents", json={"short_description": "VPN drops", "description": "VPN drops every few minutes."}).json()
    assert client.post("/api/servicenow/incidents", json={"incident_id": inc["id"]}).json()["ok"] is False


def test_servicenow_rejects_plain_http_url(monkeypatch):
    monkeypatch.setenv("SERVICENOW_INSTANCE_URL", "http://evil.example.com")
    monkeypatch.setenv("SERVICENOW_USERNAME", "u"); monkeypatch.setenv("SERVICENOW_PASSWORD", "p")
    assert servicenow_service.test_connection()["ok"] is False


# ---------- dashboard / system ----------
def test_dashboard_and_settings_do_not_leak_secrets(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-leak-check")
    monkeypatch.setenv("SERVICENOW_PASSWORD", "pw-leak-check")
    d = client.get("/api/dashboard").json()
    assert d["totals"]["incidents"] >= 8 and d["recent_incidents"]
    body = client.get("/api/settings").text + client.get("/api/servicenow/status").text
    assert "sk-leak-check" not in body and "pw-leak-check" not in body


def test_frontend_served(client):
    assert "SmartDesk AI" in client.get("/").text
