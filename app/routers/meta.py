"""Health and conversation history endpoints."""

from fastapi import APIRouter, HTTPException

from app.dependencies import get_ollama, get_piper, get_store, get_whisper
from app.models.schemas import HealthResponse
from app.services.ollama_client import OllamaError
from app.storage.store import ConversationStore

router = APIRouter(prefix="", tags=["meta"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe + service status snapshot."""
    ollama = get_ollama()
    try:
        ollama_status = await ollama.health()
    except OllamaError as e:
        ollama_status = {"host": ollama.host, "available": False, "error": str(e)}

    return HealthResponse(
        status="ok",
        environment="production",
        ollama=ollama_status,
        whisper={"ready": get_whisper().is_ready(), "model": get_whisper().model_name},
        piper={"ready": get_piper().is_ready(), "voice": get_piper().voice},
    )


@router.get("/history/{call_id}")
async def history(call_id: str, limit: int = 50):
    """Fetch conversation history for a call."""
    store: ConversationStore = get_store()
    if limit <= 0 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be 1..500")
    rows = await store.history(call_id, limit=limit)
    return {"call_id": call_id, "count": len(rows), "items": rows}


@router.get("/history")
async def recent_history(limit: int = 50):
    """Recent conversation entries across all calls."""
    store: ConversationStore = get_store()
    if limit <= 0 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be 1..500")
    rows = await store.recent(limit=limit)
    return {"count": len(rows), "items": rows}
