# SmartDesk AI – Intelligent IT Service Management & Knowledge Assistant

An AI-assisted IT helpdesk built as a portfolio project for an **HCLTech – USM & Generative AI** role.
It demonstrates ITSM concepts, a service-request workflow reused across departments (the USM idea), a real
**Retrieval-Augmented Generation (RAG)** knowledge assistant, optional **ServiceNow Table API** integration and a
professional web dashboard.

> **Honesty notes (important for your interview)**
> * It is a demo, **not** an official ServiceNow USM product. It demonstrates universal-service-management *principles*.
> * With no LLM key the app still runs, but uses a **clearly labelled rule-based fallback** – never presented as AI.
> * The ServiceNow button only reports success if ServiceNow really answered with a `sys_id`. Nothing is simulated.
> * Authentication is a fixed demo user. Not production-grade security.

## Features

| Area | What it does |
|---|---|
| Incident management | Create incident → AI summary, category, impact/urgency suggestion, troubleshooting steps, recommended resolution; priority from an impact × urgency matrix; status workflow New → In Progress → Resolved → Closed; search + filters; assignment group/technician |
| AI Knowledge Assistant | Chat with RAG over local IT articles; shows sources + excerpts; labels answer mode (RAG+LLM / fallback / no knowledge) and retrieval mode (semantic / keyword) |
| RAG | Chunking → embeddings (any OpenAI-compatible provider) → SQLite vector store → cosine similarity → grounded answer. Admits when the KB lacks the answer. TXT/MD/PDF upload |
| Service requests (USM) | IT, HR, Finance, Facilities share one catalog/workflow (Submitted → Approved → In Progress → Fulfilled) |
| Dashboard | KPIs, priority/category/status/department charts, recent incidents |
| ServiceNow (optional) | Push an incident to a real instance via `POST /api/now/table/incident`; stores returned `sys_id` and number |
| Safety | `.env` secrets, Pydantic validation, rate limit, body-size limit, safe error messages, no secrets in responses |

## Tech stack

Python · FastAPI · Pydantic · SQLite (`sqlite3`) · Uvicorn · httpx · HTML/CSS/vanilla JavaScript (Fetch API) · pytest.
No ChromaDB/FAISS (they cause Windows build problems and are overkill for a small KB) – vectors are stored in SQLite
and compared with a small cosine-similarity function you can explain line by line.

## Prerequisites (Windows 11)

* Python 3.10 – 3.14 (check: `python --version`). Install from python.org and tick **"Add python.exe to PATH"**.
* VS Code (optional) and a modern browser.
* Optional: an LLM API key and a free ServiceNow Personal Developer Instance.

## Setup – Windows PowerShell

```powershell
cd path\to\SmartDesk-AI

# 1. Create and activate a virtual environment
python -m venv .venv
# If activation is blocked, run this once for the current window only:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 3. Create your config file
Copy-Item .env.example .env
notepad .env          # fill in keys if you have them (all optional)

# 4. Start the app (tables + sample data + knowledge base are created automatically)
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000** (the UI is served by FastAPI itself, so there is no CORS setup).
Swagger API docs: **http://127.0.0.1:8000/docs**.

### Run the tests

```powershell
pytest -q
```

### Reset the demo data

```powershell
python scripts\reset_db.py     # deletes data\smartdesk.db; it is re-created on the next start
```

## Running without an LLM key

Leave `LLM_API_KEY` empty. Then:
* new incidents are triaged by **keyword rules** (badge: *rule-based fallback*),
* the assistant uses **keyword (TF-IDF) retrieval** and returns the **retrieved passage** (badge: *Fallback: retrieved passage, no LLM*),
* everything else (dashboard, requests, tickets) works normally.

## Configuring an LLM provider

Edit `.env`. Any OpenAI-compatible Chat Completions API works:

| Provider | `LLM_BASE_URL` | `LLM_MODEL` example |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Groq (free tier) | `https://api.groq.com/openai/v1` | `llama-3.1-8b-instant` |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.0-flash` |
| OpenRouter | `https://openrouter.ai/api/v1` | any listed model |
| Ollama (local, offline) | `http://localhost:11434/v1` (key can be any text, e.g. `ollama`) | `llama3.2` |

Restart `uvicorn` after editing `.env`. The pill in the top bar and **Settings** page show the active mode.

## Configuring embeddings / RAG

Semantic search needs an **embeddings** endpoint. By default it reuses `LLM_BASE_URL` + `LLM_API_KEY`.
If your chat provider has no embeddings (e.g. Groq), set `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL`
separately (OpenAI `text-embedding-3-small`, Gemini `text-embedding-004`, Ollama `nomic-embed-text`).

After adding an embedding key, open **Knowledge Base → Re-index embeddings** (or `POST /api/knowledge/reindex`).
Documents then show a green *embedded* badge and answers show *Retrieval: semantic (embeddings)*.
If answers say "knowledge base does not contain…" too often for a model, lower `EMBEDDING_MIN_SCORE`
(e.g. `0.25`); if irrelevant chunks appear, raise it.

## Connecting ServiceNow (optional)

See **[SERVICENOW_SETUP.md](SERVICENOW_SETUP.md)** for the beginner walkthrough. In short, set
`SERVICENOW_INSTANCE_URL`, `SERVICENOW_USERNAME`, `SERVICENOW_PASSWORD` in `.env`, restart, then use
**Settings → Test connection** and **Incident → Create in ServiceNow**.

## Testing the API

Use Swagger at `/docs`, or PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/dashboard

$body = @{ short_description = "VPN keeps disconnecting"; description = "VPN drops every 5 minutes since morning." } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/incidents -ContentType "application/json" -Body $body

$q = @{ message = "My VPN is not connecting." } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/assistant/chat -ContentType "application/json" -Body $q
```

| Endpoint | Purpose |
|---|---|
| `GET /api/dashboard` | KPIs and chart data |
| `GET/POST /api/incidents`, `GET/PATCH /api/incidents/{id}` | Incident CRUD (filters: `status`, `category`, `priority`, `q`) |
| `POST /api/assistant/chat`, `GET /api/assistant/history` | RAG assistant |
| `GET /api/knowledge`, `POST /api/knowledge/upload`, `POST /api/knowledge/reindex`, `GET /api/knowledge/search?q=` | Knowledge base |
| `GET /api/requests/catalog`, `GET/POST /api/requests`, `PATCH /api/requests/{id}` | Service requests |
| `GET /api/servicenow/status`, `POST /api/servicenow/test`, `POST /api/servicenow/incidents` | Optional ServiceNow |
| `GET /api/settings`, `GET /api/health` | Status (never returns secrets) |

## Project layout

```
SmartDesk-AI/
  app/
    main.py            FastAPI app, middleware, static frontend
    config.py          settings from environment / .env
    database.py        SQLite schema + connection helper
    schemas.py         Pydantic validation (inputs and LLM output)
    seed.py            sample incidents/requests
    routes/            HTTP endpoints (thin)
    services/          llm_service, rag_service, incident_service,
                       servicenow_service, request_service, dashboard_service
    utils/ratelimit.py rate limiter
  frontend/            index.html, css/styles.css, js/app.js
  knowledge_base/      7 IT articles (Markdown)
  scripts/             seed.py, reset_db.py
  tests/               pytest suite
  *.md                 README, ARCHITECTURE, INTERVIEW_GUIDE, DEMO_SCRIPT, SERVICENOW_SETUP
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `python` not recognised | Reinstall Python with "Add to PATH", or use `py -m venv .venv` |
| `Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| `ModuleNotFoundError: No module named 'app'` | Run commands from the `SmartDesk-AI` folder (the one containing `app\`) |
| `Address already in use` | `uvicorn app.main:app --port 8001` |
| Top bar says *Server offline* | The backend is not running, or you opened `index.html` directly. Use http://127.0.0.1:8000 |
| LLM error "rejected the API key (401)" | Wrong key/provider URL. Check `LLM_BASE_URL` matches the key's provider |
| LLM error "(429)" | Quota / rate limit. App falls back automatically; try later or another provider |
| Assistant always says "knowledge base does not contain…" | Lower `EMBEDDING_MIN_SCORE`; or check Settings shows embeddings configured and re-index |
| `.env` changes ignored | Restart `uvicorn` (`--reload` watches code, not always `.env`) |
| ServiceNow 401 / 403 / 404 | See SERVICENOW_SETUP.md → Troubleshooting |
| PDF upload says unreadable | Scanned-image PDFs have no text; use a text PDF or TXT/MD |

## Further reading

* [ARCHITECTURE.md](ARCHITECTURE.md) – how it works internally (with diagrams)
* [INTERVIEW_GUIDE.md](INTERVIEW_GUIDE.md) – concepts and 35+ Q&A
* [DEMO_SCRIPT.md](DEMO_SCRIPT.md) – 5-minute demo
* [SERVICENOW_SETUP.md](SERVICENOW_SETUP.md) – ServiceNow PDI + API setup
