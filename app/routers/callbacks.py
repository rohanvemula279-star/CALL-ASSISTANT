"""Callback action endpoints.

The Telegram message contains three buttons:
    Call Back | Send SMS | Mark Done
Each button is encoded as a `callback_data` payload of the form
`cb:<action>:<callback_id>`. The Telegram webhook (see routers/telegram.py)
forwards those to update_callback() with the right status.

This router exposes the same operations as a clean REST surface so that
the dashboard, an iOS client, or curl can drive the same state machine.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.dependencies import get_store
from app.logger import get_logger
from app.storage.store import ConversationStore

router = APIRouter(prefix="", tags=["callbacks"])
log = get_logger(__name__)


VALID_ACTIONS = {"callback", "sms", "done", "dismiss", "reopen"}


class CallbackActionRequest(BaseModel):
    action: str = Field(..., pattern="^(callback|sms|done|dismiss|reopen)$")
    note: Optional[str] = None


class CallbackResponse(BaseModel):
    id: int
    call_id: str
    caller: str
    caller_name: Optional[str] = None
    status: str
    action: Optional[str] = None
    note: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@router.post("/callback/{callback_id}", response_model=CallbackResponse)
async def post_callback_action(
    callback_id: int, body: CallbackActionRequest
) -> CallbackResponse:
    """Update a callback's status (call-back / sms / done / dismiss / reopen)."""
    store: ConversationStore = get_store()
    cb = await store.get_callback(callback_id)
    if cb is None:
        raise HTTPException(status_code=404, detail="callback not found")

    # Map action -> status
    action_to_status = {
        "callback": "in_progress",
        "sms": "in_progress",
        "done": "completed",
        "dismiss": "dismissed",
        "reopen": "pending",
    }
    new_status = action_to_status[body.action]

    # Don't downgrade a completed callback via "callback" or "sms"
    if cb["status"] == "completed" and body.action in ("callback", "sms"):
        raise HTTPException(
            status_code=409,
            detail="callback already completed; reopen it first",
        )

    ok = await store.update_callback(
        callback_id, status=new_status, note=body.note
    )
    if not ok:
        raise HTTPException(status_code=500, detail="update failed")

    cb = await store.get_callback(callback_id)
    log.info("callback.updated", id=callback_id, action=body.action, status=new_status)
    return _to_response(cb)


@router.get("/callbacks", response_model=list[CallbackResponse])
async def list_callbacks(
    status: Optional[str] = None,
    limit: int = 100,
) -> list[CallbackResponse]:
    store: ConversationStore = get_store()
    if limit <= 0 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be 1..500")
    if status and status not in ("pending", "in_progress", "completed", "dismissed"):
        raise HTTPException(status_code=400, detail="invalid status")
    rows = await store.list_callbacks(status=status, limit=limit)
    return [_to_response(r) for r in rows]


@router.get("/callbacks/{callback_id}", response_model=CallbackResponse)
async def get_callback(callback_id: int) -> CallbackResponse:
    store: ConversationStore = get_store()
    cb = await store.get_callback(callback_id)
    if cb is None:
        raise HTTPException(status_code=404, detail="callback not found")
    return _to_response(cb)


@router.delete("/callbacks/{callback_id}")
async def delete_callback(callback_id: int) -> dict:
    """No-op compatibility endpoint — mark dismissed instead of removing."""
    store: ConversationStore = get_store()
    cb = await store.get_callback(callback_id)
    if cb is None:
        raise HTTPException(status_code=404, detail="callback not found")
    await store.update_callback(callback_id, status="dismissed")
    return {"ok": True, "id": callback_id, "status": "dismissed"}


def _to_response(cb: dict) -> CallbackResponse:
    return CallbackResponse(
        id=cb["id"],
        call_id=cb["call_id"],
        caller=cb["caller"],
        caller_name=cb.get("caller_name"),
        status=cb["status"],
        action=cb.get("action"),
        note=cb.get("note"),
        created_at=cb["created_at"].isoformat() if cb.get("created_at") else None,
        updated_at=cb["updated_at"].isoformat() if cb.get("updated_at") else None,
    )
