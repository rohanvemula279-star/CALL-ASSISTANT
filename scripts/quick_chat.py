"""Quick smoke test of the user's "Basic Python Example" flow.

Mirrors the snippet the user shared:

    def chat(message):
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "minimax-m3", "prompt": message, "stream": False},
        )
        return response.json()["response"]

Run it once Ollama is up:

    python scripts/quick_chat.py "Hello, who are you?"
"""

import sys
import requests

from app.config import get_settings


def chat(message: str) -> str:
    settings = get_settings()
    response = requests.post(
        f"{settings.ollama_host}/api/generate",
        json={
            "model": settings.ollama_model,
            "prompt": message,
            "stream": False,
        },
        timeout=settings.ollama_timeout,
    )
    response.raise_for_status()
    return response.json()["response"]


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) or "Hello, who are you?"
    print(f"-> {prompt}")
    print(f"<- {chat(prompt)}")
