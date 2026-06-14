"""edge-tts TTS plugin for livekit-agents (free, no API key).

Streams Microsoft Edge neural voices. Defaults to the Telugu voice used across
this project. edge-tts yields MP3 chunks, which we hand to the AudioEmitter with
an audio/mp3 mime type; livekit decodes them to PCM for the call.
"""

from __future__ import annotations

import edge_tts
from livekit.agents import (
    DEFAULT_API_CONNECT_OPTIONS,
    APIConnectOptions,
    tts,
    utils,
)

# edge-tts returns 24 kHz mono MP3 for neural voices.
SAMPLE_RATE = 24000
NUM_CHANNELS = 1
DEFAULT_VOICE = "te-IN-MohanNeural"


class EdgeTTS(tts.TTS):
    """Text-to-speech backed by Microsoft edge-tts."""

    def __init__(self, *, voice: str = DEFAULT_VOICE) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=SAMPLE_RATE,
            num_channels=NUM_CHANNELS,
        )
        self._voice = voice

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> "ChunkedStream":
        return ChunkedStream(tts=self, input_text=text, conn_options=conn_options)


class ChunkedStream(tts.ChunkedStream):
    def __init__(self, *, tts: EdgeTTS, input_text: str, conn_options: APIConnectOptions) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._voice = tts._voice

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        request_id = utils.shortuuid()
        output_emitter.initialize(
            request_id=request_id,
            sample_rate=SAMPLE_RATE,
            num_channels=NUM_CHANNELS,
            mime_type="audio/mp3",
        )

        communicate = edge_tts.Communicate(self.input_text, self._voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio" and chunk.get("data"):
                output_emitter.push(chunk["data"])

        output_emitter.flush()
