"""POST /speak - text -> audio file via Piper."""

from fastapi import APIRouter, HTTPException

from app.dependencies import get_piper
from app.models.schemas import SpeakRequest, SpeakResponse
from app.services.piper_service import PiperError, PiperService

router = APIRouter(prefix="", tags=["tts"])


@router.post("/speak", response_model=SpeakResponse)
async def speak(request: SpeakRequest) -> SpeakResponse:
    """Synthesize speech audio from text using Piper."""
    piper: PiperService = get_piper()
    if not piper.is_ready():
        raise HTTPException(status_code=503, detail="Piper voice not ready")

    try:
        result = await piper.synthesize(
            text=request.text,
            voice=request.voice,
            speed=request.speed,
        )
    except PiperError as e:
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {e}")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))

    return SpeakResponse(**result)
