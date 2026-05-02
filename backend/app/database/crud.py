from sqlalchemy.orm import Session as DBSession
from app.database.models import Session, Message, LegalLead, MedicalLead
from datetime import datetime, timedelta
from typing import Optional, List
import json

# ---------- SESSION CRUD ----------
def create_session(db: DBSession, session_id: str, tab_type: str) -> Session:
    session = Session(id=session_id, tab_type=tab_type)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

def get_session(db: DBSession, session_id: str) -> Optional[Session]:
    return db.query(Session).filter(Session.id == session_id).first()

def update_session(db: DBSession, session_id: str, **kwargs) -> Optional[Session]:
    session = get_session(db, session_id)
    if not session:
        return None
    for key, value in kwargs.items():
        setattr(session, key, value)
    session.last_active = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return session

def delete_session(db: DBSession, session_id: str) -> bool:
    db.query(Message).filter(Message.session_id == session_id).delete()
    rows = db.query(Session).filter(Session.id == session_id).delete()
    db.commit()
    return rows > 0

# ---------- MESSAGE CRUD ----------
def create_message(
    db: DBSession,
    session_id: str,
    role: str,
    content: str,
    input_type: str = "text",
    citations: list = None,
    agent_used: str = None,
    tokens_used: int = None,
    response_ms: int = None
) -> Message:
    msg = Message(
        session_id=session_id,
        role=role,
        content=content,
        input_type=input_type,
        citations_json=json.dumps(citations) if citations else None,
        agent_used=agent_used,
        tokens_used=tokens_used,
        response_ms=response_ms
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg

def get_messages(db: DBSession, session_id: str) -> List[Message]:
    return db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.created_at).all()

# ---------- LEADS CRUD ----------
def create_legal_lead(db: DBSession, **kwargs) -> LegalLead:
    lead = LegalLead(**kwargs)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead

def create_medical_lead(db: DBSession, **kwargs) -> MedicalLead:
    lead = MedicalLead(**kwargs)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead

def get_legal_leads(db: DBSession, status: str = None, limit: int = 20, offset: int = 0):
    query = db.query(LegalLead)
    if status:
        query = query.filter(LegalLead.status == status)
    total = query.count()
    leads = query.order_by(LegalLead.created_at.desc()).offset(offset).limit(limit).all()
    return leads, total

def get_medical_leads(db: DBSession, status: str = None, limit: int = 20, offset: int = 0):
    query = db.query(MedicalLead)
    if status:
        query = query.filter(MedicalLead.status == status)
    total = query.count()
    leads = query.order_by(MedicalLead.created_at.desc()).offset(offset).limit(limit).all()
    return leads, total
