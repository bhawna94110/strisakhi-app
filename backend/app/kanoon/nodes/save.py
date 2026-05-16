"""
Save Node — Pure Python
Persists state to SQLite after each turn.
Updates: metadata_json, agent_phase, confidence_score.
"""
from app.kanoon.state import KanoonState, state_to_metadata


def save_node(state: KanoonState, db) -> dict:
    """
    Save state to SQLite.
    db is passed in from legal.py — not part of LangGraph state.
    """
    from app.session.session_manager import (
        update_session_metadata, update_session_phase, save_message
    )
    from app.database import crud

    session_id = state.get("session_id", "")
    metadata = state_to_metadata(state)
    phase = state.get("phase", "intake")
    score = state.get("readiness_score", 0)

    try:
        update_session_metadata(db, session_id, metadata)
        update_session_phase(db, session_id, phase)
        crud.update_session(db, session_id, confidence_score=score)
    except Exception as e:
        import logging
        logging.getLogger("strisakhi").warning(f"Save node failed: {e}")

    return {}
