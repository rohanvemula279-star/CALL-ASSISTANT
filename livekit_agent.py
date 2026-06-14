"""LiveKit voice agent — fully free/self-hosted stack.

  STT  : local openai-whisper        (agent/whisper_stt.py)
  LLM  : your local Ollama           (OpenAI-compatible /v1 endpoint)
  TTS  : Microsoft edge-tts (Telugu) (agent/edge_tts_plugin.py)
  VAD  : silero                      (free, bundled plugin)

No paid APIs (no Deepgram/OpenAI/ElevenLabs). Uses LiveKit Cloud's free tier
via LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET in .env.

Run the worker (registers with LiveKit Cloud and waits for calls):

    python livekit_agent.py dev

Then connect a caller to a room (LiveKit SIP inbound, or the test playground)
and the agent joins automatically and starts talking.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.plugins import openai, silero

from agent.edge_tts_plugin import EdgeTTS
from agent.whisper_stt import WhisperSTT

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "minimax-m3:cloud")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE") or None  # None = auto-detect
TTS_VOICE = os.getenv("AGENT_TTS_VOICE", "te-IN-MohanNeural")

# Ollama exposes an OpenAI-compatible API at /v1.
OLLAMA_OPENAI_BASE = f"{OLLAMA_HOST}/v1"

SYSTEM_PROMPT = (
    "You are Max, Rohan's friendly phone assistant. Rohan is busy and cannot "
    "take the call. Speak naturally in the caller's language (Telugu or "
    "English). Greet them, explain you're Rohan's assistant, ask who is "
    "calling and what they need, and tell them you'll pass the message to "
    "Rohan. Keep replies short and conversational — this is a phone call."
)

GREETING = (
    "నమస్తే! నేను రోహన్ గారి అసిస్టెంట్ మాక్స్‌ని. రోహన్ గారు ప్రస్తుతం బిజీగా "
    "ఉన్నారు. మీరు ఎవరు మాట్లాడుతున్నారో, ఏం కావాలో చెప్పండి — నేను రోహన్ గారికి "
    "చెప్తాను."
)


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    session = AgentSession(
        stt=WhisperSTT(
            model=WHISPER_MODEL,
            device=WHISPER_DEVICE,
            language=WHISPER_LANGUAGE,
        ),
        llm=openai.LLM.with_ollama(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_OPENAI_BASE,
        ),
        tts=EdgeTTS(voice=TTS_VOICE),
        vad=silero.VAD.load(),
    )

    await session.start(
        agent=Agent(instructions=SYSTEM_PROMPT),
        room=ctx.room,
    )

    # Speak first so the caller hears the assistant immediately on answer.
    await session.say(GREETING, allow_interruptions=True)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
