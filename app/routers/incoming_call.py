"""POST /incoming-call - mobile gateway webhook (missed-call reports).

Wires the request to the [MissedCallService] which:
  - persists the event
  - asks Ollama for a voicemail summary (only if a transcript is given)
  - synthesizes Piper TTS
  - creates a callback row
  - sends a Telegram notification with action buttons
  - returns the result to the Android client
"""

from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.dependencies import get_missed_call_service
from app.logger import get_logger
from app.services.missed_call_service import IncomingCallEvent, MissedCallService

router = APIRouter(prefix="", tags=["gateway"])
log = get_logger(__name__)


class IncomingCallRequest(BaseModel):
    number: str = Field(..., min_length=1)
    name: Optional[str] = None
    timestamp_ms: int
    call_id: str
    device: Optional[str] = None
    # Optional: only set when the caller actually left a voicemail.
    voicemail_transcript: Optional[str] = None
    context: Optional[dict[str, Any]] = None


class IncomingCallResponse(BaseModel):
    ok: bool
    message: str
    call_id: str
    reply_text: Optional[str] = None
    reply_audio_url: Optional[str] = None
    summary: Optional[str] = None
    callback_id: Optional[int] = None
    telegram: Optional[dict[str, Any]] = None
    contact_exists: bool = False
    previous_call_count: int = 0
    voicemail: bool = False


# 60-second dedupe window per call_id
_seen: dict[str, float] = {}


@router.post("/incoming-call", response_model=IncomingCallResponse)
async def incoming_call(req: IncomingCallRequest) -> IncomingCallResponse:
    service: MissedCallService = get_missed_call_service()

    now = time.time()
    last = _seen.get(req.call_id)
    if last and (now - last) < 60:
        log.info("incoming_call.duplicate", call_id=req.call_id)
        return IncomingCallResponse(
            ok=True, message="duplicate", call_id=req.call_id
        )
    _seen[req.call_id] = now

    try:
        result = await service.handle(
            IncomingCallEvent(
                number=req.number,
                name=req.name,
                timestamp_ms=req.timestamp_ms,
                call_id=req.call_id,
                device=req.device,
                voicemail_transcript=req.voicemail_transcript,
                context=req.context,
            )
        )
    except Exception as e:  # noqa: BLE001
        log.error("incoming_call.failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

    return IncomingCallResponse(
        ok=result.ok,
        message=result.message,
        call_id=result.call_id,
        reply_text=result.reply_text,
        reply_audio_url=result.reply_audio_url,
        summary=result.summary,
        callback_id=result.callback_id,
        telegram=result.telegram,
        contact_exists=result.contact_exists,
        previous_call_count=result.previous_call_count,
        voicemail=result.voicemail,
    )
