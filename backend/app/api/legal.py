"""
Legal API v2 — Kanoon Sakhi
Thin SSE wrapper. All logic delegated to LangGraph graph.
"""
import json
import time
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from collections import deque
from datetime import datetime

from app.database.connection import get_db
from app.session.session_manager import (
    get_session_with_history, save_message,
    get_conversation_history
)
from app.kanoon.graph import run_kanoon_graph
from app.runtime_config import get_config
import psutil

router = APIRouter()
LOG = logging.getLogger("strisakhi")
EVENT_LOG: deque = deque(maxlen=200)


def log_event(level: str, event_type: str, session_id: str = "", **kwargs):
    ts = datetime.now().strftime("%H:%M:%S")
    detail = " ".join(f"{k}={v}" for k, v in kwargs.items())
    icons = {
        "INTAKE": "🔍", "EXPERT": "⚡", "EMERGENCY": "🚨",
        "FOLLOWUP": "💬", "RAG": "📚", "ROUTE": "🔀",
        "PHASE": "→", "DONE": "✅", "ERROR": "❌",
        "EMERGENCY_CHECK": "🛡️", "PARAM": "📝",
    }
    icon = icons.get(event_type, "•")
    print(f"{icon} {ts} [{event_type}] {session_id[:8]} {detail}", flush=True)
    EVENT_LOG.append({
        "ts": ts, "level": level, "type": event_type,
        "session": session_id[:8] if session_id else "",
        "detail": {**kwargs},
    })


class ChatRequest(BaseModel):
    session_id: str
    message: str
    input_type: Optional[str] = "text"
    language: Optional[str] = "hi"


def _get_metadata(session_data: dict) -> dict:
    meta = (
        session_data.get("metadata") or
        session_data.get("metadata_json") or {}
    )
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    return meta or {}


@router.post("/chat")
async def legal_chat(req: ChatRequest, db: Session = Depends(get_db)):
    session_data = get_session_with_history(db, req.session_id)
    if not session_data:
        raise HTTPException(404, f"Session {req.session_id} not found")

    language = req.language or "hi"
    cfg = get_config()
    max_turns = cfg.get("intake_max_turns", 10)
    emergency_enabled = cfg.get("emergency_check_enabled", True)
    metadata = _get_metadata(session_data)

    log_event("INFO", "ROUTE", req.session_id,
              phase=metadata.get("phase", "intake"),
              lang=language,
              msg=req.message[:40])

    # Save user message
    save_message(db, req.session_id, "user", req.message, req.input_type,
                 agent_used=metadata.get("phase", "intake"))

    history = get_conversation_history(db, req.session_id)

    return StreamingResponse(
        _sse_stream(
            session_id=req.session_id,
            user_message=req.message,
            language=language,
            history=history,
            metadata=metadata,
            db=db,
            emergency_enabled=emergency_enabled,
            max_turns=max_turns,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _sse_stream(
    session_id, user_message, language, history,
    metadata, db, emergency_enabled, max_turns
):
    start = time.time()
    full_response = ""
    citations = []
    agent_used = "intake"
    follow_ups = []

    mem = psutil.virtual_memory()
    yield f"data: {json.dumps({'type': 'metrics', 'ram_used_gb': round(mem.used/(1024**3), 2), 'ram_percent': mem.percent})}\n\n"

    try:
        async for event in run_kanoon_graph(
            session_id=session_id,
            user_message=user_message,
            language=language,
            history=history,
            existing_metadata=metadata,
            db=db,
            emergency_enabled=emergency_enabled,
            max_turns=max_turns,
        ):
            event_type = event.get("type", "")

            if event_type == "token":
                full_response += event.get("token", "")
                agent_used = event.get("agent", agent_used)
                yield f"data: {json.dumps(event)}\n\n"

            elif event_type == "citations":
                citations = event.get("citations", [])
                yield f"data: {json.dumps(event)}\n\n"

            elif event_type == "done":
                full_response = event.get("full_response", full_response)
                citations = event.get("citations", citations)
                follow_ups = event.get("follow_up_questions", [])
                agent_used = event.get("agent", agent_used)

                response_ms = int((time.time() - start) * 1000)
                log_event("INFO", "DONE", session_id,
                          agent=agent_used,
                          words=len(full_response.split()),
                          ms=response_ms,
                          followups=len(follow_ups))

                yield f"data: {json.dumps({**event, 'response_ms': response_ms})}\n\n"

            elif event_type in ("emergency", "phase_change", "metadata_update",
                                "routing", "processing"):
                if event_type == "emergency":
                    log_event("WARN", "EMERGENCY", session_id, action="overlay")
                elif event_type == "phase_change":
                    log_event("INFO", "PHASE", session_id,
                              from_phase=event.get("from"), to_phase=event.get("to"))
                elif event_type == "metadata_update":
                    log_event("INFO", "PARAM", session_id,
                              score=event.get("confidence_score", 0),
                              crime=event.get("crime_type", "?"))
                yield f"data: {json.dumps(event)}\n\n"

            elif event_type == "error":
                log_event("ERROR", "ERROR", session_id, msg=event.get("message", ""))
                yield f"data: {json.dumps(event)}\n\n"

    except Exception as e:
        log_event("ERROR", "ERROR", session_id, msg=str(e))
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


@router.get("/test")
async def legal_test():
    return {"status": "Kanoon Sakhi v2 (LangGraph) ready"}
