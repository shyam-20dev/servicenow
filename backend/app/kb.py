"""Knowledge base + simple RAG: embed articles, retrieve by cosine similarity, answer from sources."""
import json

import numpy as np

from . import db, llm
from .kb_seed import ARTICLES

MIN_SCORE = 0.58   # below this an article is treated as not relevant
REL_MARGIN = 0.15  # also drop articles scoring this far below the best match
TOP_K = 3


def article_dict(r) -> dict:
    d = dict(r)
    d["has_embedding"] = bool(d.pop("embedding", None))
    return d


async def add_article(title: str, category: str, body: str) -> dict:
    vec = (await llm.embed([f"{title}. {body}"]))[0]
    with db.conn() as c:
        cur = c.execute("INSERT INTO kb_articles (title, category, body, embedding) VALUES (?,?,?,?)",
                        (title, category, body, json.dumps(vec)))
        row = c.execute("SELECT * FROM kb_articles WHERE id=?", (cur.lastrowid,)).fetchone()
    return article_dict(row)


async def seed() -> dict:
    with db.conn() as c:
        have = {r["title"] for r in c.execute("SELECT title FROM kb_articles")}
    todo = [a for a in ARTICLES if a[0] not in have]
    if todo:
        vecs = await llm.embed([f"{t}. {b}" for t, _, b in todo])
        with db.conn() as c:
            c.executemany("INSERT INTO kb_articles (title, category, body, embedding) VALUES (?,?,?,?)",
                          [(t, cat, b, json.dumps(v)) for (t, cat, b), v in zip(todo, vecs)])
    return {"added": len(todo), "total": len(have) + len(todo)}


async def retrieve(query: str, k: int = TOP_K, min_score: float = MIN_SCORE) -> list[dict]:
    """Top-k articles for a query with cosine score >= min_score."""
    with db.conn() as c:
        rows = c.execute("SELECT * FROM kb_articles WHERE embedding IS NOT NULL").fetchall()
    if not rows:
        return []
    q = np.array((await llm.embed([query]))[0], dtype=np.float32)
    q /= np.linalg.norm(q) or 1.0
    scored = []
    for r in rows:
        v = np.array(json.loads(r["embedding"]), dtype=np.float32)
        v /= np.linalg.norm(v) or 1.0
        scored.append((float(q @ v), r))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[0][0]
    return [{"id": r["id"], "title": r["title"], "category": r["category"], "body": r["body"],
             "score": round(s, 3)} for s, r in scored[:k] if s >= min_score and s >= top - REL_MARGIN]


async def ask(question: str) -> dict:
    hits = await retrieve(question)
    if not hits:
        return {"answer": "No relevant knowledge base article was found for this question.",
                "sources": [], "used_llm": False}
    text = await llm.answer(question, hits)
    return {"answer": text, "used_llm": True,
            "sources": [{k: h[k] for k in ("id", "title", "category", "score")} for h in hits]}
