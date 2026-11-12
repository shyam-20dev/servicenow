# ServiceNow Setup (Optional)

> **SmartDesk AI works fully without ServiceNow.** This guide is only for the optional "Create in ServiceNow" button.
> If you skip it, the button simply reports "ServiceNow is not configured" – nothing is faked.

## 1. Get a free Personal Developer Instance (PDI)

1. Go to **https://developer.servicenow.com** and create/sign in to a free account.
2. Click your profile icon (top right) → **Start building** / **Manage my instance** → **Request instance**.
3. Choose the latest release and wait a few minutes.
4. The **Manage my instance** page shows:
   * **Instance URL** – e.g. `https://dev123456.service-now.com`  ← this is `SERVICENOW_INSTANCE_URL`
   * **User name** – `admin`
   * **Current password** – click the eye icon. Save it in a password manager.
5. Notes:
   * A PDI **hibernates after inactivity** (about 10 days; it may also sleep sooner). If the URL shows a "hibernating" page, open the developer site and wake it up.
   * Instances are reclaimed if unused for a long time. Keep a habit of logging in once a week before your interview.

## 2. Explore (30 minutes – this is what interviewers ask about)

Open the instance, log in as `admin`, and in the left **filter navigator** try:

* `Incident > Create New` – fill Caller, Short description, Category, Impact, Urgency and watch **Priority** compute itself.
* `Incident > All` – a **list** view; open a record to see a **form**.
* `System Definition > Tables` → search `incident` – the **table** behind the form (extends the `task` table).
* `User Administration > Groups` – **assignment groups**.
* `Service Catalog` – where service **requests** (`sc_request`, `sc_req_item`) come from.
* `Flow Designer` – the modern workflow tool.

## 3. Create a dedicated API user (recommended)

Using `admin` works for a quick test, but a dedicated integration user is the correct practice (least privilege).

1. Navigate to **User Administration > Users → New**.
2. Fill: **User ID** `smartdesk.api`, **First name** `SmartDesk`, **Last name** `API`, set a **Password**.
3. Tick **Web service access only** (the account can call APIs but cannot log in to the UI). If your release lacks this box, skip it.
4. Save, then in the **Roles** related list click **Edit** and add **`itil`**.
5. Put the user's ID and password in `.env`.

### Minimum permissions needed

| Action | Needs |
|---|---|
| Connection test (`GET /api/now/table/incident`) | read access on `incident` – role `itil` |
| Create incident (`POST /api/now/table/incident`) | create access on `incident` – role **`itil`** |

`itil` is the standard role of ITIL fulfillers and is what ServiceNow's default incident ACLs expect. Avoid giving `admin`
to an integration account.

## 4. Configure SmartDesk AI

Edit `.env` (never commit it):

```
SERVICENOW_INSTANCE_URL=https://dev123456.service-now.com
SERVICENOW_USERNAME=smartdesk.api
SERVICENOW_PASSWORD=your-password
```

Rules: `https://`, no trailing path, no spaces/quotes. Restart `uvicorn`.

## 5. Test the Table API

### A. From SmartDesk AI
**Settings → Test connection.** Green ✓ appears only if ServiceNow actually answered HTTP 200.

### B. With PowerShell (independent check)

```powershell
$pair  = "smartdesk.api:your-password"
$token = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
Invoke-RestMethod -Uri "https://dev123456.service-now.com/api/now/table/incident?sysparm_limit=1&sysparm_fields=number" `
  -Headers @{ Authorization = "Basic $token"; Accept = "application/json" }
```

You should see `result` with an incident number.

### C. Create an incident from SmartDesk AI
Open an incident → **Create in ServiceNow**. On success you get `Created in ServiceNow as INC00xxxxx`; the local record
stores `sys_id` and number. Verify in ServiceNow: `Incident > All` and search the number.

## 6. What SmartDesk sends

`POST {instance}/api/now/table/incident` with JSON:

```json
{ "short_description": "...", "description": "... (+ SmartDesk reference & AI summary)",
  "urgency": "1", "impact": "2", "category": "network" }
```

ServiceNow calculates its own priority from impact/urgency and assigns its own number. The response `result.sys_id`
(32-char unique id) and `result.number` are stored locally.

## 7. Troubleshooting

| Message in SmartDesk | Meaning / fix |
|---|---|
| "not configured" | One of the three variables is empty, or `uvicorn` was not restarted |
| 401 | Wrong username/password. PDI `admin` password may have been reset – check the developer site |
| 403 | User lacks `itil`/ACL on incident, or "Web service access only" user is blocked by instance policy |
| 404 or HTML "Instance Hibernating" | URL typo, or instance asleep – wake it at developer.servicenow.com |
| "timed out" / "Could not reach" | Network/VPN/proxy blocking, or the instance is waking up (retry in a minute) |
| "must look like https://devXXXXXX.service-now.com" | URL malformed or `http://` used |
| MFA / SSO errors | Basic auth does not work with SSO users; use a local API user as above |

## 8. Core project vs. optional integration

| Works without ServiceNow | Needs ServiceNow |
|---|---|
| Incidents, AI triage, dashboard, assistant/RAG, service requests, knowledge base | "Test connection", "Create in ServiceNow" |

In the interview, say precisely: *"Core app is standalone. The optional integration calls the real Table API; I tested it
against my PDI"* – but only say that if you actually ran it successfully.
