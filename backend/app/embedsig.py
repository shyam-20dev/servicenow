"""Stored embeddings only make sense for the model that made them. Rebuild them if the model changes."""
from . import config, db


def check() -> str | None:
    """Clear all stored embeddings if the embedding model changed. Returns a note when it did."""
    with db.conn() as c:
        row = c.execute("SELECT value FROM app_meta WHERE key='embed_signature'").fetchone()
        old = row["value"] if row else None
        note = None
        if old != config.EMBED_SIGNATURE:
            n1 = c.execute("UPDATE tickets SET embedding=NULL WHERE embedding IS NOT NULL").rowcount
            n2 = c.execute("UPDATE kb_articles SET embedding=NULL WHERE embedding IS NOT NULL").rowcount
            if n1 or n2:
                note = f"Embedding model changed ({old} -> {config.EMBED_SIGNATURE}): cleared {n1} ticket and {n2} article embeddings; they are rebuilt automatically."
            c.execute("INSERT INTO app_meta (key, value) VALUES ('embed_signature', ?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (config.EMBED_SIGNATURE,))
    if note:
        print(note, flush=True)
    return note
