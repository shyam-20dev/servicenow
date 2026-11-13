const path = require("path");
const fs = require("fs");

// Minimal .env loader so pm2 children get the same settings as the backend.
const env = {};
const envFile = path.join(__dirname, ".env");
if (fs.existsSync(envFile)) {
  for (const line of fs.readFileSync(envFile, "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m) env[m[1]] = m[2].replace(/^(['"])(.*)\1$/, "$2");
  }
}

const isWin = process.platform === "win32";
const venvPython = isWin
  ? path.join(__dirname, "backend", ".venv", "Scripts", "python.exe")
  : path.join(__dirname, "backend", ".venv", "bin", "python");

const backendPort = env.BACKEND_PORT || "8000";
const frontendPort = env.FRONTEND_PORT || "3000";

const useOllama = (env.LLM_PROVIDER || "ollama").toLowerCase() !== "gemini";

module.exports = {
  apps: [
    // Local model server: only needed when LLM_PROVIDER=ollama
    ...(useOllama ? [{
      name: "pl-ollama",
      script: path.join(__dirname, "scripts", "ollama-serve.js"),
      env,
    }] : []),
    {
      name: "pl-backend",
      cwd: path.join(__dirname, "backend"),
      script: venvPython,
      interpreter: "none",
      args: `-m uvicorn app.main:app --host 0.0.0.0 --port ${backendPort}`,
      // no env here: the backend loads ../.env itself, so `pm2 restart pl-backend` picks up .env edits
    },
    {
      name: "pl-frontend",
      cwd: path.join(__dirname, "frontend"),
      script: path.join(__dirname, "frontend", "node_modules", "next", "dist", "bin", "next"),
      args: `start -p ${frontendPort}`,
      env: { ...env, NODE_ENV: "production", BACKEND_PORT: backendPort },
    },
  ],
};
