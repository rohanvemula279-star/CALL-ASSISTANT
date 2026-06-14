"""Server-rendered dashboard for missed-call callbacks.

A small but practical UI:
  - summary tiles (total / pending / in-progress / completed)
  - table of recent callbacks with quick action buttons
  - no JavaScript framework required

Routes:
  GET  /dashboard           -> HTML
  GET  /dashboard/data      -> JSON for an external client
  POST /dashboard/action    -> form-encoded action; same shape as /callback
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import get_store
from app.logger import get_logger
from app.storage.store import ConversationStore

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
log = get_logger(__name__)


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "utils" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    status: Optional[str] = None,
) -> HTMLResponse:
    store: ConversationStore = get_store()
    if status and status not in ("pending", "in_progress", "completed", "dismissed"):
        raise HTTPException(status_code=400, detail="invalid status")
    rows = await store.list_callbacks(status=status, limit=200)
    stats = await store.callback_stats()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "rows": rows,
            "stats": stats,
            "status_filter": status or "all",
        },
    )


@router.get("/data")
async def dashboard_data(status: Optional[str] = None, limit: int = 200) -> dict:
    store: ConversationStore = get_store()
    if limit <= 0 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be 1..500")
    rows = await store.list_callbacks(status=status, limit=limit)
    stats = await store.callback_stats()
    return {
        "stats": stats,
        "items": [
            {
                "id": r["id"],
                "call_id": r["call_id"],
                "caller": r["caller"],
                "caller_name": r["caller_name"],
                "status": r["status"],
                "action": r["action"],
                "note": r["note"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in rows
        ],
    }


@router.post("/action")
async def dashboard_action(
    callback_id: int = Form(...),
    action: str = Form(...),
    note: Optional[str] = Form(None),
):
    """Form submission from the dashboard's action buttons."""
    from app.routers.callbacks import post_callback_action, CallbackActionRequest

    if action not in ("callback", "sms", "done", "dismiss", "reopen"):
        raise HTTPException(status_code=400, detail="invalid action")
    result = await post_callback_action(
        callback_id, CallbackActionRequest(action=action, note=note)
    )
    return JSONResponse({"ok": True, "callback": result.dict()})
