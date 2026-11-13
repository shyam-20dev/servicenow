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

## Knowledge base (RAG)

`/knowledge` holds IT articles, each embedded once with `nomic-embed-text`. A question retrieves the closest articles by cosine similarity (minimum score 0.58, within 0.15 of the best match) and the local LLM answers using only those, citing sources. If nothing is relevant the LLM is not called. The same retrieval grounds the AI ticket analysis, and the sources are shown on the ticket. Use "Load sample articles" to add 14 demo articles.

## Pages

- `/` tickets, AI triage, Problem detection
- `/knowledge` knowledge base and Q&A
- `/evaluation` AI accuracy against labelled synthetic tickets

## ServiceNow mode

`SN_MODE=mock` (default) simulates incident creation locally and is labelled "simulated" in the UI. Set `SN_MODE=live` plus `SN_INSTANCE`, `SN_USER`, `SN_PASSWORD` to create real incidents through the ServiceNow Table API, then `pm2 restart pl-backend`.
