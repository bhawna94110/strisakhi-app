from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.session.session_manager import (
    create_new_session, get_session_with_history,
    delete_session, get_session_summary
)

router = APIRouter()

class NewSessionRequest(BaseModel):
    tab_type: str  # legal | medical

@router.post("/new")
async def new_session(req: NewSessionRequest, db: Session = Depends(get_db)):
    if req.tab_type not in ["legal", "medical"]:
        raise HTTPException(400, "tab_type must be 'legal' or 'medical'")
    session = create_new_session(db, req.tab_type)
    return session

@router.get("/{session_id}")
async def get_session(session_id: str, db: Session = Depends(get_db)):
    session = get_session_with_history(db, session_id)
    if not session:
        raise HTTPException(404, f"Session {session_id} not found")
    return session

@router.delete("/{session_id}")
async def reset_session(session_id: str, db: Session = Depends(get_db)):
    success = delete_session(db, session_id)
    if not success:
        raise HTTPException(404, f"Session {session_id} not found")
    return {"message": "Session deleted", "session_id": session_id}

@router.get("/{session_id}/summary")
async def session_summary(session_id: str, db: Session = Depends(get_db)):
    summary = get_session_summary(db, session_id)
    if not summary:
        raise HTTPException(404, f"Session {session_id} not found")
    return summary
