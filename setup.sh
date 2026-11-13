#!/usr/bin/env bash
# ProblemLens setup: Linux, macOS, and Windows (run from Git Bash).
# Usage: ./setup.sh
set -euo pipefail
cd "$(dirname "$0")"

log()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

case "$(uname -s)" in
  Linux*)               OS=linux ;;
  Darwin*)              OS=mac ;;
  MINGW*|MSYS*|CYGWIN*) OS=windows ;;
  *) die "Unsupported OS: $(uname -s)" ;;
esac
log "Detected OS: $OS"

# ---------- Node.js ----------
have node || die "Node.js 18+ is required. Install from https://nodejs.org and re-run."
NODE_MAJOR=$(node -p 'process.versions.node.split(".")[0]')
[ "$NODE_MAJOR" -ge 18 ] || die "Node.js 18+ required (found $(node -v))."

# ---------- Python ----------
PY=""
for c in python3 python py; do
  if have "$c" && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then PY="$c"; break; fi
done
[ -n "$PY" ] || die "Python 3.10+ is required. Install it (Windows: python.org, tick 'Add to PATH') and re-run."
log "Using Python: $($PY --version)"

# ---------- pm2 ----------
if ! have pm2; then
  log "Installing pm2"
  npm install -g pm2 || die "Could not install pm2 globally. Try with sudo (Linux) or an admin shell (Windows)."
fi

# ---------- Ollama ----------
if ! have ollama; then
  log "Installing Ollama"
  case "$OS" in
    linux)   curl -fsSL https://ollama.com/install.sh | sh ;;
    mac)     if have brew; then brew install ollama; else die "Install Ollama from https://ollama.com/download and re-run."; fi ;;
    windows)
      if have winget; then
        winget install -e --id Ollama.Ollama --accept-package-agreements --accept-source-agreements || true
        export PATH="$PATH:/c/Users/$USERNAME/AppData/Local/Programs/Ollama"
      fi
      have ollama || die "Install Ollama from https://ollama.com/download, open a NEW Git Bash, and re-run."
      ;;
  esac
fi

# ---------- .env ----------
if [ ! -f .env ]; then
  cp .env.example .env
  warn "Created .env. Edit it and set SN_PASSWORD (your ServiceNow admin password)."
fi
# shellcheck disable=SC1091
set -a; . ./.env; set +a

# ---------- Backend ----------
log "Setting up backend (Python venv)"
[ -d backend/.venv ] || "$PY" -m venv backend/.venv
if [ "$OS" = windows ]; then VENV_PY="backend/.venv/Scripts/python.exe"; else VENV_PY="backend/.venv/bin/python"; fi
"$VENV_PY" -m pip install --upgrade pip
"$VENV_PY" -m pip install -r backend/requirements.txt

# ---------- Frontend ----------
log "Setting up frontend (Next.js)"
(cd frontend && npm install && BACKEND_PORT="${BACKEND_PORT:-8000}" npm run build)

# ---------- Start Ollama (via the pm2 wrapper) and pull models ----------
mkdir -p logs
pm2 delete pl-ollama >/dev/null 2>&1 || true
pm2 start ecosystem.config.js --only pl-ollama
log "Waiting for Ollama"
HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
for _ in $(seq 1 30); do curl -fs "$HOST/api/tags" >/dev/null 2>&1 && break; sleep 1; done
curl -fs "$HOST/api/tags" >/dev/null 2>&1 || die "Ollama did not start. Run 'ollama serve' to see why."

log "Pulling models (first time can take a few minutes)"
ollama pull "${OLLAMA_MODEL:-llama3.2:3b}"
ollama pull "${OLLAMA_EMBED_MODEL:-nomic-embed-text}"

# ---------- Start everything ----------
log "Starting all services with pm2"
pm2 start ecosystem.config.js
pm2 save

echo
log "Done"
echo "  Frontend : http://localhost:${FRONTEND_PORT:-3000}"
echo "  API docs : http://localhost:${BACKEND_PORT:-8000}/docs"
echo "  Health   : http://localhost:${BACKEND_PORT:-8000}/api/health"
echo
echo "  pm2 status | pm2 logs | pm2 restart all | pm2 stop all"
case "$OS" in
  linux|mac) echo "  Start on boot: run 'pm2 startup' and execute the command it prints, then 'pm2 save'." ;;
  windows)   echo "  Start on boot (Windows): npm i -g pm2-windows-startup && pm2-startup install" ;;
esac
