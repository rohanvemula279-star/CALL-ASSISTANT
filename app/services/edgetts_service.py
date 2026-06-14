from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from typing import Optional

import edge_tts
import structlog

log = structlog.get_logger(__name__)

TELUGU_VOICE = "te-IN-MohanNeural"
OUTPUT_DIR = Path("storage/telugu_tts")


class EdgeTTSError(Exception):
    pass


class EdgeTTSService:
    def __init__(self) -> None:
        self.output_dir = OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def startup(self) -> None:
        log.info("edgetts.startup")

    async def shutdown(self) -> None:
        log.info("edgetts.shutdown")

    async def synthesize(self, text: str, voice: str = TELUGU_VOICE) -> dict:
        out_id = uuid.uuid4().hex[:12]
        mp3_path = self.output_dir / f"speech_{out_id}.mp3"
        wav_path = self.output_dir / f"speech_{out_id}.wav"

        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(mp3_path))

            subprocess.run(
                ["ffmpeg", "-y", "-i", str(mp3_path),
                 "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                 str(wav_path)],
                capture_output=True, check=True,
            )

            mp3_path.unlink(missing_ok=True)
            duration = float(
                subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries",
                     "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                     str(wav_path)],
                    capture_output=True, text=True,
                ).stdout.strip() or 0
            )

            return {
                "audio_path": str(wav_path),
                "audio_url": f"/storage/telugu_tts/{wav_path.name}",
                "duration_estimate": round(duration, 2),
                "voice": voice,
            }
        except Exception as e:
            raise EdgeTTSError(str(e)) from e

    async def get_greeting(self) -> Path:
        greeting_path = self.output_dir / "telugu_greeting.wav"
        if greeting_path.exists():
            return greeting_path

        result = await self.synthesize(
            "రోహన్ సర్ బిజీగా ఉన్నారు. నేను అతని అసిస్టెంట్ మాక్స్ ని. "
            "నేను మీరు చెప్పిన సమాచారాన్ని సర్ కి పంపిస్తాను."
        )
        src = Path(result["audio_path"])
        src.rename(greeting_path)
        return greeting_path
