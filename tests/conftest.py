"""Test setup: every test gets a fresh temporary database and NO external credentials."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

SECRET_VARS = ["LLM_API_KEY", "EMBEDDING_API_KEY", "SERVICENOW_INSTANCE_URL",
               "SERVICENOW_USERNAME", "SERVICENOW_PASSWORD"]


@pytest.fixture(autouse=True)
def clean_env(tmp_path, monkeypatch):
    for v in SECRET_VARS:
        monkeypatch.setenv(v, "")
    monkeypatch.setenv("SMARTDESK_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1000")


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:   # runs startup: create tables, seed, index knowledge base
        yield c
