// Keeps Ollama running under pm2 without clashing with an already-running
// instance (e.g. the systemd service on Linux or the Windows tray app).
const http = require("http");
const { spawn } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

// Find the ollama binary: OLLAMA_BIN, then common install locations, then PATH.
function findOllama() {
  const exe = process.platform === "win32" ? "ollama.exe" : "ollama";
  const candidates = [
    process.env.OLLAMA_BIN,
    path.join(os.homedir(), "ollama-local", "bin", exe),
    path.join(process.env.LOCALAPPDATA || "", "Programs", "Ollama", exe),
    "/usr/local/bin/ollama",
    "/usr/bin/ollama",
    "/opt/homebrew/bin/ollama",
  ].filter(Boolean);
  return candidates.find((c) => fs.existsSync(c)) || "ollama";
}

const host = process.env.OLLAMA_HOST || "http://127.0.0.1:11434";
const url = new URL(host);

function isUp() {
  return new Promise((resolve) => {
    const req = http.get({ hostname: url.hostname, port: url.port || 11434, path: "/api/tags", timeout: 2000 }, (res) => {
      res.resume();
      resolve(true);
    });
    req.on("error", () => resolve(false));
    req.on("timeout", () => { req.destroy(); resolve(false); });
  });
}

(async () => {
  if (await isUp()) {
    console.log("Ollama already running; watching it.");
    setInterval(() => {}, 1 << 30);
    return;
  }
  const child = spawn(findOllama(), ["serve"], { stdio: "inherit" });
  child.on("exit", (code) => process.exit(code ?? 1));
})();
