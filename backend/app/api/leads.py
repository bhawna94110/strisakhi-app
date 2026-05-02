from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from app.database.connection import get_db
from app.database.crud import create_legal_lead, create_medical_lead, get_legal_leads, get_medical_leads
from app.session.session_manager import get_session_summary
from app.config import settings
import secrets

router = APIRouter()
security = HTTPBasic()

class LegalLeadRequest(BaseModel):
    session_id: Optional[str] = None
    name: Optional[str] = None
    phone: str
    district: Optional[str] = None
    state: Optional[str] = None
    issue_type: Optional[str] = None
    urgency_level: Optional[str] = "medium"

class MedicalLeadRequest(BaseModel):
    session_id: Optional[str] = None
    name: Optional[str] = None
    phone: str
    district: Optional[str] = None
    state: Optional[str] = None
    symptom_summary: Optional[str] = None
    red_flag_detected: bool = False

@router.post("/legal", status_code=201)
async def submit_legal_lead(req: LegalLeadRequest, db: Session = Depends(get_db)):
    # Auto-attach conversation summary if session_id provided
    summary_text = None
    if req.session_id:
        summary = get_session_summary(db, req.session_id)
        if summary:
            summary_text = summary.get("summary")
            if not req.issue_type:
                req.issue_type = summary.get("issue_type")
            if not req.state:
                req.state = summary.get("location_state")

    lead = create_legal_lead(
        db,
        session_id=req.session_id,
        name=req.name,
        phone=req.phone,
        district=req.district,
        state=req.state,
        issue_type=req.issue_type,
        urgency_level=req.urgency_level,
        conversation_summary=summary_text
    )
    return {
        "lead_id": lead.id,
        "message": "Ek vakeel 2-4 ghante mein aapko call karenge",
        "message_english": "A lawyer will call you within 2-4 hours",
        "helplines": {
            "women_helpline": "181",
            "police": "100",
            "legal_aid": "15100"
        }
    }

@router.post("/medical", status_code=201)
async def submit_medical_lead(req: MedicalLeadRequest, db: Session = Depends(get_db)):
    summary_text = None
    if req.session_id:
        summary = get_session_summary(db, req.session_id)
        if summary:
            summary_text = summary.get("summary")

    lead = create_medical_lead(
        db,
        session_id=req.session_id,
        name=req.name,
        phone=req.phone,
        district=req.district,
        state=req.state,
        symptom_summary=req.symptom_summary,
        red_flag_detected=req.red_flag_detected,
        conversation_summary=summary_text
    )
    return {
        "lead_id": lead.id,
        "message": "Ek doctor jald hi aapko call karenge",
        "message_english": "A doctor will call you soon",
        "emergency_numbers": {
            "ambulance": "108",
            "health_helpline": "104",
            "women_helpline": "181"
        }
    }

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    correct_user = secrets.compare_digest(credentials.username, settings.admin_username)
    correct_pass = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (correct_user and correct_pass):
        raise HTTPException(401, "Invalid credentials")
    return credentials.username

@router.get("/legal")
async def list_legal_leads(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin)
):
    offset = (page - 1) * limit
    leads, total = get_legal_leads(db, status, limit, offset)
    return {
        "leads": [_lead_to_dict(l) for l in leads],
        "total": total,
        "page": page,
        "limit": limit
    }

@router.get("/medical")
async def list_medical_leads(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin)
):
    offset = (page - 1) * limit
    leads, total = get_medical_leads(db, status, limit, offset)
    return {
        "leads": [_lead_to_dict(l) for l in leads],
        "total": total,
        "page": page,
        "limit": limit
    }

def _lead_to_dict(lead) -> dict:
    return {
        "id": lead.id,
        "session_id": lead.session_id,
        "name": lead.name,
        "phone": lead.phone,
        "district": lead.district,
        "state": lead.state,
        "status": lead.status,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "conversation_summary": lead.conversation_summary,
    }
