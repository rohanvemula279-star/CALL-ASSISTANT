"""Local Whisper STT plugin for livekit-agents (free, no API key).

Wraps openai-whisper. Audio is buffered by the AgentSession (VAD-gated), then
handed to this plugin as a single AudioBuffer for one-shot recognition. The
model is loaded lazily on the first call and reused.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from livekit.agents import (
    DEFAULT_API_CONNECT_OPTIONS,
    APIConnectOptions,
    stt,
    utils,
)
from livekit.agents.types import NOT_GIVEN, NotGivenOr
from livekit.agents.utils import is_given

# Whisper expects mono 16 kHz float32 PCM.
WHISPER_SAMPLE_RATE = 16000


class WhisperSTT(stt.STT):
    """Speech-to-text backed by a locally loaded openai-whisper model."""

    def __init__(
        self,
        *,
        model: str = "base",
        device: str = "cpu",
        language: Optional[str] = None,
    ) -> None:
        # Whisper is non-streaming: we only support buffered (interim=False) recognition.
        super().__init__(
            capabilities=stt.STTCapabilities(streaming=False, interim_results=False)
        )
        self._model_name = model
        self._device = device
        self._language = language
        self._model = None
        self._lock = asyncio.Lock()

    async def _ensure_model(self):
        if self._model is not None:
            return self._model
        async with self._lock:
            if self._model is None:
                # load_model is blocking + CPU heavy -> run off the event loop.
                self._model = await asyncio.to_thread(self._load_model)
        return self._model

    def _load_model(self):
        import whisper  # type: ignore

        return whisper.load_model(self._model_name, device=self._device)

    async def _recognize_impl(
        self,
        buffer: utils.AudioBuffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> stt.SpeechEvent:
        import numpy as np
        from livekit import rtc

        model = await self._ensure_model()

        # Collapse the (possibly multi-frame) buffer into one mono frame, then
        # resample to whisper's required 16 kHz if the call rate differs.
        frame = utils.audio.combine_frames(buffer)
        if frame.sample_rate != WHISPER_SAMPLE_RATE:
            resampler = rtc.AudioResampler(
                input_rate=frame.sample_rate,
                output_rate=WHISPER_SAMPLE_RATE,
                num_channels=frame.num_channels,
            )
            resampled = resampler.push(frame) + resampler.flush()
            if resampled:
                frame = utils.audio.combine_frames(resampled)

        # int16 PCM -> float32 in [-1, 1], the format whisper.transcribe expects.
        samples = np.frombuffer(frame.data, dtype=np.int16).astype(np.float32) / 32768.0

        lang = language if is_given(language) else self._language
        options: dict = {"task": "transcribe", "fp16": False}
        if lang:
            options["language"] = lang

        result = await asyncio.to_thread(model.transcribe, samples, **options)
        text = (result.get("text") or "").strip()
        detected = result.get("language") or lang or "en"

        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[
                stt.SpeechData(text=text, language=detected, confidence=1.0)
            ],
        )
