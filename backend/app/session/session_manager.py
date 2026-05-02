import uuid
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session as DBSession
from app.database import crud
from app.database.models import Session
from app.config import settings

def create_new_session(db: DBSession, tab_type: str) -> dict:
    session_id = str(uuid.uuid4())
    session = crud.create_session(db, session_id, tab_type)
    return _session_to_dict(session)

def get_session_with_history(db: DBSession, session_id: str) -> dict:
    session = crud.get_session(db, session_id)
    if not session:
        return None
    messages = crud.get_messages(db, session_id)
    result = _session_to_dict(session)
    result["messages"] = [_message_to_dict(m) for m in messages]
    return result

def delete_session(db: DBSession, session_id: str) -> bool:
    return crud.delete_session(db, session_id)

def update_session_metadata(db: DBSession, session_id: str, metadata: dict) -> dict:
    session = crud.update_session(
        db,
        session_id,
        metadata_json=json.dumps(metadata, ensure_ascii=False)
    )
    return _session_to_dict(session) if session else None

def update_session_phase(db: DBSession, session_id: str, phase: str, confidence: int = None) -> dict:
    kwargs = {"agent_phase": phase}
    if confidence is not None:
        kwargs["confidence_score"] = confidence
    session = crud.update_session(db, session_id, **kwargs)
    return _session_to_dict(session) if session else None

def flag_emergency(db: DBSession, session_id: str) -> dict:
    session = crud.update_session(db, session_id, emergency_flagged=True)
    return _session_to_dict(session) if session else None

def save_message(
    db: DBSession,
    session_id: str,
    role: str,
    content: str,
    input_type: str = "text",
    citations: list = None,
    agent_used: str = None,
    tokens_used: int = None,
    response_ms: int = None
) -> dict:
    msg = crud.create_message(
        db, session_id, role, content,
        input_type, citations, agent_used,
        tokens_used, response_ms
    )
    return _message_to_dict(msg)

def get_conversation_history(db: DBSession, session_id: str) -> list:
    messages = crud.get_messages(db, session_id)
    return [{"role": m.role, "content": m.content} for m in messages]

def get_session_summary(db: DBSession, session_id: str) -> dict:
    session = crud.get_session(db, session_id)
    if not session:
        return None
    messages = crud.get_messages(db, session_id)
    metadata = json.loads(session.metadata_json) if session.metadata_json else {}

    # Build plain text summary
    user_messages = [m.content for m in messages if m.role == "user"]
    summary_text = " | ".join(user_messages[:5]) if user_messages else "No conversation"

    return {
        "session_id": session_id,
        "tab_type": session.tab_type,
        "summary": summary_text,
        "metadata": metadata,
        "issue_type": metadata.get("issue_type", "unknown"),
        "urgency": metadata.get("urgency", "unknown"),
        "location_state": metadata.get("location_state", "unknown"),
        "message_count": len(messages),
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }

def _session_to_dict(session: Session) -> dict:
    return {
        "session_id": session.id,
        "tab_type": session.tab_type,
        "language": session.language,
        "agent_phase": session.agent_phase,
        "confidence_score": session.confidence_score,
        "emergency_flagged": session.emergency_flagged,
        "metadata": json.loads(session.metadata_json) if session.metadata_json else {},
        "lead_submitted": session.lead_submitted,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "last_active": session.last_active.isoformat() if session.last_active else None,
    }

def _message_to_dict(msg) -> dict:
    import json
    return {
        "id": msg.id,
        "session_id": msg.session_id,
        "role": msg.role,
        "content": msg.content,
        "input_type": msg.input_type,
        "citations": json.loads(msg.citations_json) if msg.citations_json else [],
        "agent_used": msg.agent_used,
        "tokens_used": msg.tokens_used,
        "response_ms": msg.response_ms,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }
