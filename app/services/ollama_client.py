"""Ollama client wrapper for local model inference.

Falls back to raw HTTP via httpx when the official `ollama` SDK is unavailable
or fails. Always points at the configured local Ollama server.
"""

import time
from typing import Optional

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.config import Settings
from app.logger import get_logger

log = get_logger(__name__)


class OllamaError(Exception):
    """Raised when the Ollama client fails irrecoverably."""


class OllamaClient:
    """Thin client for the Ollama HTTP API.

    Uses /api/generate for plain prompts and /api/chat for multi-turn.
    """

    def __init__(self, settings: Settings) -> None:
        self.host = settings.ollama_host.rstrip("/")
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def startup(self) -> None:
        """Open the HTTP client and verify reachability."""
        self._client = httpx.AsyncClient(
            base_url=self.host,
            timeout=httpx.Timeout(self.timeout),
        )
        try:
            await self.health()
            log.info("ollama.connected", host=self.host, model=self.model)
        except Exception as e:
            log.warning("ollama.unreachable", error=str(e))

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _post(self, path: str, payload: dict) -> dict:
        if self._client is None:
            raise OllamaError("Client not started")
        try:
            response = await self._client.post(path, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise OllamaError(
                f"Ollama returned {e.response.status_code}: {e.response.text[:300]}"
            ) from e
        except httpx.RequestError as e:
            raise OllamaError(f"Ollama request error: {e}") from e

    async def health(self) -> dict:
        """Check whether Ollama is reachable and list available models."""
        if self._client is None:
            raise OllamaError("Client not started")
        response = await self._client.get("/api/tags")
        response.raise_for_status()
        data = response.json()
        return {
            "host": self.host,
            "model": self.model,
            "available": any(
                m.get("name", "").startswith(self.model) for m in data.get("models", [])
            ),
            "models": [m.get("name") for m in data.get("models", [])],
        }

    @retry(
        retry=retry_if_exception_type(OllamaError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> tuple[str, float]:
        """Single-turn generation using /api/generate. Returns (text, latency_ms)."""
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        start = time.perf_counter()
        result = await self._post("/api/generate", payload)
        latency = (time.perf_counter() - start) * 1000
        return result.get("response", ""), latency

    @retry(
        retry=retry_if_exception_type(OllamaError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> tuple[str, float]:
        """Multi-turn chat using /api/chat. Returns (assistant_text, latency_ms)."""
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        start = time.perf_counter()
        result = await self._post("/api/chat", payload)
        latency = (time.perf_counter() - start) * 1000
        message = result.get("message", {}) or {}
        return message.get("content", ""), latency
