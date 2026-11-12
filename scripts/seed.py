"""Create tables, load sample incidents/requests and index the knowledge base (idempotent).

The app does this automatically on startup; run this script if you want to do it manually:
    python scripts/seed.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.database import init_db  # noqa: E402
from app.seed import seed_if_empty  # noqa: E402
from app.services import rag_service  # noqa: E402

init_db()
seed_if_empty()
print(f"Knowledge documents newly indexed: {rag_service.load_bundled_knowledge_base()}")
print("Done.")
