from __future__ import annotations

import os
import time
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from app.dependencies import get_container
from app.logger import get_logger

router = APIRouter(prefix="/telugu", tags=["telugu"])
log = get_logger(__name__)


class TeluguVoicemailResponse(BaseModel):
    ok: bool
    message: str
    call_id: str
    transcript: Optional[str] = None
    summary: Optional[str] = None
    callback_id: Optional[int] = None
    telegram_sent: bool = False


SUMMARY_SYSTEM = (
    "You are a Telugu/English bilingual assistant. Summarize this voicemail "
    "in Telugu. Use Telugu script (తెలుగు) for the summary. "
    "Be concise - 1-2 sentences max. No emojis."
)


@router.post("/voicemail", response_model=TeluguVoicemailResponse)
async def upload_telugu_voicemail(
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

    wav_path = f"storage/voicemails/{call_id}.wav"
    os.makedirs("storage/voicemails", exist_ok=True)

    try:
        content = await audio.read()
        with open(wav_path, "wb") as f:
            f.write(content)

        log.info("telugu_voicemail.received", call_id=call_id, number=number, size=len(content))

        transcript = None
        if c.whisper.is_ready():
            try:
                with open(wav_path, "rb") as f:
                    result = c.whisper.transcribe(f.read(), language="te")
                transcript = result.get("text", "").strip() or None
            except Exception as e:
                log.warning("telugu_voicemail.whisper_failed", error=str(e))

        summary = None
        if transcript:
            try:
                prompt = (
                    f"Caller: {name or 'Unknown'} ({number})\n"
                    f"Message: {transcript}\n\n"
                    "Summarize this voicemail in Telugu (తెలుగు)."
                )
                summary, _ = await c.ollama.generate(
                    prompt=prompt,
                    system=SUMMARY_SYSTEM,
                    temperature=0.3,
                    max_tokens=200,
                )
                summary = (summary or "").strip() or None
            except Exception as e:
                log.warning("telugu_voicemail.ollama_failed", error=str(e))

        callback_id = None
        try:
            callback_id = await c.store.create_callback(
                call_id=call_id, caller=number,
                caller_name=name or None, action="callback",
            )
        except Exception as e:
            log.warning("telugu_voicemail.callback_failed", error=str(e))

        telegram_sent = False
        if c.telegram.enabled:
            try:
                msg = f"<b>📞 తెలుగు వాయిస్‌మెయిల్</b>\n"
                if name:
                    msg += f"<b>నుండి:</b> {name} ({number})\n"
                else:
                    msg += f"<b>నంబర్:</b> {number}\n"
                if transcript:
                    msg += f"\n<b>వాయిస్ సందేశం:</b>\n{transcript}\n"
                if summary:
                    msg += f"\n<b>సారాంశం:</b>\n{summary}\n"
                msg += f"\n⏰ {time.strftime('%I:%M %p')}"
                await c.telegram.send_message(msg)
                telegram_sent = True
            except Exception as e:
                log.warning("telugu_voicemail.telegram_failed", error=str(e))

        return TeluguVoicemailResponse(
            ok=True, message="processed", call_id=call_id,
            transcript=transcript, summary=summary,
            callback_id=callback_id, telegram_sent=telegram_sent,
        )
    except Exception as e:
        log.error("telugu_voicemail.error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
