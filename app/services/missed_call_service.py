"""Missed-call processing service.

Glues the existing pieces together:
  - Persists the event to the conversation store
  - Computes prior-history stats (count, contact-known)
  - If a voicemail transcript is supplied, asks Ollama for a summary
  - Creates a callback row
  - Sends a Telegram notification (with action buttons)
  - Returns a structured response to the caller (the Android app)

The router is thin; this service holds the business logic.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Optional

import structlog

from app.config import Settings
from app.services.ollama_client import OllamaClient, OllamaError
from app.services.piper_service import PiperError, PiperService
from app.services.telegram_notifier import TelegramError, TelegramNotifier
from app.storage.store import ConversationStore

log = structlog.get_logger(__name__)


SUMMARY_SYSTEM = (
    "You are a helpful personal assistant. Given a voicemail transcript, "
    "write a 1-2 sentence plain-text summary of what the caller said, and "
    "an inferred reason for the call. Be conservative. No emojis, no markdown."
)


@dataclass
class IncomingCallEvent:
    number: str
    name: Optional[str]
    timestamp_ms: int
    call_id: str
    device: Optional[str] = None
    voicemail_transcript: Optional[str] = None
    context: Optional[dict] = None


@dataclass
class MissedCallResult:
    ok: bool
    message: str
    reply_text: Optional[str] = None
    reply_audio_url: Optional[str] = None
    call_id: str = ""
    callback_id: Optional[int] = None
    telegram: Optional[dict] = None
    summary: Optional[str] = None
    contact_exists: bool = False
    previous_call_count: int = 0
    voicemail: bool = False


class MissedCallService:
    """Coordinates everything that happens when a missed call is reported."""

    def __init__(
        self,
        settings: Settings,
        store: ConversationStore,
        ollama: OllamaClient,
        piper: PiperService,
        telegram: TelegramNotifier,
    ) -> None:
        self.settings = settings
        self.store = store
        self.ollama = ollama
        self.piper = piper
        self.telegram = telegram

    async def handle(self, event: IncomingCallEvent) -> MissedCallResult:
        log.info(
            "missed_call.received",
            number=event.number,
            name=event.name,
            call_id=event.call_id,
            has_voicemail=bool(event.voicemail_transcript),
        )

        # 1) Compute prior-history stats before we insert this row
        prior_count = await self.store.caller_call_count(event.number)
        contact_exists = bool((event.name or "").strip()) and prior_count > 0
        has_voicemail = bool((event.voicemail_transcript or "").strip())

        # 2) Persist the missed-call event
        try:
            await self.store.add(
                role="system",
                content=(
                    f"Missed call from {event.name or 'unknown'} "
                    f"({event.number}) at {event.timestamp_ms}"
                    + (" (with voicemail)" if has_voicemail else "")
                ),
                call_id=event.call_id,
                caller=event.number,
                metadata={
                    "event": "missed_call",
                    "device": event.device,
                    "voicemail": has_voicemail,
                },
            )
        except Exception as e:  # noqa: BLE001
            log.warning("missed_call.store_failed", error=str(e))

        # 3) Summary via Ollama — ONLY when a voicemail exists
        summary: Optional[str] = None
        if has_voicemail:
            try:
                prompt = self._build_voicemail_prompt(event)
                summary, _ = await self.ollama.generate(
                    prompt=prompt,
                    system=SUMMARY_SYSTEM,
                    temperature=0.4,
                    max_tokens=140,
                )
                summary = (summary or "").strip() or None
            except OllamaError as e:
                log.warning("missed_call.ollama_failed", error=str(e))

        # 4) Persist the voicemail summary (if any)
        if summary:
            try:
                await self.store.add(
                    role="assistant",
                    content=f"Voicemail summary: {summary}",
                    call_id=event.call_id,
                    caller=event.number,
                )
            except Exception as e:  # noqa: BLE001
                log.warning("missed_call.summary_persist_failed", error=str(e))

        # 5) TTS of the summary (optional)
        audio_url: Optional[str] = None
        if summary and self.piper.is_ready():
            try:
                tts = await self.piper.synthesize(summary)
                audio_url = tts["audio_url"]
            except PiperError as e:
                log.warning("missed_call.piper_failed", error=str(e))

        # 6) Create a callback row so the user can mark done / track it
        callback_id: Optional[int] = None
        try:
            callback_id = await self.store.create_callback(
                call_id=event.call_id,
                caller=event.number,
                caller_name=event.name,
                action="callback",
            )
        except Exception as e:  # noqa: BLE001
            log.warning("missed_call.callback_create_failed", error=str(e))

        # 7) Telegram notification (best-effort)
        telegram_info: Optional[dict] = None
        if self.telegram.enabled:
            try:
                resp = await self.telegram.send_missed_call(
                    number=event.number,
                    name=event.name,
                    timestamp_ms=event.timestamp_ms,
                    summary=summary,
                    call_id=event.call_id,
                    previous_call_count=prior_count,
                    contact_exists=contact_exists,
                    voicemail=has_voicemail,
                    callback_id=callback_id,
                    base_url=self.settings.base_url,
                )
                telegram_info = {
                    "sent": True,
                    "message_id": (resp.get("result") or {}).get("message_id"),
                }
            except TelegramError as e:
                log.warning("missed_call.telegram_failed", error=str(e))
                telegram_info = {"sent": False, "error": str(e)}
        else:
            log.debug("missed_call.telegram_disabled")

        return MissedCallResult(
            ok=True,
            message="processed",
            reply_text=summary,
            reply_audio_url=audio_url,
            call_id=event.call_id,
            callback_id=callback_id,
            telegram=telegram_info,
            summary=summary,
            contact_exists=contact_exists,
            previous_call_count=prior_count,
            voicemail=has_voicemail,
        )

    def _build_voicemail_prompt(self, event: IncomingCallEvent) -> str:
        from datetime import datetime, timezone

        ts = datetime.fromtimestamp(event.timestamp_ms / 1000, tz=timezone.utc)
        local = ts.astimezone()
        human_time = local.strftime("%A %I:%M %p")

        parts = [
            f"Caller: {event.name or 'Unknown'} ({event.number})",
            f"Time: {human_time}",
            "",
            "Voicemail transcript:",
            event.voicemail_transcript or "(empty)",
        ]
        return "\n".join(parts)
