"""
Admin API — backend/app/api/admin.py
Settings + live event log endpoints.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.runtime_config import get_config, save_config

router = APIRouter()
ADMIN_PIN = "1234"


class SettingsRequest(BaseModel):
    pin: str
    tts_speed_hi: Optional[float] = None
    tts_speed_en: Optional[float] = None
    intake_max_turns: Optional[int] = None
    intake_min_score: Optional[int] = None
    temperature: Optional[float] = None
    expert_max_tokens: Optional[int] = None


@router.get("/settings")
async def get_settings():
    return get_config()


@router.post("/settings")
async def save_settings(req: SettingsRequest):
    if req.pin != ADMIN_PIN:
        raise HTTPException(403, "Wrong PIN")
    updates = {k: v for k, v in req.dict().items()
               if k != "pin" and v is not None}
    return save_config(updates)


@router.get("/logs")
async def get_logs(limit: int = 100):
    """Return recent events from the in-memory log buffer."""
    try:
        from app.api.legal import EVENT_LOG
        events = list(EVENT_LOG)[-limit:]
        return {"events": events, "total": len(EVENT_LOG)}
    except Exception as e:
        return {"events": [], "total": 0, "error": str(e)}


@router.get("/session/{session_id}")
async def get_session_debug(session_id: str):
    """Return live session state for debugging."""
    try:
        from app.database.connection import SessionLocal
        from app.session.session_manager import get_session_with_history
        db = SessionLocal()
        session = get_session_with_history(db, session_id)
        db.close()
        if not session:
            raise HTTPException(404, "Session not found")
        return {
            "session_id": session_id,
            "phase": session.get("agent_phase"),
            "metadata": session.get("metadata") or session.get("metadata_json"),
            "confidence_score": session.get("confidence_score"),
            "emergency_flagged": session.get("emergency_flagged"),
            "message_count": len(session.get("history", [])),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
