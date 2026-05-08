"""
Legal API — passes session language to all agents
"""
import json
import time
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.database.connection import get_db
from app.database import crud
from app.session.session_manager import (
    get_session_with_history, save_message,
    update_session_metadata, update_session_phase,
    flag_emergency, get_conversation_history
)
from app.agents.model_router import route, RouteDecision, INTAKE_MAX_TURNS
from app.agents.intake_agent import run_intake_stream
from app.agents.legal_agent import run_legal_expert_stream
from app.emergency.detector import detect_emergency, get_emergency_response
import psutil

router = APIRouter()

class ChatRequest(BaseModel):
    session_id: str
    message: str
    input_type: Optional[str] = "text"
    language: Optional[str] = "hi"  # session language from frontend

@router.post("/chat")
async def legal_chat(req: ChatRequest, db: Session = Depends(get_db)):
    session_data = get_session_with_history(db, req.session_id)
    if not session_data:
        raise HTTPException(404, f"Session {req.session_id} not found")

    language = req.language or "hi"

    is_emergency, emergency_type, severity = detect_emergency(req.message, "legal")
    if is_emergency and severity == "critical":
        flag_emergency(db, req.session_id)
        save_message(db, req.session_id, "user", req.message, req.input_type)
        emergency_data = get_emergency_response(emergency_type, "legal", language)
        async def es():
            yield f"data: {json.dumps({'type': 'emergency', 'data': emergency_data})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return StreamingResponse(es(), media_type="text/event-stream")

    save_message(db, req.session_id, "user", req.message, req.input_type,
                 agent_used=session_data["agent_phase"])
    history = get_conversation_history(db, req.session_id)
    user_turns = sum(1 for m in history if m.get("role") == "user")
    metadata = session_data.get("metadata", {})

    if user_turns >= INTAKE_MAX_TURNS and session_data["agent_phase"] == "intake":
        update_session_phase(db, req.session_id, "expert")
        session_data["agent_phase"] = "expert"

    decision, model_name, reason = route(
        agent_phase=session_data["agent_phase"],
        confidence_score=session_data["confidence_score"],
        emergency_flagged=session_data["emergency_flagged"],
        metadata=metadata,
        tab_type="legal",
        user_turn_count=user_turns
    )

    return StreamingResponse(
        _stream(db, req.session_id, req.message, decision, metadata,
                history, language, session_data, model_name, reason),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

async def _stream(db, session_id, message, decision, metadata,
                  history, language, session_data, model_name, reason):
    start = time.time()
    full_response = ""
    citations = []
    agent_used = decision.value

    yield f"data: {json.dumps({'type': 'routing', 'decision': decision.value, 'model': model_name, 'reason': reason})}\n\n"
    mem = psutil.virtual_memory()
    yield f"data: {json.dumps({'type': 'metrics', 'ram_used_gb': round(mem.used/(1024**3),2), 'ram_percent': mem.percent, 'model': model_name})}\n\n"

    if decision == RouteDecision.INTAKE:
        async for ev in run_intake_stream(history, metadata, "legal", language):
            if ev["type"] == "token":
                full_response += ev["token"]
                yield f"data: {json.dumps(ev)}\n\n"
            elif ev["type"] == "metadata_update":
                update_session_metadata(db, session_id, ev["metadata"])
                crud.update_session(db, session_id, confidence_score=ev["confidence_score"])
                yield f"data: {json.dumps({'type': 'metadata_update', 'confidence_score': ev['confidence_score']})}\n\n"
            elif ev["type"] == "phase_change":
                update_session_phase(db, session_id, "expert")
                yield f"data: {json.dumps({'type': 'phase_change', 'from': 'intake', 'to': 'expert'})}\n\n"
            elif ev["type"] == "emergency":
                flag_emergency(db, session_id)
                yield f"data: {json.dumps({'type': 'emergency'})}\n\n"
                return
            elif ev["type"] == "error":
                yield f"data: {json.dumps({'type': 'error', 'message': ev['message']})}\n\n"
                return

    elif decision == RouteDecision.EXPERT:
        if session_data["agent_phase"] != "expert":
            update_session_phase(db, session_id, "expert")
        async for ev in run_legal_expert_stream(metadata, history, language):
            if ev["type"] == "token":
                full_response += ev["token"]
                yield f"data: {json.dumps(ev)}\n\n"
            elif ev["type"] == "rag_retrieved":
                citations = ev.get("citations", [])
                yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
            elif ev["type"] == "error":
                yield f"data: {json.dumps({'type': 'error', 'message': ev['message']})}\n\n"
                return

    response_ms = int((time.time() - start) * 1000)
    save_message(db, session_id, "assistant", full_response,
                 citations=citations, agent_used=agent_used, response_ms=response_ms)
    yield f"data: {json.dumps({'type': 'done', 'full_response': full_response, 'citations': citations, 'response_ms': response_ms, 'agent': agent_used})}\n\n"

@router.get("/test")
async def legal_test():
    return {"status": "Legal router working"}
