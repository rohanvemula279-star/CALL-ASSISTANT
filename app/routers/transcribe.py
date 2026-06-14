"""POST /transcribe - audio bytes -> text via Whisper."""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.dependencies import get_whisper
from app.models.schemas import TranscribeResponse
from app.services.whisper_service import WhisperError, WhisperService

router = APIRouter(prefix="", tags=["transcribe"])


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    audio: UploadFile = File(..., description="Audio file (wav, mp3, m4a, ogg)"),
    language: str | None = Form(default=None),
) -> TranscribeResponse:
    """Transcribe uploaded audio to text using Whisper."""
    whisper: WhisperService = get_whisper()
    if not whisper.is_ready():
        raise HTTPException(status_code=503, detail="Whisper model not ready")

    try:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio upload")

        result = whisper.transcribe(
            audio_bytes=audio_bytes,
            language=language,
            filename_hint=audio.filename or "audio.wav",
        )
    except WhisperError as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))

    return TranscribeResponse(
        text=result.get("text", ""),
        language=result.get("language"),
        duration=result.get("duration"),
        segments=result.get("segments"),
    )
