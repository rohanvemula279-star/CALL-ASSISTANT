"""Telegram bot notifier.

Plain HTTP calls to the Bot API — no extra dependency, no rate-limit
overhead beyond what Telegram imposes. Used by the missed-call
processing service to push a notification to the user.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

import httpx
import structlog

from app.config import Settings

log = structlog.get_logger(__name__)


class TelegramError(Exception):
    """Telegram call failed (network or non-2xx)."""


class TelegramNotifier:
    """Thin async wrapper around the Telegram Bot API.

    Two config knobs (env):
      - TELEGRAM_BOT_TOKEN
      - TELEGRAM_CHAT_ID
    Both are required to send. If either is missing the notifier becomes
    a no-op so the rest of the system keeps working.
    """

    API = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self, settings: Settings) -> None:
        self.token: Optional[str] = settings.telegram_bot_token or None
        self.chat_id: Optional[str] = settings.telegram_chat_id or None
        self.timeout = settings.telegram_timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def startup(self) -> None:
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    async def _post(self, method: str, payload: dict[str, Any]) -> dict:
        if self._client is None:
            raise TelegramError("Client not started")
        if not self.token:
            raise TelegramError("TELEGRAM_BOT_TOKEN not set")
        url = self.API.format(token=self.token, method=method)
        try:
            r = await self._client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as e:
            raise TelegramError(f"telegram http error: {e}") from e
        if not data.get("ok"):
            raise TelegramError(
                f"telegram returned not-ok: {json.dumps(data)[:300]}"
            )
        return data

    async def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        disable_notification: bool = False,
        chat_id: Optional[str] = None,
        reply_markup: Optional[dict] = None,
    ) -> dict:
        """Send a text message. Returns the API response."""
        target = chat_id or self.chat_id
        if not target:
            raise TelegramError("TELEGRAM_CHAT_ID not set")
        payload: dict = {
            "chat_id": target,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": disable_notification,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return await self._post("sendMessage", payload)

    async def send_missed_call(
        self,
        number: str,
        name: Optional[str],
        timestamp_ms: int,
        summary: Optional[str],
        call_id: str,
        previous_call_count: int = 0,
        contact_exists: bool = False,
        voicemail: bool = False,
        callback_id: Optional[int] = None,
        base_url: Optional[str] = None,
    ) -> dict:
        """Send a missed-call notification with inline action buttons.

        The body deliberately doesn't hallucinate a reason. If no voicemail
        transcript is supplied, the message says so explicitly.

        Buttons (when a callback_id is provided):
            Call Back  |  Send SMS  |  Mark Done
        Plus a "Open dashboard" URL button.
        """
        from datetime import datetime, timezone

        ts = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        local = ts.astimezone()
        time_str = local.strftime("%I:%M %p").lstrip("0")
        display_name = (name or "Unknown").strip() or "Unknown"

        parts = [
            "📞 <b>Missed Call</b>\n",
            f"<b>Name:</b> {self._escape(display_name)}",
            f"<b>Number:</b> {self._escape(number)}",
            f"<b>Time:</b> {self._escape(time_str)}",
            "",
            f"<b>Contact exists:</b> {'Yes' if contact_exists else 'No'}",
            f"<b>Previous calls:</b> {previous_call_count}",
        ]

        if voicemail and summary:
            parts.append("")
            parts.append("<b>📝 Voicemail summary:</b>")
            parts.append(self._escape(summary.strip()))
        else:
            parts.append("")
            parts.append("<i>Caller did not leave a message.</i>")

        parts.append("")
        parts.append(f"<code>call_id: {self._escape(call_id)}</code>")

        reply_markup: Optional[dict] = None
        if callback_id is not None:
            reply_markup = {
                "inline_keyboard": [
                    [
                        {"text": "📞 Call Back", "callback_data": f"cb:callback:{callback_id}"},
                        {"text": "💬 Send SMS", "callback_data": f"cb:sms:{callback_id}"},
                        {"text": "✅ Mark Done", "callback_data": f"cb:done:{callback_id}"},
                    ]
                ]
            }
            if base_url:
                reply_markup["inline_keyboard"].append(
                    [{"text": "🌐 Open dashboard",
                      "url": f"{base_url.rstrip('/')}/dashboard"}]
                )

        return await self.send_message(
            "\n".join(parts),
            reply_markup=reply_markup,
        )

    async def edit_message(
        self,
        message_id: int,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "HTML",
        reply_markup: Optional[dict] = None,
    ) -> dict:
        """Edit a previously sent message (used to update button labels)."""
        target = chat_id or self.chat_id
        if not target:
            raise TelegramError("TELEGRAM_CHAT_ID not set")
        payload: dict = {
            "chat_id": target,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return await self._post("editMessageText", payload)

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str = "",
        show_alert: bool = False,
    ) -> dict:
        """Acknowledge a button press (removes the loading spinner)."""
        return await self._post(
            "answerCallbackQuery",
            {
                "callback_query_id": callback_query_id,
                "text": text,
                "show_alert": show_alert,
            },
        )

    @staticmethod
    def _escape(text: str) -> str:
        """Escape for HTML parse_mode."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
