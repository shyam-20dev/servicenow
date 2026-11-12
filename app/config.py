"""Central configuration. Everything comes from environment variables / .env.

Settings are read at call time (not import time) so tests can change them.
Secrets are never logged or returned by the API.
"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# override=False: real environment variables win over the .env file.
load_dotenv(BASE_DIR / ".env", override=False)


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


@dataclass(frozen=True)
class Settings:
    # --- LLM (any OpenAI-compatible Chat Completions API) ---
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout: float
    # --- Embeddings (any OpenAI-compatible Embeddings API) ---
    embedding_base_url: str
    embedding_api_key: str
    embedding_model: str
    embedding_min_score: float
    # --- ServiceNow (optional) ---
    sn_url: str
    sn_username: str
    sn_password: str
    sn_timeout: float
    # --- App ---
    db_path: Path
    kb_dir: Path
    rate_limit_per_minute: int

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def embeddings_configured(self) -> bool:
        return bool(self.embedding_api_key)

    @property
    def servicenow_configured(self) -> bool:
        return bool(self.sn_url and self.sn_username and self.sn_password)


def get_settings() -> Settings:
    llm_base = _env("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    llm_key = _env("LLM_API_KEY")
    return Settings(
        llm_base_url=llm_base,
        llm_api_key=llm_key,
        llm_model=_env("LLM_MODEL", "gpt-4o-mini"),
        llm_timeout=float(_env("LLM_TIMEOUT_SECONDS", "40")),
        # Embeddings default to the same provider/key as the chat model, but can
        # be set separately (e.g. chat with Anthropic-compatible proxy, embed with OpenAI).
        embedding_base_url=(_env("EMBEDDING_BASE_URL") or llm_base).rstrip("/"),
        embedding_api_key=_env("EMBEDDING_API_KEY") or llm_key,
        embedding_model=_env("EMBEDDING_MODEL", "text-embedding-3-small"),
        embedding_min_score=float(_env("EMBEDDING_MIN_SCORE", "0.30")),
        sn_url=_env("SERVICENOW_INSTANCE_URL").rstrip("/"),
        sn_username=_env("SERVICENOW_USERNAME"),
        sn_password=os.environ.get("SERVICENOW_PASSWORD", ""),
        sn_timeout=float(_env("SERVICENOW_TIMEOUT_SECONDS", "20")),
        db_path=Path(_env("SMARTDESK_DB", str(BASE_DIR / "data" / "smartdesk.db"))),
        kb_dir=Path(_env("SMARTDESK_KB_DIR", str(BASE_DIR / "knowledge_base"))),
        rate_limit_per_minute=int(_env("RATE_LIMIT_PER_MINUTE", "60")),
    )
