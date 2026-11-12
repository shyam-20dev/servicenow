"""Retrieval-Augmented Generation (RAG) pipeline.

Pipeline:  document -> chunks -> embeddings -> SQLite vector store
           question -> embedding -> cosine similarity -> top-k chunks
           top-k chunks + question -> LLM -> grounded answer + citations

Two retrieval modes (always reported to the user):
  * "semantic"  - real embeddings from the configured provider + cosine similarity.
  * "keyword"   - TF-IDF keyword matching. Used ONLY when no embedding API is
                  available or it failed. It is labelled as a fallback.
Vectors are stored as JSON in SQLite: the knowledge base is tiny, so a plain
Python cosine loop is fast and avoids heavy dependencies (ChromaDB/FAISS).
"""
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..config import get_settings
from ..database import get_conn, now_iso
from . import llm_service
from .llm_service import LLMError

CHUNK_SIZE = 700      # characters per chunk
CHUNK_OVERLAP = 100   # characters shared between neighbouring long chunks
TOP_K = 3
KEYWORD_MIN_SCORE = 0.12
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}

STOPWORDS = set(
    "a an the and or but if then of to in on at for with without from by is are was were be been am do does did "
    "my me i we you your our it its this that these those how what why when where which who can could should would "
    "not no cannot cant dont doesnt isnt please help need want get got have has had there here as so up out into "
    "about after before again any some more most other than too very just also company access".split()
)


# --------------------------------------------------------------------------
# Chunking
# --------------------------------------------------------------------------
def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Paragraph-aware chunking: pack paragraphs up to `size`; hard-split very long ones."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: List[str] = []
    current = ""
    for para in paragraphs:
        if len(para) > size:  # long paragraph: sliding window with overlap
            if current:
                chunks.append(current)
                current = ""
            step = max(size - overlap, 1)
            for start in range(0, len(para), step):
                chunks.append(para[start:start + size])
                if start + size >= len(para):
                    break
            continue
        if current and len(current) + len(para) + 2 > size:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


# --------------------------------------------------------------------------
# Keyword (fallback) scoring
# --------------------------------------------------------------------------
def _stem(w: str) -> str:
    for suf in ("ation", "ing", "ion", "ly", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    return w


def tokenize(text: str) -> List[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [_stem(w) for w in words if w not in STOPWORDS and len(w) > 1]


def _tfidf_scores(query: str, chunks: List[dict]) -> List[float]:
    docs = [Counter(tokenize(c["text"])) for c in chunks]
    n = len(docs)
    df: Counter = Counter()
    for d in docs:
        df.update(d.keys())
    idf = {t: math.log((n + 1) / (df[t] + 1)) + 1 for t in df}
    q = Counter(tokenize(query))
    qvec = {t: c * idf.get(t, 0.0) for t, c in q.items()}
    qnorm = math.sqrt(sum(v * v for v in qvec.values()))
    scores = []
    for d in docs:
        dvec = {t: c * idf[t] for t, c in d.items()}
        dnorm = math.sqrt(sum(v * v for v in dvec.values()))
        dot = sum(qvec[t] * dvec.get(t, 0.0) for t in qvec)
        scores.append(dot / (qnorm * dnorm) if qnorm and dnorm else 0.0)
    return scores


# --------------------------------------------------------------------------
# Semantic scoring
# --------------------------------------------------------------------------
def cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


# --------------------------------------------------------------------------
# Ingestion
# --------------------------------------------------------------------------
def extract_text(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Only .txt, .md and .pdf files are supported.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("File is larger than the 2 MB limit.")
    if ext == ".pdf":
        try:
            from io import BytesIO
            from pypdf import PdfReader
        except ImportError:
            raise ValueError("PDF support needs the 'pypdf' package (pip install pypdf).")
        try:
            reader = PdfReader(BytesIO(data))
            text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            raise ValueError("Could not read this PDF (it may be encrypted or scanned images).")
    else:
        text = data.decode("utf-8", errors="replace")
    if len(text.strip()) < 20:
        raise ValueError("The document has no readable text.")
    return text


def _title_from(filename: str, text: str) -> str:
    m = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    return m.group(1).strip()[:120] if m else Path(filename).stem.replace("_", " ").replace("-", " ").title()


def ingest_document(filename: str, text: str, source: str = "uploaded") -> dict:
    """Store a document, chunk it and (if possible) embed the chunks. Replaces same-named docs."""
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("The document has no readable text.")
    embeddings: Optional[List[List[float]]] = None
    embed_note = ""
    s = get_settings()
    if s.embeddings_configured:
        try:
            embeddings = llm_service.embed(chunks)
        except LLMError as e:
            embed_note = f"Embeddings unavailable ({e}); stored for keyword search only."
    else:
        embed_note = "No embedding key configured; stored for keyword (fallback) search only."

    with get_conn() as conn:
        conn.execute("DELETE FROM knowledge_documents WHERE filename = ?", (filename,))
        cur = conn.execute(
            "INSERT INTO knowledge_documents (filename, title, source, content, chunk_count, embedded, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (filename, _title_from(filename, text), source, text, len(chunks), 1 if embeddings else 0, now_iso()),
        )
        doc_id = cur.lastrowid
        for i, chunk in enumerate(chunks):
            conn.execute(
                "INSERT INTO knowledge_chunks (document_id, chunk_index, text, embedding, embedding_model) "
                "VALUES (?,?,?,?,?)",
                (doc_id, i, chunk,
                 json.dumps(embeddings[i]) if embeddings else None,
                 s.embedding_model if embeddings else None),
            )
    return {"id": doc_id, "filename": filename, "chunks": len(chunks),
            "embedded": bool(embeddings), "note": embed_note}


def load_bundled_knowledge_base() -> int:
    """Index knowledge_base/*.md|txt that are not yet in the database. Returns count added."""
    kb = get_settings().kb_dir
    if not kb.exists():
        return 0
    with get_conn() as conn:
        existing = {r["filename"] for r in conn.execute("SELECT filename FROM knowledge_documents")}
    added = 0
    for path in sorted(kb.iterdir()):
        if path.suffix.lower() in {".md", ".txt"} and path.name not in existing:
            ingest_document(path.name, path.read_text(encoding="utf-8"), source="bundled")
            added += 1
    return added


def reindex_all() -> dict:
    """Re-embed every document (use after adding an embedding key)."""
    with get_conn() as conn:
        docs = [dict(r) for r in conn.execute("SELECT filename, content, source FROM knowledge_documents")]
    results = [ingest_document(d["filename"], d["content"], d["source"]) for d in docs]
    return {"documents": len(results), "embedded": sum(1 for r in results if r["embedded"])}


def list_documents() -> List[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, filename, title, source, chunk_count, embedded, created_at, "
            "substr(content, 1, 280) AS preview FROM knowledge_documents ORDER BY title"
        ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Retrieval
# --------------------------------------------------------------------------
def _load_chunks() -> List[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT c.id, c.text, c.embedding, c.embedding_model, d.filename, d.title "
            "FROM knowledge_chunks c JOIN knowledge_documents d ON d.id = c.document_id"
        ).fetchall()
    return [dict(r) for r in rows]


def retrieve(query: str, k: int = TOP_K) -> Dict:
    """Return {mode, note, hits}. Hits below the relevance threshold are dropped."""
    chunks = _load_chunks()
    s = get_settings()
    note = ""
    if not chunks:
        return {"mode": "keyword", "note": "The knowledge base is empty.", "hits": []}

    scored: List[Tuple[float, dict]] = []
    mode = "keyword"
    threshold = KEYWORD_MIN_SCORE

    embedded_chunks = [c for c in chunks if c["embedding"] and c["embedding_model"] == s.embedding_model]
    if s.embeddings_configured and embedded_chunks:
        try:
            qvec = llm_service.embed([query])[0]
            scored = [(cosine(qvec, json.loads(c["embedding"])), c) for c in embedded_chunks]
            mode, threshold = "semantic", s.embedding_min_score
        except LLMError as e:
            note = f"Embedding search failed ({e}); used keyword fallback instead."
    elif s.embeddings_configured:
        note = "Documents are not embedded yet (run reindex); used keyword fallback."
    else:
        note = "No embedding key configured; used keyword (TF-IDF) fallback, not semantic search."

    if mode == "keyword":
        scores = _tfidf_scores(query, chunks)
        scored = list(zip(scores, chunks))

    scored.sort(key=lambda t: t[0], reverse=True)
    hits, seen_docs = [], Counter()
    for score, c in scored:
        if score < threshold:
            break
        if seen_docs[c["filename"]] >= 2:  # at most 2 chunks per document -> diverse sources
            continue
        seen_docs[c["filename"]] += 1
        hits.append({"document": c["filename"], "title": c["title"],
                     "excerpt": c["text"], "score": round(score, 3)})
        if len(hits) >= k:
            break
    return {"mode": mode, "note": note, "hits": hits}


# --------------------------------------------------------------------------
# Answer generation
# --------------------------------------------------------------------------
NO_KNOWLEDGE_MSG = ("The knowledge base does not contain enough information to answer this. "
                    "Please raise an incident so a support engineer can help.")

RAG_SYSTEM_PROMPT = (
    "You are SmartDesk, an internal IT helpdesk assistant. Answer the employee's question using ONLY the "
    "numbered context excerpts provided. Do not use outside knowledge. Be concise and give numbered steps "
    "where appropriate. Cite the excerpts you used like [1] or [2]. If the context does not contain the "
    "answer, reply with exactly: INSUFFICIENT_CONTEXT"
)


def _extractive_answer(hits: List[dict]) -> str:
    top = hits[0]
    return (f"(No LLM is configured, so this is NOT a generated answer - it is the most relevant "
            f"passage from the knowledge base: \"{top['title']}\".)\n\n{top['excerpt']}")


def answer_question(question: str, session_id: str = "demo-session") -> Dict:
    retrieval = retrieve(question)
    hits = retrieval["hits"]
    notes = [retrieval["note"]] if retrieval["note"] else []
    s = get_settings()

    if not hits:
        answer, answer_mode = NO_KNOWLEDGE_MSG, "no-knowledge"
    elif s.llm_configured:
        context = "\n\n".join(f"[{i}] (source: {h['title']})\n{h['excerpt']}" for i, h in enumerate(hits, 1))
        try:
            text = llm_service.chat(
                [{"role": "system", "content": RAG_SYSTEM_PROMPT},
                 {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}],
                temperature=0.1,
            ).strip()
            if "INSUFFICIENT_CONTEXT" in text:
                answer, answer_mode, hits = NO_KNOWLEDGE_MSG, "no-knowledge", []
            else:
                answer, answer_mode = text, "rag-llm"
        except LLMError as e:
            answer, answer_mode = _extractive_answer(hits), "extractive-fallback"
            notes.append(f"LLM call failed ({e}); showing the retrieved passage instead.")
    else:
        answer, answer_mode = _extractive_answer(hits), "extractive-fallback"
        notes.append("No LLM API key configured; answer generation is disabled.")

    with get_conn() as conn:
        conn.execute("INSERT INTO chat_history (session_id, role, content, mode, sources, created_at) "
                     "VALUES (?,?,?,?,?,?)", (session_id, "user", question, None, None, now_iso()))
        conn.execute("INSERT INTO chat_history (session_id, role, content, mode, sources, created_at) "
                     "VALUES (?,?,?,?,?,?)",
                     (session_id, "assistant", answer, answer_mode,
                      json.dumps([h["document"] for h in hits]), now_iso()))
    return {"answer": answer, "answer_mode": answer_mode, "retrieval_mode": retrieval["mode"],
            "sources": hits, "notes": notes}
