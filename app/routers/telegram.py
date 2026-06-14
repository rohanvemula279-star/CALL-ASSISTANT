"""Telegram webhook handler.

Receives `callback_query` updates (button presses) and:
  * updates the callback row's status
  * edits the original message to reflect the change
  * acknowledges the press

The webhook URL is what you give @BotFather as the allowed update source.
The server is started in polling-less mode (no long-poll) — you set
`webhook_url` in config and we tell Telegram to use it once on startup.

For local development, you can also call [POST /telegram/simulate/cb]
with a fake callback payload.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import get_settings
from app.dependencies import get_store, get_telegram
from app.logger import get_logger
from app.services.telegram_notifier import TelegramError, TelegramNotifier
from app.storage.store import ConversationStore

router = APIRouter(prefix="/telegram", tags=["telegram"])
log = get_logger(__name__)


# Map from the button's callback_data to a human label
ACTION_LABELS = {
    "callback": "Calling back…",
    "sms": "SMS sent",
    "done": "Marked done ✅",
    "dismiss": "Dismissed",
    "reopen": "Re-opened",
}


def _parse_callback_data(data: str) -> tuple[str, int]:
    """Parse `cb:<action>:<id>` -> (action, id)."""
    parts = (data or "").split(":")
    if len(parts) != 3 or parts[0] != "cb":
        raise ValueError("unrecognized callback_data")
    action, cb_id = parts[1], parts[2]
    if action not in ACTION_LABELS:
        raise ValueError(f"unknown action: {action}")
    return action, int(cb_id)


@router.post("/webhook")
async def telegram_webhook(update: dict[str, Any]) -> dict:
    """Entry point Telegram calls when a user presses a button."""
    log.info("telegram.webhook", update=update)

    if "callback_query" not in update:
        return {"ok": True, "ignored": True}

    cb_query = update["callback_query"]
    query_id: str = cb_query.get("id", "")
    data: str = cb_query.get("data", "")
    message = cb_query.get("message") or {}
    message_id: Optional[int] = message.get("message_id")
    chat_id: Optional[str] = (
        (message.get("chat") or {}).get("id")
        if isinstance(message.get("chat"), dict) else None
    )
    inline_message_id: Optional[str] = cb_query.get("inline_message_id")

    telegram: TelegramNotifier = get_telegram()
    try:
        action, callback_id = _parse_callback_data(data)
    except ValueError as e:
        await telegram.answer_callback_query(query_id, f"Bad button: {e}", show_alert=True)
        return {"ok": False, "error": str(e)}

    store: ConversationStore = get_store()
    cb = await store.get_callback(callback_id)
    if cb is None:
        await telegram.answer_callback_query(query_id, "Already removed.", show_alert=True)
        return {"ok": False, "error": "callback not found"}

    # Map action to status
    action_to_status = {
        "callback": "in_progress",
        "sms": "in_progress",
        "done": "completed",
        "dismiss": "dismissed",
        "reopen": "pending",
    }
    new_status = action_to_status[action]
    if cb["status"] == "completed" and action in ("callback", "sms"):
        await telegram.answer_callback_query(
            query_id, "Already completed — reopen first.", show_alert=True
        )
        return {"ok": False, "error": "already completed"}
    await store.update_callback(callback_id, status=new_status)

    # Acknowledge the press (removes the spinner)
    try:
        await telegram.answer_callback_query(query_id, ACTION_LABELS.get(action, ""))
    except TelegramError as e:
        log.warning("telegram.ack_failed", error=str(e))

    # Edit the original message to reflect the new state — strip the buttons
    # from the action row to avoid double-pressing, and append a status line.
    if message_id is not None and chat_id is not None:
        try:
            original_text = message.get("text", "")
            status_line = f"\n\n<i>Status: {new_status.replace('_', ' ')}</i>"
            await telegram.edit_message(
                message_id=message_id,
                text=original_text + status_line,
                chat_id=str(chat_id),
                reply_markup={"inline_keyboard": []},
            )
        except TelegramError as e:
            log.warning("telegram.edit_failed", error=str(e))
    elif inline_message_id is not None:
        # Less common; older clients send it without chat/message
        log.debug("telegram.webhook.inline_only", id=inline_message_id)

    log.info(
        "telegram.callback_processed",
        action=action,
        callback_id=callback_id,
        new_status=new_status,
    )
    return {"ok": True, "action": action, "callback_id": callback_id, "status": new_status}


class SimulateCallbackRequest(BaseModel):
    action: str
    callback_id: int


@router.post("/simulate/cb")
async def simulate_callback(body: SimulateCallbackRequest) -> dict:
    """Local-dev helper: feed a fake callback_query into the handler."""
    payload = {
        "id": "simulated",
        "from": {"id": 0, "first_name": "sim"},
        "data": f"cb:{body.action}:{body.callback_id}",
        "message": {
            "message_id": 0,
            "chat": {"id": 0},
            "text": "(simulated)",
        },
    }
    return await telegram_webhook(payload)


@router.post("/set_webhook")
async def set_webhook() -> dict:
    """Register `BASE_URL/telegram/webhook` with Telegram."""
    settings = get_settings()
    telegram: TelegramNotifier = get_telegram()
    if not telegram.enabled:
        raise HTTPException(
            status_code=400,
            detail="Telegram not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing)",
        )
    url = f"{settings.base_url.rstrip('/')}/telegram/webhook"
    try:
        resp = await telegram._post("setWebhook", {"url": url})  # noqa: SLF001
        return {"ok": True, "url": url, "telegram": resp}
    except TelegramError as e:
        raise HTTPException(status_code=502, detail=str(e))
