"""Knowledge base + simple RAG: embed articles, retrieve by cosine similarity, answer from sources."""
import io
import json
import re

import numpy as np

from . import config, db, llm
from .kb_seed import ARTICLES

TOP_K = 3


def article_dict(r) -> dict:
    d = dict(r)
    d["has_embedding"] = bool(d.pop("embedding", None))
    return d


async def add_article(title: str, category: str, body: str) -> dict:
    vec = (await llm.embed([f"{title}. {body}"], "document"))[0]
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
        vecs = await llm.embed([f"{t}. {b}" for t, _, b in todo], "document")
        with db.conn() as c:
            c.executemany("INSERT INTO kb_articles (title, category, body, embedding) VALUES (?,?,?,?)",
                          [(t, cat, b, json.dumps(v)) for (t, cat, b), v in zip(todo, vecs)])
    return {"added": len(todo), "total": len(have) + len(todo)}


async def reembed_missing() -> int:
    """Re-embed articles whose vectors were cleared (e.g. after switching the embedding model)."""
    with db.conn() as c:
        rows = c.execute("SELECT id, title, body FROM kb_articles WHERE embedding IS NULL").fetchall()
    if not rows:
        return 0
    vecs = await llm.embed([f"{r['title']}. {r['body']}" for r in rows], "document")
    with db.conn() as c:
        c.executemany("UPDATE kb_articles SET embedding=? WHERE id=?", [(json.dumps(v), r["id"]) for v, r in zip(vecs, rows)])
    return len(rows)


async def retrieve(query: str, k: int = TOP_K, min_score: float | None = None) -> list[dict]:
    """Top-k articles for a query with cosine score >= min_score."""
    min_score = config.KB_MIN_SCORE if min_score is None else min_score
    await reembed_missing()
    with db.conn() as c:
        rows = c.execute("SELECT * FROM kb_articles WHERE embedding IS NOT NULL").fetchall()
    if not rows:
        return []
    q = np.array((await llm.embed([query], "query"))[0], dtype=np.float32)
    q /= np.linalg.norm(q) or 1.0
    scored = []
    for r in rows:
        v = np.array(json.loads(r["embedding"]), dtype=np.float32)
        v /= np.linalg.norm(v) or 1.0
        scored.append((float(q @ v), r))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[0][0]
    return [{"id": r["id"], "title": r["title"], "category": r["category"], "body": r["body"],
             "score": round(s, 3)} for s, r in scored[:k] if s >= min_score and s >= top - config.KB_REL_MARGIN]


async def ask(question: str) -> dict:
    hits = await retrieve(question)
    if not hits:
        return {"answer": "No relevant knowledge base article was found for this question.",
                "sources": [], "used_llm": False}
    text = await llm.answer(question, hits)
    return {"answer": text, "used_llm": True,
            "sources": [{k: h[k] for k in ("id", "title", "category", "score")} for h in hits]}


# ---------- File upload ----------
ALLOWED = {".txt", ".md", ".pdf", ".docx"}
MAX_BYTES = 5 * 1024 * 1024
CHUNK_CHARS = 800
MAX_CHUNKS = 200


def extract_text(filename: str, data: bytes) -> str:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED:
        raise ValueError(f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED))}")
    if ext in (".txt", ".md"):
        return data.decode("utf-8", errors="replace")
    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    from docx import Document
    doc = Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n\n".join(parts)


def chunk_text(text: str, size: int = CHUNK_CHARS) -> list[str]:
    """Split on paragraphs, packing them up to ~size characters; hard-split oversized paragraphs."""
    text = re.sub(r"[ \t]+", " ", text.replace("\r", ""))
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    pieces = []
    for p in paras:
        while len(p) > size:                      # very long paragraph: cut at a sentence/space near the limit
            cut = max(p.rfind(". ", 0, size), p.rfind(" ", 0, size))
            cut = cut + 1 if cut > size // 2 else size
            pieces.append(p[:cut].strip())
            p = p[cut:].strip()
        if p:
            pieces.append(p)
    chunks, cur = [], ""
    for piece in pieces:
        if cur and len(cur) + len(piece) + 2 > size:
            chunks.append(cur)
            cur = piece
        else:
            cur = f"{cur}\n\n{piece}" if cur else piece
    if cur:
        chunks.append(cur)
    return chunks


async def add_file(filename: str, data: bytes, category: str) -> dict:
    if len(data) > MAX_BYTES:
        raise ValueError(f"File is larger than {MAX_BYTES // (1024 * 1024)} MB")
    text = extract_text(filename, data).strip()
    if not text:
        raise ValueError("No text could be extracted (a scanned PDF needs OCR, which is not supported)")
    chunks = chunk_text(text)
    if len(chunks) > MAX_CHUNKS:
        raise ValueError(f"File is too large: {len(chunks)} passages (max {MAX_CHUNKS})")
    titles = [f"{filename} · part {i + 1}/{len(chunks)}" for i in range(len(chunks))]
    vecs = await llm.embed([f"{t}. {c}" for t, c in zip(titles, chunks)], "document")
    with db.conn() as c:
        c.execute("DELETE FROM kb_articles WHERE source=?", (filename,))   # re-upload replaces the old version
        c.executemany(
            "INSERT INTO kb_articles (title, category, body, embedding, source, chunk_idx) VALUES (?,?,?,?,?,?)",
            [(t, category, ch, json.dumps(v), filename, i) for i, (t, ch, v) in enumerate(zip(titles, chunks, vecs))])
    return {"filename": filename, "chunks": len(chunks), "characters": len(text)}


# ---------- Conversational RAG for the AI Assistant ----------
MAX_PER_SOURCE = 2   # keep answers from leaning on one document only


async def chat(question: str, history: list[dict]) -> dict:
    """1) rewrite follow-ups into a standalone query  2) retrieve passages  3) answer with citations."""
    search = question
    if history:
        try:
            search = await llm.rewrite_query(history, question)
        except Exception:
            search = question                      # rewriting is an optimisation; fall back to the raw question
    hits = await retrieve(search, k=8)
    chosen, per_source = [], {}
    for h in hits:                                 # best first; cap passages per file
        with db.conn() as c:
            row = c.execute("SELECT source FROM kb_articles WHERE id=?", (h["id"],)).fetchone()
        src = (row["source"] if row else None) or f"article-{h['id']}"
        h["source"] = row["source"] if row else None
        if per_source.get(src, 0) < MAX_PER_SOURCE and len(chosen) < 4:
            chosen.append(h)
            per_source[src] = per_source.get(src, 0) + 1
    if not chosen:
        return {"answer": "I could not find this in the uploaded documents.", "search_query": search,
                "sources": [], "used_llm": False}
    answer = await llm.chat_answer(question, history, chosen)
    cited = {int(n) for n in re.findall(r"\[KB(\d+)\]", answer)}      # passages the model says it used
    return {"answer": answer, "search_query": search, "used_llm": True,
            "sources": [{"id": h["id"], "title": h["title"], "source": h["source"], "category": h["category"],
                         "score": h["score"], "text": h["body"], "cited": h["id"] in cited} for h in chosen]}
