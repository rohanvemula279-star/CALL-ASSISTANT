"""
LiveKit Voice Agent — connects to LiveKit Cloud and uses Ollama for AI.

Run:
  python livekit_agent.py

Requires LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET in .env
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "minimax-m3:cloud")

GREETING = (
    "Hi, Rohan is currently busy. Please leave a message after the tone, "
    "and he will get back to you as soon as possible."
)


async def main():
    if not all([LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET]):
        print("ERROR: Set LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET in .env")
        sys.exit(1)

    print(f"LiveKit Agent starting...")
    print(f"  URL: {LIVEKIT_URL}")
    print(f"  Ollama: {OLLAMA_HOST} ({OLLAMA_MODEL})")
    print()
    print("NOTE: Install livekit-agents and plugins to enable voice AI:")
    print("  pip install livekit-agents livekit-plugins-deepgram livekit-plugins-openai")
    print()
    print("Then uncomment the full agent code below.")
    print()

    """
    Full agent implementation (uncomment when dependencies are installed):
    
    from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
    
    async def entrypoint(ctx: JobContext):
        await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
        # Your voice agent logic here
        pass
    
    if __name__ == "__main__":
        cli.run_app(WorkerOptions(entrypoint_factory=entrypoint))
    """


if __name__ == "__main__":
    asyncio.run(main())
