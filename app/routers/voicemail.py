from __future__ import annotations

import os
import time
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from app.dependencies import get_container
from app.logger import get_logger

router = APIRouter(prefix="", tags=["voicemail"])
log = get_logger(__name__)


class VoicemailResponse(BaseModel):
    ok: bool
    message: str
    call_id: str
    transcript: Optional[str] = None
    summary: Optional[str] = None
    callback_id: Optional[int] = None
    telegram_sent: bool = False


@router.post("/voicemail", response_model=VoicemailResponse)
async def upload_voicemail(
    audio: UploadFile,
    number: str = "",
    name: str = "",
    call_id: str = "",
):
    c = get_container()
    if not call_id:
        call_id = str(uuid.uuid4())

    if not number:
        number = "unknown"

    wav_path = None
    try:
        os.makedirs("storage/voicemails", exist_ok=True)
        wav_path = f"storage/voicemails/{call_id}.wav"
        content = await audio.read()
        with open(wav_path, "wb") as f:
            f.write(content)

        log.info(
            "voicemail.received",
            call_id=call_id,
            number=number,
            name=name or "unknown",
            size=len(content),
        )

        transcript = None
        if c.whisper.is_ready():
            try:
                with open(wav_path, "rb") as f:
                    audio_bytes = f.read()
                result = c.whisper.transcribe(audio_bytes)
                transcript = result.get("text", "").strip() or None
            except Exception as e:
                log.warning("voicemail.whisper_failed", error=str(e))

        summary = None
        if transcript:
            try:
                prompt = (
                    f"Caller: {name or 'Unknown'} ({number})\n"
                    f"Message: {transcript}\n\n"
                    "Summarize this voicemail message in 1-2 sentences."
                )
                summary, _ = await c.ollama.generate(
                    prompt=prompt,
                    system="You summarize voicemails concisely. No emojis, no markdown.",
                    temperature=0.3,
                    max_tokens=150,
                )
                summary = (summary or "").strip() or None
            except Exception as e:
                log.warning("voicemail.ollama_failed", error=str(e))

        callback_id = None
        try:
            callback_id = await c.store.create_callback(
                call_id=call_id,
                caller=number,
                caller_name=name or None,
                action="callback",
            )
        except Exception as e:
            log.warning("voicemail.callback_failed", error=str(e))

        telegram_sent = False
        if c.telegram.enabled:
            try:
                msg = f"<b>📞 Voicemail from {name or number}</b>\n"
                if name:
                    msg += f"<b>Number:</b> {number}\n"
                if transcript:
                    msg += f"\n<b>Message:</b>\n{transcript}\n"
                if summary:
                    msg += f"\n<b>Summary:</b> {summary}\n"
                msg += f"\n⏰ {time.strftime('%I:%M %p')}"
                resp = await c.telegram.send_message(msg)
                telegram_sent = bool(resp.get("ok"))
            except Exception as e:
                log.warning("voicemail.telegram_failed", error=str(e))

        if transcript:
            try:
                await c.store.add(
                    role="user",
                    content=f"Voicemail from {name or number}: {transcript}",
                    call_id=call_id,
                    caller=number,
                    metadata={"event": "voicemail"},
                )
                if summary:
                    await c.store.add(
                        role="assistant",
                        content=f"Summary: {summary}",
                        call_id=call_id,
                        caller=number,
                    )
            except Exception as e:
                log.warning("voicemail.store_failed", error=str(e))

        return VoicemailResponse(
            ok=True,
            message="voicemail_processed",
            call_id=call_id,
            transcript=transcript,
            summary=summary,
            callback_id=callback_id,
            telegram_sent=telegram_sent,
        )

    except Exception as e:
        log.error("voicemail.processing_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
