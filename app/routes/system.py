from fastapi import APIRouter

from ..config import get_settings
from ..services import dashboard_service

router = APIRouter(prefix="/api", tags=["System"])


@router.get("/dashboard")
def dashboard():
    return dashboard_service.get_dashboard()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/settings")
def settings_summary():
    """Feature status only. Secrets are never returned."""
    s = get_settings()
    return {
        "llm": {"configured": s.llm_configured, "model": s.llm_model if s.llm_configured else None,
                "provider_host": s.llm_base_url.split("//")[-1].split("/")[0]},
        "embeddings": {"configured": s.embeddings_configured,
                       "model": s.embedding_model if s.embeddings_configured else None},
        "retrieval_mode": "semantic" if s.embeddings_configured else "keyword (fallback)",
        "servicenow_configured": s.servicenow_configured,
        "demo_auth": "No real authentication. Demo user 'demo.employee' is assumed. Not production-grade.",
    }
