# 5-Minute Demo Script

**Before the interview (10 min):** run `pytest -q`; start the app; open http://127.0.0.1:8000; check the top-bar pill
(LLM or fallback); run **Settings → Test connection** if ServiceNow is configured; open your ServiceNow incident list in
a second tab; keep a browser tab on `/docs` as backup. Run `python scripts\reset_db.py` for a clean, seeded state.

## Script (≈5:00)

### 0:00 – Start & pitch (30 s)
*Start:* `uvicorn app.main:app --reload` (already running).
> "SmartDesk AI is an AI-assisted service desk. Employees raise incidents and requests, an LLM helps triage, and a RAG
> assistant answers questions from our knowledge base. It's built with FastAPI, SQLite and vanilla JS, and can push
> incidents to ServiceNow through its REST API."

### 0:30 – Dashboard (30 s)
Show the **Dashboard**: KPIs, priority chart, categories, requests by department.
> "These counts come straight from SQL GROUP BY queries. The seeded records are labelled *sample data* – they are not AI output."

### 1:00 – Create an incident + AI triage (60 s)
**Incidents → New incident**. Enter:
* Short: `Cannot connect to VPN from home`
* Description: `Since this morning the VPN shows authentication timeout. I have a client deadline today and cannot reach internal apps.`

Leave impact/urgency on *Let AI suggest* → **Create & analyse**. In the detail window point out:
* AI summary, **category = Network**, troubleshooting steps, recommended resolution
* The badge showing the source (*LLM (model)* or *rule-based fallback*) – "I always label what produced it."
* Impact × urgency → **priority**: "The LLM only suggests impact/urgency; the priority comes from a fixed matrix, so it's predictable and auditable."
* Assignment group **Network Support** and technician.
Change status to **In Progress** → Save.

### 2:00 – Knowledge assistant & RAG (75 s)
**AI Assistant** → click *My VPN is not connecting.* Show:
* the answer badge (*RAG + LLM*, or *Fallback: retrieved passage* without a key),
* **Retrieval: semantic** vs *keyword fallback*,
* **Sources** – open one to show the exact excerpt from `vpn_troubleshooting.md`.

Then ask something outside the KB: `What is the capital of France?` →
> "It says the knowledge base doesn't contain the information instead of inventing an answer – and doesn't even call the LLM. That is the point of RAG."

Optionally upload a small TXT (Knowledge Base page) and ask about it to show instant knowledge updates.

### 3:15 – Service request & USM (45 s)
**Service Requests** → Department **HR** → *Employment letter* → submit. Then switch to **Finance** / **Facilities**.
> "Same form, same workflow, same statuses, different fulfilment group. This is the universal service management idea:
> one platform, many departments. It's my prototype of the principle, not an official ServiceNow USM product."
Update the request status to **Approved**.

### 4:00 – ServiceNow integration (45 s)
Open the incident → **Create in ServiceNow**.
* If configured: show the success message with the number, then switch to the ServiceNow tab and search that number – show `short_description`, urgency, impact.
* If not configured: show the clear "not configured – nothing was sent" message.
> "It calls `POST /api/now/table/incident`, reads the `sys_id` and number from the response and stores them. If the call fails, I store the failure and never claim success."

### 4:45 – Wrap-up (15 s)
> "Local demo = my SQLite database and my UI. Live ServiceNow = the real platform with its own workflows, SLAs, ACLs and users.
> My app integrates with it; it doesn't replace it. Next steps: SLA timers, approvals, authentication and a ServiceNow webhook back."

## Local demo vs live ServiceNow (say this clearly)

| Local SmartDesk | Live ServiceNow |
|---|---|
| SQLite, one demo user | Enterprise platform, roles/ACLs, SSO |
| Simple status workflow | Flow Designer, SLAs, approvals, CMDB |
| AI triage + RAG assistant built by me | Now Assist and the Platform's own AI (licensed) |
| Runs offline with fallbacks | Needs an instance (PDI is free for learning) |

## If something goes wrong
* **No LLM / internet:** the fallback badges prove honest degradation – narrate it as a feature.
* **ServiceNow asleep:** show the "Test connection" failure message and your pre-captured screenshot of a created record.
* **UI glitch:** use `/docs` (Swagger) to demonstrate the same API calls.
