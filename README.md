# ProblemLens

AI-assisted IT service desk. FastAPI backend, Next.js frontend, local Ollama LLM, ServiceNow as the system of record. All processes run under pm2.

## Setup (new machine)

- Linux / macOS: `./setup.sh`
- Windows: install Git for Windows, then run `./setup.sh` in Git Bash (or `./setup.ps1` in PowerShell).

Then edit `.env` and set `SN_PASSWORD`, and run `pm2 restart all`.

Requires Node 18+ and Python 3.10+. The script installs pm2 and Ollama, creates the venv, builds the frontend, pulls the models and starts everything.

## URLs

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs
- Health (API, Ollama, ServiceNow): http://localhost:8000/api/health

## Layout

- `backend/` FastAPI app (tickets, AI triage, ServiceNow client)
- `frontend/` Next.js UI (proxies `/api/*` to the backend)
- `ecosystem.config.js` pm2 processes: `pl-ollama`, `pl-backend`, `pl-frontend`
- `scripts/ollama-serve.js` starts Ollama only if one isn't already running

## Choosing the LLM

Set `LLM_PROVIDER` in `.env`:

- `ollama` (default): a local model. `setup.sh` installs Ollama and pulls `OLLAMA_MODEL` and `OLLAMA_EMBED_MODEL`. Nothing leaves your machine.
- `gemini`: the Gemini API. Set `GEMINI_API_KEY` (and optionally `GEMINI_MODEL`, `GEMINI_EMBED_MODEL`). Ollama is not installed or started. Ticket text is sent to Google, after basic masking of emails, phone numbers and IPs.

After changing it run `pm2 restart all --update-env`. Embeddings from different models are not comparable, so when the embedding model changes the stored ticket and article embeddings are cleared and rebuilt automatically. `KB_MIN_SCORE`, `KB_REL_MARGIN` and `CLUSTER_THRESHOLD` can be tuned per model. Defaults were measured on the demo data: Ollama 0.58 / 0.15 / 0.70, Gemini 0.60 / 0.15 / 0.85.

Gemini notes: the free tier allows 100 embedding requests per minute (each text counts), and Google sometimes overloads its larger models, so a `-flash-lite` model is the default. Temporary 429/503 errors are retried automatically. Check which models your key can use with `curl -H "x-goog-api-key: $GEMINI_API_KEY" https://generativelanguage.googleapis.com/v1beta/models`.

## Knowledge base (RAG)

`/knowledge` holds IT articles, each embedded once with `nomic-embed-text`. A question retrieves the closest articles by cosine similarity (minimum score 0.58, within 0.15 of the best match) and the local LLM answers using only those, citing sources. If nothing is relevant the LLM is not called. The same retrieval grounds the AI ticket analysis, and the sources are shown on the ticket. Use "Load sample articles" to add 14 demo articles. Files (.txt, .md, .pdf, .docx, up to 5 MB) can be uploaded too: the text is extracted, split into passages of about 800 characters and each passage is embedded, so answers cite the right part of the file. Scanned PDFs are not supported (no OCR).

## Pages

- `/` Dashboard: ticket counts and status, tickets needing human review, AI override rate, average AI time, charts, detected Problems, knowledge base summary, demo data tools
- `/report` Report an Issue: describe the problem, watch AI analysis and incident creation, follow the ticket status
- `/tickets` Ticket Evaluation: every ticket raised by everyone with its status. Tickets that need a human (high priority, AI unsure, no grounding, part of an incident spike) are listed separately; a person approves or corrects the AI and updates the status
- `/knowledge` Knowledge Base: upload files (.txt, .md, .pdf, .docx) and manage written articles
- `/assistant` AI Assistant: chat that answers only from the knowledge base (query rewriting for follow-ups, vector retrieval, per-file cap, cited sources, no-answer guard)
- `/evaluation` AI accuracy against labelled demo tickets (linked from the Dashboard)

## ServiceNow mode

`SN_MODE=mock` (default) simulates incident creation locally and is labelled "simulated" in the UI. Set `SN_MODE=live` plus `SN_INSTANCE`, `SN_USER`, `SN_PASSWORD` to create real incidents through the ServiceNow Table API, then `pm2 restart pl-backend`.

### Where data lives (live mode)

ServiceNow is the system of record: tickets are `incident` records and detected Problems are `problem` records. The AI analysis, review status, overrides and requester are stored in custom `u_pl_*` columns that the app creates on first start (ServiceNow may prefix them with the app scope, e.g. `x_..._u_pl_*`; the app looks the names up). SQLite (`problemlens.db`) is only a local cache for fast dashboards and clustering. Local changes are pushed in the background within about 5 seconds, ServiceNow-side changes (e.g. an incident resolved there) are pulled every minute, and if the local database is deleted it is rebuilt from ServiceNow at startup. Demo (synthetic) data is never sent to ServiceNow. `GET /api/sync` shows pending rows and errors, and `POST /api/sync/now` forces a push and pull. In `SN_MODE=mock` nothing is sent and SQLite is the only store. The knowledge base stays in SQLite.
