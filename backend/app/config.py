import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT.parent / ".env")

SN_MODE = os.getenv("SN_MODE", "mock").lower()  # "mock" (simulated) or "live"
SN_INSTANCE = os.getenv("SN_INSTANCE", "").rstrip("/")
SN_USER = os.getenv("SN_USER", "")
SN_PASSWORD = os.getenv("SN_PASSWORD", "")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

DB_PATH = ROOT / "problemlens.db"
