"""
Scheme (Yojana) API — StriSakhi
Government schemes guidance for Indian women.
Reuses legal pipeline with scheme-specific prompts.
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
from app.agents.model_router import route, calculate_confidence, RouteDecision, INTAKE_MAX_TURNS
from app.agents.scheme_agent import run_scheme_expert_stream
from app.agents.intake_agent import run_intake_stream
from app.emergency.detector import detect_emergency, get_emergency_response
from app.utils.language_detect import detect_language
import psutil

router = APIRouter()

class ChatRequest(BaseModel):
    session_id: str
    message: str
    input_type: Optional[str] = "text"

@router.post("/chat")
async def scheme_chat(req: ChatRequest, db: Session = Depends(get_db)):
    session_data = get_session_with_history(db, req.session_id)
    if not session_data:
        raise HTTPException(404, f"Session {req.session_id} not found")

    language = detect_language(req.message)
    is_emergency, emergency_type, severity = detect_emergency(req.message, "legal")
    if is_emergency and severity == "critical":
        flag_emergency(db, req.session_id)
        save_message(db, req.session_id, "user", req.message, req.input_type)
        emergency_data = get_emergency_response(emergency_type, "legal", language)
        async def emergency_stream():
            yield f"data: {json.dumps({'type': 'emergency', 'data': emergency_data})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return StreamingResponse(emergency_stream(), media_type="text/event-stream")

    save_message(db, req.session_id, "user", req.message, req.input_type,
                 agent_used=session_data["agent_phase"])
    history = get_conversation_history(db, req.session_id)
    user_turn_count = sum(1 for m in history if m.get("role") == "user")
    metadata = session_data.get("metadata", {})

    if user_turn_count >= INTAKE_MAX_TURNS and session_data["agent_phase"] == "intake":
        update_session_phase(db, req.session_id, "expert")
        session_data["agent_phase"] = "expert"

    decision, model_name, reason = route(
        agent_phase=session_data["agent_phase"],
        confidence_score=session_data["confidence_score"],
        emergency_flagged=session_data["emergency_flagged"],
        metadata=metadata,
        tab_type="legal",
        user_turn_count=user_turn_count
    )

    return StreamingResponse(
        _scheme_stream_generator(
            db, req.session_id, req.message,
            decision, metadata, history, language,
            session_data, model_name, reason
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

async def _scheme_stream_generator(
    db, session_id, message,
    decision, metadata, history, language,
    session_data, model_name, reason
):
    start_time = time.time()
    full_response = ""
    citations = []
    agent_used = decision.value

    yield f"data: {json.dumps({'type': 'routing', 'decision': decision.value, 'model': model_name, 'reason': reason})}\n\n"
    mem = psutil.virtual_memory()
    yield f"data: {json.dumps({'type': 'metrics', 'ram_used_gb': round(mem.used/(1024**3), 2), 'ram_percent': mem.percent, 'model': model_name})}\n\n"

    if decision == RouteDecision.INTAKE:
        async for event in run_intake_stream(history, metadata, "scheme", language):
            if event["type"] == "token":
                full_response += event["token"]
                yield f"data: {json.dumps(event)}\n\n"
            elif event["type"] == "metadata_update":
                update_session_metadata(db, session_id, event["metadata"])
                crud.update_session(db, session_id, confidence_score=event["confidence_score"])
                yield f"data: {json.dumps({'type': 'metadata_update', 'confidence_score': event['confidence_score'], 'metadata': event['metadata']})}\n\n"
            elif event["type"] == "phase_change":
                update_session_phase(db, session_id, "expert")
                yield f"data: {json.dumps({'type': 'phase_change', 'from': 'intake', 'to': 'expert'})}\n\n"
            elif event["type"] == "error":
                yield f"data: {json.dumps({'type': 'error', 'message': event['message']})}\n\n"
                return

    elif decision == RouteDecision.EXPERT:
        if session_data["agent_phase"] != "expert":
            update_session_phase(db, session_id, "expert")
        async for event in run_scheme_expert_stream(metadata, history, language):
            if event["type"] == "token":
                full_response += event["token"]
                yield f"data: {json.dumps(event)}\n\n"
            elif event["type"] == "rag_retrieved":
                citations = event.get("citations", [])
                yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
            elif event["type"] == "error":
                yield f"data: {json.dumps({'type': 'error', 'message': event['message']})}\n\n"
                return

    response_ms = int((time.time() - start_time) * 1000)
    save_message(db, session_id, "assistant", full_response,
                 citations=citations, agent_used=agent_used, response_ms=response_ms)

    yield f"data: {json.dumps({'type': 'done', 'full_response': full_response, 'citations': citations, 'response_ms': response_ms, 'agent': agent_used})}\n\n"

@router.get("/test")
async def scheme_test():
    return {"status": "Scheme (Yojana) router working", "endpoints": ["/chat"]}
