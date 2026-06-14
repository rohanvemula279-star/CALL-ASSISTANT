"""Whisper speech-to-text integration.

Loads openai-whisper lazily so the FastAPI process can boot even on hosts
without a usable Whisper install. The transcribe() call accepts raw audio
bytes (WAV/PCM/anything ffmpeg understands).
"""

import io
import tempfile
from pathlib import Path
from typing import Optional

from app.config import Settings
from app.logger import get_logger

log = get_logger(__name__)


class WhisperError(Exception):
    """Whisper failed to process audio."""


class WhisperService:
    """Wraps openai-whisper for file/bytes transcription."""

    def __init__(self, settings: Settings) -> None:
        self.model_name = settings.whisper_model
        self.device = settings.whisper_device
        self._model = None

    def startup(self) -> None:
        """Preload the Whisper model if requested."""
        if not _whisper_available():
            log.warning("whisper.unavailable", msg="openai-whisper not installed")
            return
        try:
            log.info("whisper.loading", model=self.model_name, device=self.device)
            import whisper  # type: ignore

            self._model = whisper.load_model(self.model_name, device=self.device)
            log.info("whisper.loaded", model=self.model_name)
        except Exception as e:
            log.error("whisper.load_failed", error=str(e))
            self._model = None

    def shutdown(self) -> None:
        self._model = None

    def is_ready(self) -> bool:
        return self._model is not None

    def transcribe(
        self,
        audio_bytes: bytes,
        language: Optional[str] = None,
        filename_hint: str = "audio.wav",
    ) -> dict:
        """Transcribe audio bytes. Returns dict with 'text' and metadata.

        Writes bytes to a temp file so Whisper can process them via ffmpeg
        (the underlying lib handles .wav, .mp3, .m4a, .ogg, .flac, .webm).
        """
        if self._model is None:
            if not _whisper_available():
                raise WhisperError(
                    "openai-whisper is not installed in this environment"
                )
            raise WhisperError("Whisper model not loaded")

        suffix = Path(filename_hint).suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            options: dict = {"task": "transcribe"}
            if language:
                options["language"] = language

            result = self._model.transcribe(tmp_path, **options)
            return {
                "text": (result.get("text") or "").strip(),
                "language": result.get("language"),
                "segments": result.get("segments", []),
                "duration": _estimate_duration(tmp_path),
            }
        except Exception as e:
            log.error("whisper.transcribe_failed", error=str(e))
            raise WhisperError(str(e)) from e
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass


def _whisper_available() -> bool:
    try:
        import whisper  # type: ignore # noqa: F401

        return True
    except Exception:
        return False


def _estimate_duration(path: str) -> Optional[float]:
    """Best-effort audio duration via ffprobe."""
    import shutil
    import subprocess

    if shutil.which("ffprobe") is None:
        return None
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            stderr=subprocess.STDOUT,
            timeout=15,
        )
        return float(out.decode().strip())
    except Exception:
        return None
