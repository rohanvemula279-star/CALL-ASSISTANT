from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.dependencies import get_piper
from app.logger import get_logger

router = APIRouter(prefix="/api", tags=["greeting"])
log = get_logger(__name__)

GREETING_TEXT = "Hi, Rohan is currently busy. Please leave a message after the beep, and he will get back to you as soon as possible."


@router.get("/greeting")
async def get_greeting():
    piper = get_piper()
    greeting_dir = Path("storage/greeting")
    greeting_dir.mkdir(parents=True, exist_ok=True)
    greeting_path = greeting_dir / "greeting.wav"

    if not greeting_path.exists():
        if not piper.is_ready():
            log.warning("greeting.piper_not_ready")
            greeting_path.write_bytes(_fallback_wav())
        else:
            result = await piper.synthesize(GREETING_TEXT)
            shutil.move(result["audio_path"], str(greeting_path))

    return FileResponse(
        str(greeting_path),
        media_type="audio/wav",
        filename="greeting.wav",
    )


def _fallback_wav() -> bytes:
    import struct
    import wave
    import io

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"")
    return buf.getvalue()
