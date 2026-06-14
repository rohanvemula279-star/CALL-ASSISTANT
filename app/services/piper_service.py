"""Piper text-to-speech integration.

Synthesizes WAV audio to disk. Uses the official `piper` package when
available; falls back to the piper CLI subprocess when it is not.
"""

import asyncio
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Optional

from app.config import Settings
from app.logger import get_logger

log = get_logger(__name__)


class PiperError(Exception):
    """Piper failed to synthesize audio."""


class PiperService:
    """Piper TTS wrapper."""

    def __init__(self, settings: Settings) -> None:
        self.voice = settings.piper_voice
        self.output_dir = settings.piper_output_path
        self._piper_voice = None  # Lazy-loaded PiperVoice if SDK available
        self._cli_voice_path: Optional[Path] = None

    def startup(self) -> None:
        """Try to resolve the voice (SDK or downloaded file)."""
        try:
            from piper import PiperVoice  # type: ignore
            from piper.download import ensure_voice  # type: ignore

            try:
                voice_path, config_path = ensure_voice(self.voice)
                self._piper_voice = PiperVoice.load(str(voice_path), str(config_path))
                log.info("piper.loaded", voice=self.voice, mode="sdk")
            except Exception as e:
                log.warning("piper.sdk_load_failed", voice=self.voice, error=str(e))
        except Exception as e:
            log.warning("piper.sdk_unavailable", error=str(e))

        # Pre-locate CLI voice file (downloaded into the app's models/ dir)
        candidate = Path("models") / f"{self.voice}.onnx"
        if candidate.exists():
            self._cli_voice_path = candidate
            log.info("piper.cli_voice_resolved", path=str(candidate))

    def shutdown(self) -> None:
        self._piper_voice = None

    def is_ready(self) -> bool:
        return self._piper_voice is not None or self._cli_voice_path is not None

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
    ) -> dict:
        """Synthesize text -> WAV file. Returns metadata dict."""
        if not text or not text.strip():
            raise PiperError("Empty text for TTS")

        voice_name = voice or self.voice
        out_id = uuid.uuid4().hex[:12]
        out_path = self.output_dir / f"speech_{out_id}.wav"

        # Path 1: SDK
        if self._piper_voice is not None:
            await self._synth_sdk(text, out_path, speed)
        # Path 2: CLI subprocess
        elif self._cli_voice_path is not None or shutil.which("piper"):
            await self._synth_cli(text, voice_name, out_path, speed)
        else:
            raise PiperError(
                "Piper is not available (no SDK voice loaded and no `piper` CLI on PATH)"
            )

        return {
            "audio_path": str(out_path),
            "audio_url": f"/storage/tts/{out_path.name}",
            "duration_estimate": _estimate_wav_duration(out_path),
            "voice": voice_name,
        }

    async def _synth_sdk(self, text: str, out_path: Path, speed: float) -> None:
        try:
            import wave

            def _run() -> None:
                with wave.open(str(out_path), "wb") as wf:
                    self._piper_voice.synthesize(text, wf, speed=speed)

            await asyncio.to_thread(_run)
        except Exception as e:
            log.error("piper.sdk_synth_failed", error=str(e))
            raise PiperError(str(e)) from e

    async def _synth_cli(
        self, text: str, voice: str, out_path: Path, speed: float
    ) -> None:
        binary = shutil.which("piper")
        if not binary:
            raise PiperError("Piper CLI not found in PATH")

        cmd: list[str] = [binary, "--output_file", str(out_path)]
        voice_path = self._cli_voice_path or Path("models") / f"{voice}.onnx"
        if voice_path.exists():
            cmd.extend(["--model", str(voice_path)])
        else:
            cmd.extend(["--voice", voice])
        if speed and speed != 1.0:
            cmd.extend(["--length-scale", str(1.0 / speed)])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate(input=text.encode("utf-8"))
            if proc.returncode != 0:
                raise PiperError(
                    f"piper CLI failed: {stderr.decode(errors='ignore')[:500]}"
                )
        except FileNotFoundError as e:
            raise PiperError("piper binary not executable") from e


def _estimate_wav_duration(path: Path) -> float:
    """Estimate duration of a WAV file in seconds."""
    try:
        import wave

        with wave.open(str(path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate() or 1
            return round(frames / float(rate), 3)
    except Exception:
        return 0.0
