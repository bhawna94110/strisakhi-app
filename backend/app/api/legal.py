"""
Legal API — StriSakhi Kanoon Sakhi
Clean state machine: INTAKE → EXPERT → FOLLOW_UP
LLM-based emergency detection on every message.
Structured logging for admin dashboard and debugging.
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
from app.database import crud
from app.session.session_manager import (
    get_session_with_history, save_message,
    update_session_metadata, update_session_phase,
    flag_emergency, get_conversation_history
)
from app.agents.model_router import route, RouteDecision, get_runtime_config
from app.agents.intake_agent import run_intake_stream
from app.agents.legal_agent import run_legal_expert_stream
from app.emergency.detector import detect_emergency_llm, get_emergency_response
import psutil

router = APIRouter()

# ─── Structured logging ───────────────────────────────────────────────────────
LOG = logging.getLogger("strisakhi")

# In-memory ring buffer — last 200 events, readable by admin
EVENT_LOG: deque = deque(maxlen=200)

def log_event(level: str, event_type: str, session_id: str = "", **kwargs):
    """Emit to Python logger AND store in admin-readable buffer."""
    ts = datetime.now().strftime("%H:%M:%S")
    detail = " ".join(f"{k}={v}" for k, v in kwargs.items())
    msg = f"[{event_type}] {session_id[:8] if session_id else ''} {detail}"

    icons = {
        "INTAKE": "🔍", "EXPERT": "⚡", "EMERGENCY": "🚨",
        "FOLLOWUP": "💬", "RAG": "📚", "ROUTE": "🔀",
        "PHASE": "→", "DONE": "✅", "ERROR": "❌",
        "EMERGENCY_CHECK": "🛡️", "PARAM": "📝",
    }
    icon = icons.get(event_type, "•")
    print(f"{icon} {ts} {msg}", flush=True)

    EVENT_LOG.append({
        "ts": ts,
        "level": level,
        "type": event_type,
        "session": session_id[:8] if session_id else "",
        "detail": {**kwargs},
    })


# ─── Emergency messages ───────────────────────────────────────────────────────
EMERGENCY_MESSAGES = {
    "hi": (
        "🆘 आपकी स्थिति बहुत गंभीर लग रही है।\n\n"
        "**अभी तुरंत करें:**\n"
        "📞 **181** — महिला हेल्पलाइन (24 घंटे, FREE)\n"
        "📞 **100** — Police\n"
        "📞 **1091** — Women in Distress\n\n"
        "आप सुरक्षित जगह जाएं। मैं यहाँ हूँ — बात जारी रखें।"
    ),
    "en": (
        "🆘 Your situation sounds very serious.\n\n"
        "**Call RIGHT NOW:**\n"
        "📞 **181** — Women Helpline (24 hours, FREE)\n"
        "📞 **100** — Police\n"
        "📞 **1091** — Women in Distress\n\n"
        "Please get to a safe place. I'm still here — keep talking to me."
    ),
    "bn": (
        "🆘 আপনার পরিস্থিতি খুব গুরুতর মনে হচ্ছে।\n\n"
        "**এখনই ফোন করুন:**\n"
        "📞 **181** — মহিলা হেল্পলাইন (24 ঘণ্টা, FREE)\n"
        "📞 **100** — পুলিশ\n\n"
        "নিরাপদ জায়গায় যান। আমি এখানে আছি।"
    ),
}

EMERGENCY_FOLLOWUPS = {
    "hi": [
        "मुझे कानूनी मदद चाहिए",
        "Protection order कैसे मिलेगा?",
        "FIR कैसे दर्ज करें?",
        "मुफ्त वकील कहाँ मिलेगा?",
        "घर में रहने का क्या अधिकार है?",
    ],
    "en": [
        "I need legal help",
        "How do I get a protection order?",
        "How do I file an FIR?",
        "Where can I get a free lawyer?",
        "What are my rights to stay in the home?",
    ],
    "bn": [
        "আমার আইনি সাহায্য দরকার",
        "Protection order কীভাবে পাব?",
        "FIR কীভাবে করব?",
    ],
}


class ChatRequest(BaseModel):
    session_id: str
    message: str
    input_type: Optional[str] = "text"
    language: Optional[str] = "hi"


def _get_metadata(session_data: dict) -> dict:
    """
    Extract metadata from session_data.
    Handles both 'metadata' and 'metadata_json' key names.
    """
    meta = (
        session_data.get("metadata") or
        session_data.get("metadata_json") or
        {}
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
    cfg = get_runtime_config()
    max_turns = cfg.get("intake_max_turns", 10)
    current_phase = session_data.get("agent_phase", "intake")
    metadata = _get_metadata(session_data)

    log_event("INFO", "ROUTE", req.session_id,
              phase=current_phase,
              lang=language,
              msg=req.message[:50])

    # ── Step 1: LLM Emergency check (every message, every phase) ─────────────
    log_event("INFO", "EMERGENCY_CHECK", req.session_id, msg=req.message[:50])
    emergency_result = await detect_emergency_llm(req.message, "legal")
    is_emergency = emergency_result.get("is_emergency", False)
    severity = emergency_result.get("severity", "none")

    log_event(
        "WARN" if is_emergency else "INFO",
        "EMERGENCY_CHECK", req.session_id,
        detected=is_emergency,
        severity=severity,
        reason=emergency_result.get("reason", "")[:60]
    )

    if is_emergency and severity == "critical":
        flag_emergency(db, req.session_id)
        save_message(db, req.session_id, "user", req.message, req.input_type)
        emergency_text = EMERGENCY_MESSAGES.get(language, EMERGENCY_MESSAGES["en"])
        emergency_data = get_emergency_response("legal", "legal", language)
        log_event("WARN", "EMERGENCY", req.session_id, action="overlay_shown")

        async def emergency_stream():
            yield f"data: {json.dumps({'type': 'emergency', 'data': emergency_data})}\n\n"
            for char in emergency_text:
                yield f"data: {json.dumps({'type': 'token', 'token': char, 'agent': 'emergency'})}\n\n"
            save_message(db, req.session_id, "assistant", emergency_text,
                        citations=[], agent_used="emergency")
            yield f"data: {json.dumps({'type': 'done', 'full_response': emergency_text, 'citations': [], 'agent': 'emergency', 'follow_up_questions': EMERGENCY_FOLLOWUPS.get(language, EMERGENCY_FOLLOWUPS['en'])})}\n\n"

        return StreamingResponse(
            emergency_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )

    # ── Step 2: Save user message ─────────────────────────────────────────────
    save_message(db, req.session_id, "user", req.message, req.input_type,
                 agent_used=current_phase)

    history = get_conversation_history(db, req.session_id)
    user_turns = sum(1 for m in history if m.get("role") == "user")

    # Re-read metadata fresh from DB after saving user message
    # This ensures score from previous turn is included
    fresh_session = get_session_with_history(db, req.session_id)
    metadata = _get_metadata(fresh_session)

    log_event("INFO", "INTAKE", req.session_id,
              turn=user_turns,
              score=metadata.get("readiness_score", 0),
              crime=metadata.get("crime_type", "unknown"),
              phase=current_phase)

    # ── Step 3: Route ─────────────────────────────────────────────────────────
    decision, model_name, reason = route(
        agent_phase=current_phase,
        confidence_score=session_data.get("confidence_score", 0),
        emergency_flagged=False,  # Never block routing — emergency handled above already
        metadata=metadata,
        tab_type="legal",
        user_turn_count=user_turns,
    )

    log_event("INFO", "ROUTE", req.session_id,
              decision=decision.value,
              reason=reason[:60])

    return StreamingResponse(
        _stream(
            db, req.session_id, req.message, decision, metadata,
            history, language, session_data, model_name, reason,
            user_turns, max_turns
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


async def _stream(
    db, session_id, message, decision, metadata,
    history, language, session_data, model_name, reason,
    user_turns, max_turns
):
    start = time.time()
    full_response = ""
    citations = []
    agent_used = decision.value
    follow_ups = []

    yield f"data: {json.dumps({'type': 'routing', 'decision': decision.value, 'reason': reason, 'turn': user_turns, 'score': metadata.get('readiness_score', 0)})}\n\n"

    mem = psutil.virtual_memory()
    yield f"data: {json.dumps({'type': 'metrics', 'ram_used_gb': round(mem.used/(1024**3), 2), 'ram_percent': mem.percent})}\n\n"

    # ── INTAKE ────────────────────────────────────────────────────────────────
    if decision == RouteDecision.INTAKE:
        log_event("INFO", "INTAKE", session_id, turn=user_turns, action="calling_llm")

        async for ev in run_intake_stream(
            history, metadata, "legal", language, user_turns, max_turns
        ):
            if ev["type"] == "token":
                full_response += ev["token"]
                yield f"data: {json.dumps(ev)}\n\n"

            elif ev["type"] == "metadata_update":
                new_meta = ev["metadata"]
                score = ev["confidence_score"]
                update_session_metadata(db, session_id, new_meta)
                try:
                    crud.update_session(db, session_id, confidence_score=score)
                except Exception:
                    pass
                log_event("INFO", "PARAM", session_id,
                          score=score,
                          crime=new_meta.get("crime_type", "?"),
                          urgency=new_meta.get("urgency", "?"),
                          relation=new_meta.get("relationship_to_accused", "?"))
                yield f"data: {json.dumps({'type': 'metadata_update', 'confidence_score': score, 'metadata': new_meta})}\n\n"

            elif ev["type"] == "phase_change":
                update_session_phase(db, session_id, "expert")
                log_event("INFO", "PHASE", session_id,
                          from_phase="intake",
                          to_phase="expert",
                          reason=ev.get("reason", ""))
                yield f"data: {json.dumps({'type': 'phase_change', 'from': 'intake', 'to': 'expert'})}\n\n"

            elif ev["type"] == "error":
                log_event("ERROR", "ERROR", session_id, msg=ev["message"])
                yield f"data: {json.dumps({'type': 'error', 'message': ev['message']})}\n\n"
                return

    # ── EXPERT ────────────────────────────────────────────────────────────────
    elif decision == RouteDecision.EXPERT:
        current_phase = session_data.get("agent_phase", "intake")
        if current_phase not in ("expert", "follow_up"):
            update_session_phase(db, session_id, "expert")
            log_event("INFO", "PHASE", session_id,
                      from_phase=current_phase, to_phase="expert")

        log_event("INFO", "EXPERT", session_id,
                  crime=metadata.get("crime_type", "unknown"),
                  score=metadata.get("readiness_score", 0),
                  action="calling_rag_and_llm")

        async for ev in run_legal_expert_stream(metadata, history, language):
            if ev["type"] == "token":
                full_response += ev["token"]
                yield f"data: {json.dumps(ev)}\n\n"
            elif ev["type"] == "rag_retrieved":
                citations = ev.get("citations", [])
                log_event("INFO", "RAG", session_id,
                          chunks=ev.get("chunk_count", 0),
                          sources=[c.get("source", "?")[:20] for c in citations[:3]])
                yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
            elif ev["type"] == "done":
                follow_ups = ev.get("follow_up_questions", [])
            elif ev["type"] == "error":
                log_event("ERROR", "ERROR", session_id, msg=ev["message"])
                yield f"data: {json.dumps({'type': 'error', 'message': ev['message']})}\n\n"
                return

        # Move to follow_up after expert responds
        update_session_phase(db, session_id, "follow_up")
        log_event("INFO", "PHASE", session_id,
                  from_phase="expert", to_phase="follow_up")

    # ── FOLLOW_UP — short contextual answer, not full expert response ─────────
    elif decision == RouteDecision.FOLLOW_UP:
        log_event("INFO", "FOLLOWUP", session_id,
                  msg=message[:50],
                  crime=metadata.get("crime_type", "unknown"))

        # Expert agent detects short follow-up messages and gives 2-4 sentence answer
        # The _is_followup() function in legal_agent.py handles this automatically
        async for ev in run_legal_expert_stream(metadata, history, language):
            if ev["type"] == "token":
                full_response += ev["token"]
                yield f"data: {json.dumps(ev)}\n\n"
            elif ev["type"] == "rag_retrieved":
                citations = ev.get("citations", [])
                yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
            elif ev["type"] == "done":
                follow_ups = ev.get("follow_up_questions", [])
            elif ev["type"] == "error":
                yield f"data: {json.dumps({'type': 'error', 'message': ev['message']})}\n\n"
                return

    response_ms = int((time.time() - start) * 1000)
    word_count = len(full_response.split())

    log_event("INFO", "DONE", session_id,
              agent=agent_used,
              words=word_count,
              ms=response_ms,
              followups=len(follow_ups))

    save_message(
        db, session_id, "assistant", full_response,
        citations=citations, agent_used=agent_used, response_ms=response_ms
    )

    yield f"data: {json.dumps({'type': 'done', 'full_response': full_response, 'citations': citations, 'response_ms': response_ms, 'agent': agent_used, 'follow_up_questions': follow_ups})}\n\n"


@router.get("/test")
async def legal_test():
    return {"status": "Kanoon Sakhi API ready"}
