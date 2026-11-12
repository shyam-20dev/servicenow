"""SmartDesk AI - FastAPI application entry point.

Run:  uvicorn app.main:app --reload
UI:   http://127.0.0.1:8000        API docs: http://127.0.0.1:8000/docs
"""
import logging
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR, get_settings
from .database import init_db
from .routes import assistant, incidents, knowledge, requests, servicenow, system
from .seed import seed_if_empty
from .services import rag_service
from .utils.ratelimit import MAX_BODY_BYTES, RateLimiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("smartdesk")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_if_empty()
    added = rag_service.load_bundled_knowledge_base()
    s = get_settings()
    log.info("SmartDesk AI started. LLM configured: %s | embeddings configured: %s | ServiceNow configured: %s | "
             "new KB docs indexed: %d", s.llm_configured, s.embeddings_configured, s.servicenow_configured, added)
    yield


app = FastAPI(
    title="SmartDesk AI",
    description="AI-assisted IT service management demo: incidents, service requests, RAG knowledge assistant "
                "and optional ServiceNow integration. Demo project - no production-grade authentication.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
                   allow_methods=["*"], allow_headers=["*"])

_limiter = RateLimiter(get_settings().rate_limit_per_minute)


@app.middleware("http")
async def guard(request: Request, call_next):
    if request.url.path.startswith("/api"):
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
            return JSONResponse({"detail": "Request body too large (max 3 MB)."}, status_code=413)
        if request.method in ("POST", "PATCH") and not _limiter.allow(request.client.host if request.client else "?"):
            return JSONResponse({"detail": "Too many requests. Please slow down."}, status_code=429)
    return await call_next(request)


@app.exception_handler(sqlite3.Error)
async def db_error_handler(request: Request, exc: sqlite3.Error):
    log.error("Database error on %s: %s", request.url.path, type(exc).__name__)
    return JSONResponse({"detail": "A database error occurred. Please try again."}, status_code=500)


for module in (system, incidents, requests, assistant, knowledge, servicenow):
    app.include_router(module.router)

FRONTEND_DIR = Path(BASE_DIR) / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
