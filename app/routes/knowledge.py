from fastapi import APIRouter, File, HTTPException, UploadFile

from ..services import rag_service

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Base"])


@router.get("")
def list_documents():
    return rag_service.list_documents()


@router.post("/upload", status_code=201)
async def upload(file: UploadFile = File(...)):
    data = await file.read(rag_service.MAX_UPLOAD_BYTES + 1)
    name = (file.filename or "document.txt").replace("\\", "/").split("/")[-1][:120]
    try:
        text = rag_service.extract_text(name, data)
        return rag_service.ingest_document(name, text, source="uploaded")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/reindex")
def reindex():
    """Re-chunk and re-embed all documents (use after adding an embedding API key)."""
    return rag_service.reindex_all()


@router.get("/search")
def search(q: str):
    """Debug endpoint: show raw retrieval results (no LLM involved)."""
    if len(q.strip()) < 2 or len(q) > 500:
        raise HTTPException(422, "q must be 2-500 characters")
    return rag_service.retrieve(q)
