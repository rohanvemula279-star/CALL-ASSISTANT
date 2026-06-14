from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.dependencies import get_container
from app.logger import get_logger

router = APIRouter(prefix="/api", tags=["greeting"])
log = get_logger(__name__)


@router.get("/greeting/english")
async def get_english_greeting():
    c = get_container()
    if c.edgetts is not None:
        path = await c.edgetts.get_greeting()
        return FileResponse(str(path), media_type="audio/wav", filename="greeting.wav")
    return FileResponse("storage/telugu_tts/telugu_greeting.wav",
                        media_type="audio/wav", filename="greeting.wav")


@router.get("/greeting")
async def get_greeting():
    return await get_english_greeting()
