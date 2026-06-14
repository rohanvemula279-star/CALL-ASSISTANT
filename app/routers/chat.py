"""POST /chat - text -> text via Ollama (with conversation history)."""

import time

from fastapi import APIRouter, HTTPException

from app.dependencies import get_ollama, get_store
from app.logger import get_logger
from app.models.schemas import ChatRequest, ChatResponse
from app.services.ollama_client import OllamaClient, OllamaError
from app.storage.store import ConversationStore

router = APIRouter(prefix="", tags=["chat"])
log = get_logger(__name__)


DEFAULT_SYSTEM = (
    "You are a concise, friendly phone-call assistant. "
    "Reply in short, clear sentences suitable for being spoken aloud. "
    "Do not use markdown, bullet points, or URLs. "
    "If you don't know, say so plainly."
)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Generate a chat reply using Ollama. Persists the exchange to history."""
    ollama: OllamaClient = get_ollama()
    store: ConversationStore = get_store()

    system = request.system_prompt or DEFAULT_SYSTEM

    # Build the message list: explicit history or auto-fetched
    if request.history:
        messages = [{"role": "system", "content": system}] + [
            {"role": m.role, "content": m.content} for m in request.history
        ] + [{"role": "user", "content": request.message}]
    elif request.call_id:
        prior = await store.history(request.call_id)
        messages = [{"role": "system", "content": system}] + [
            {"role": h["role"], "content": h["content"]} for h in prior
        ] + [{"role": "user", "content": request.message}]
    else:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": request.message},
        ]

    try:
        start = time.perf_counter()
        reply, _model_latency = await ollama.chat(
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        latency_ms = (time.perf_counter() - start) * 1000
    except OllamaError as e:
        log.error("chat.ollama_failed", error=str(e))
        raise HTTPException(status_code=502, detail=f"Ollama error: {e}")

    # Persist
    try:
        await store.add(
            role="user",
            content=request.message,
            call_id=request.call_id,
            caller=request.caller,
        )
        await store.add(
            role="assistant",
            content=reply,
            call_id=request.call_id,
            caller=request.caller,
            metadata={"latency_ms": latency_ms, "model": ollama.model},
        )
    except Exception as e:  # noqa: BLE001
        # Don't fail the response if history write fails
        log.warning("chat.store_failed", error=str(e))

    return ChatResponse(
        call_id=request.call_id,
        reply=reply,
        model=ollama.model,
        latency_ms=latency_ms,
    )
