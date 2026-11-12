#!/usr/bin/env bash
# SmartDesk AI - one-step setup for Linux, macOS and Windows (Git Bash / WSL).
#
#   bash setup.sh              create .venv, install dependencies, create .env
#   bash setup.sh --models     ...and also download the free Ollama models (if Ollama is installed)
#   source setup.sh            same, and leaves the virtual environment ACTIVATED in your shell
#
# A normal "bash setup.sh" cannot activate the venv in YOUR shell (a script runs in a child
# process). Use "source setup.sh" or run the activate command printed at the end.

_sd_main() {
  local DIR PY VENV_PY ACTIVATE WITH_MODELS=0 arg
  DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || return 1
  cd "$DIR" || return 1
  for arg in "$@"; do [ "$arg" = "--models" ] && WITH_MODELS=1; done

  # 1. Find Python 3.10+
  PY=""
  for cand in python3 python py; do
    if command -v "$cand" >/dev/null 2>&1; then
      local args=""; [ "$cand" = "py" ] && args="-3"
      if $cand $args -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' >/dev/null 2>&1; then
        PY="$cand $args"; break
      fi
    fi
  done
  if [ -z "$PY" ]; then
    echo "ERROR: Python 3.10+ not found. Install it from https://www.python.org (tick 'Add to PATH' on Windows)." >&2
    return 1
  fi
  echo "==> Using Python: $($PY --version 2>&1)"

  # 2. Create the virtual environment
  if [ ! -d .venv ]; then
    echo "==> Creating virtual environment (.venv)"
    $PY -m venv .venv || { echo "ERROR: venv creation failed (on Debian/Ubuntu: sudo apt install python3-venv)." >&2; return 1; }
  else
    echo "==> Reusing existing .venv"
  fi

  # Windows (Git Bash) puts the interpreter in Scripts/, Linux/macOS in bin/
  if [ -f .venv/Scripts/python.exe ]; then
    VENV_PY=".venv/Scripts/python.exe"; ACTIVATE=".venv/Scripts/activate"
  else
    VENV_PY=".venv/bin/python"; ACTIVATE=".venv/bin/activate"
  fi

  # 3. Install dependencies using the venv's own python (no activation needed)
  echo "==> Installing dependencies"
  "$VENV_PY" -m pip install --quiet --upgrade pip || return 1
  "$VENV_PY" -m pip install --quiet -r requirements.txt || { echo "ERROR: dependency install failed." >&2; return 1; }

  # 4. Create .env from the template (never overwrite an existing one)
  if [ ! -f .env ]; then
    cp .env.example .env
    echo "==> Created .env from .env.example (edit it to add your keys / ServiceNow details)"
  else
    echo "==> .env already exists - left untouched"
  fi

  # 5. Optional: free local AI models
  if command -v ollama >/dev/null 2>&1 || [ -x "$HOME/ollama-local/bin/ollama" ]; then
    local OLLAMA; OLLAMA="$(command -v ollama || echo "$HOME/ollama-local/bin/ollama")"
    if [ "$WITH_MODELS" = "1" ]; then
      echo "==> Downloading Ollama models (about 2.3 GB)"
      "$OLLAMA" pull nomic-embed-text && "$OLLAMA" pull llama3.2
    else
      echo "==> Ollama found. Run 'bash setup.sh --models' to download llama3.2 + nomic-embed-text."
    fi
  else
    echo "==> Ollama not installed (optional free local LLM): https://ollama.com/download"
  fi

  # 6. Verify
  "$VENV_PY" -c "import fastapi, uvicorn, httpx, pydantic; print('==> Dependencies OK')" || return 1

  cat <<EOF

Setup complete.

Activate the virtual environment:
  Linux/macOS/WSL:   source $ACTIVATE
  Git Bash:          source $ACTIVATE
  PowerShell:        .\\.venv\\Scripts\\Activate.ps1
  cmd.exe:           .venv\\Scripts\\activate.bat

Then:
  uvicorn app.main:app --reload       # UI at http://127.0.0.1:8000
  pytest -q                           # run the tests
  pm2 start ecosystem.config.js       # optional: run in the background with pm2
EOF

  # If the script was sourced, activate for the caller
  if [ "${BASH_SOURCE[0]}" != "$0" ]; then
    # shellcheck disable=SC1090
    . "$ACTIVATE" && echo "==> Virtual environment activated in this shell."
  fi
}

_sd_main "$@"
_sd_rc=$?
unset -f _sd_main
if [ "${BASH_SOURCE[0]}" != "$0" ]; then return $_sd_rc; else exit $_sd_rc; fi
