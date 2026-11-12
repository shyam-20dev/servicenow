// pm2 process file for SmartDesk AI.
//   pm2 start ecosystem.config.js      start everything
//   pm2 status | pm2 logs              inspect
//   pm2 restart smartdesk-ai           restart after editing .env
//   pm2 stop all                       stop
//
// Secrets stay in .env (read by the app itself); nothing secret is stored here.
const os = require("os");
const fs = require("fs");
const path = require("path");

const isWin = process.platform === "win32";
const venvPython = isWin
  ? path.join(__dirname, ".venv", "Scripts", "python.exe")
  : path.join(__dirname, ".venv", "bin", "python");

// Ollama: use ~/ollama-local/bin/ollama if present (user-level install), else the one on PATH.
const localOllama = path.join(os.homedir(), "ollama-local", "bin", "ollama");
const ollamaBin = fs.existsSync(localOllama) ? localOllama : "ollama";

module.exports = {
  apps: [
    {
      name: "smartdesk-ollama",          // free local LLM + embeddings server (port 11434)
      script: ollamaBin,
      args: "serve",
      interpreter: "none",
      autorestart: true,
      max_restarts: 10,
    },
    {
      name: "smartdesk-ai",              // FastAPI app + UI (port 8000)
      script: venvPython,
      args: "-m uvicorn app.main:app --host 127.0.0.1 --port 8000",
      interpreter: "none",
      cwd: __dirname,
      autorestart: true,
      max_restarts: 10,
      restart_delay: 2000,
      env: { PYTHONUNBUFFERED: "1" },
    },
  ],
};
