from __future__ import annotations

import time
from typing import Optional

import httpx
import structlog
from livekit import api

from app.config import Settings

log = structlog.get_logger(__name__)

GREETING_TEXT = (
    "Hi, Rohan is currently busy. Please leave a message after the beep, "
    "and he will get back to you as soon as possible."
)


class LiveKitService:
    def __init__(self, settings: Settings) -> None:
        self.url = settings.livekit_url
        self.api_key = settings.livekit_api_key
        self.api_secret = settings.livekit_api_secret
        self.enabled = bool(self.url and self.api_key and self.api_secret)
        self._client: Optional[httpx.AsyncClient] = None

    async def startup(self) -> None:
        if not self.enabled:
            log.info("livekit.disabled")
            return
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(30))
        log.info("livekit.ready", url=self.url)

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def create_token(self, room_name: str, identity: str = "assistant") -> str:
        token = api.AccessToken(self.api_key, self.api_secret)
        token.identity = identity
        token.add_grant(room_join=True, room=room_name)
        token.ttl = time.time() + 3600
        return token.to_jwt()

    async def create_room(self, room_name: str) -> dict:
        if not self.enabled:
            return {"room": room_name, "enabled": False}
        try:
            livekit_api = api.LiveKitAPI(
                url=self.url,
                api_key=self.api_key,
                api_secret=self.api_secret,
            )
            room = await livekit_api.room.create_room(
                api.CreateRoomRequest(name=room_name)
            )
            await livekit_api.aclose()
            return {"room": room.name, "sid": room.sid}
        except Exception as e:
            log.warning("livekit.create_room_failed", room=room_name, error=str(e))
            return {"room": room_name, "error": str(e)}
