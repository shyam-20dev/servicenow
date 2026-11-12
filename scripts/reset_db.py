"""Delete the local SQLite database so the app re-creates and re-seeds it on next start.

Usage (from the project folder):   python scripts/reset_db.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import get_settings  # noqa: E402

path = get_settings().db_path
if path.exists():
    path.unlink()
    print(f"Deleted {path}. It will be recreated and re-seeded when you start the app.")
else:
    print("No database file found - nothing to reset.")
