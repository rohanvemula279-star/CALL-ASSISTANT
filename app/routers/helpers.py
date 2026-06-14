"""Contact-name lookup + LAN-discovery helper endpoints.

These complement the Android client:

  * GET /contacts/lookup?phone=...&provider=android
        Returns the name a "trusted" source (the Android phone, if
        reachable) can resolve. Useful for the *server* to enrich
        notifications if the Android client didn't send a name (older
        builds, permission-denied, etc.).

  * GET /network/info
        Returns the host's IP addresses so the Android app can auto-
        detect the laptop on the LAN (e.g. when the user runs the app
        on a fresh install and doesn't know the URL).
"""

from __future__ import annotations

import asyncio
import socket
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.dependencies import get_telegram
from app.logger import get_logger
from app.services.telegram_notifier import TelegramError, TelegramNotifier

router = APIRouter(prefix="", tags=["helpers"])
log = get_logger(__name__)


@router.get("/network/info")
async def network_info() -> dict:
    """LAN IPs, port, and the full base URL the Android app should use."""
    settings = get_settings()
    port = settings.app_port
    ips: list[str] = []
    try:
        # Use a UDP socket to a public IP so the kernel picks the
        # outbound interface. No packets are actually sent.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
    except Exception:  # noqa: BLE001
        pass

    try:
        hostname_ips = {
            info[4][0]
            for info in socket.getaddrinfo(socket.gethostname(), None)
            if info and len(info) >= 5 and isinstance(info[4][0], str)
        }
        ips.extend(hostname_ips)
    except Exception:  # noqa: BLE001
        pass

    # Dedupe while preserving order
    seen: set[str] = set()
    unique = []
    for ip in ips:
        if ip and ip not in seen:
            seen.add(ip)
            unique.append(ip)

    base_urls = [f"http://{ip}:{port}" for ip in unique]
    return {
        "host": socket.gethostname(),
        "ips": unique,
        "port": port,
        "base_urls": base_urls,
        "recommended": base_urls[0] if base_urls else None,
    }


@router.get("/contacts/lookup")
async def contacts_lookup(
    phone: str = Query(..., min_length=3),
    provider: str = Query("offline", pattern="^(offline|android|libphonenumber)$"),
) -> dict:
    """Resolve a phone number to a contact name.

    * provider=offline (default) — only does basic normalization
    * provider=android — would query a paired Android device; the
      actual call-out is performed by the Android app posting to
      /contacts/resolve, not by the server
    * provider=libphonenumber — would use a phone-region inference
      (left as a hook for a future PR; not in default deps)

    Always returns `{"phone": "...", "name": null|str, "provider": ...}`.
    """
    if provider == "android":
        # In this architecture the Android app resolves names before
        # posting to /incoming-call, so server-side lookup is a no-op.
        # This branch is a hook for an "Android as a server" alternative
        # where the laptop queries the phone over LAN.
        return {"phone": phone, "name": None, "provider": "android"}
    return {"phone": phone, "name": None, "provider": "offline"}


@router.post("/telegram/test")
async def telegram_test(message: str = "✅ Telegram integration is working."):
    """Send a test message using the configured bot. For setup verification."""
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set. "
                "Create a bot via @BotFather, then add the chat id."
            ),
        )
    telegram: TelegramNotifier = get_telegram()
    try:
        resp = await telegram.send_message(message)
        return {"ok": True, "message_id": (resp.get("result") or {}).get("message_id")}
    except TelegramError as e:
        raise HTTPException(status_code=502, detail=str(e))
