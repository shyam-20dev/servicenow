import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

SN_MODE = os.getenv("SN_MODE", "mock").lower()  # "mock" (simulated) or "live"
SN_INSTANCE = os.getenv("SN_INSTANCE", "").rstrip("/")
SN_USER = os.getenv("SN_USER", "")
SN_PASSWORD = os.getenv("SN_PASSWORD", "")
SN_CLOSE_CODE = os.getenv("SN_CLOSE_CODE", "").strip()   # optional: resolution code used when resolving incidents

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").strip().lower()  # "ollama" (local) or "gemini" (API)
if LLM_PROVIDER not in ("ollama", "gemini"):
    raise ValueError(f"LLM_PROVIDER must be 'ollama' or 'gemini', got '{LLM_PROVIDER}'")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
GEMINI_EMBED_DIMS = int(os.getenv("GEMINI_EMBED_DIMS", "768"))
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

DB_PATH = Path(os.getenv("DB_PATH", str(ROOT / "problemlens.db")))

# Embedding models differ in how similar "related" texts score, so these are tunable.
KB_MIN_SCORE = float(os.getenv("KB_MIN_SCORE", "0.60" if LLM_PROVIDER == "gemini" else "0.58"))
KB_REL_MARGIN = float(os.getenv("KB_REL_MARGIN", "0.15"))
CLUSTER_THRESHOLD = float(os.getenv("CLUSTER_THRESHOLD", "0.85" if LLM_PROVIDER == "gemini" else "0.70"))

# Identifies the embedding space; stored vectors are rebuilt when this changes.
EMBED_SIGNATURE = (f"gemini:{GEMINI_EMBED_MODEL}:{GEMINI_EMBED_DIMS}" if LLM_PROVIDER == "gemini"
                   else f"ollama:{OLLAMA_EMBED_MODEL}")
