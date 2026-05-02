from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from app.database.connection import Base

class Session(Base):
    __tablename__ = "sessions"
    id                = Column(String, primary_key=True)
    tab_type          = Column(String, nullable=False)          # legal | medical
    language          = Column(String, default="hi")
    agent_phase       = Column(String, default="intake")        # intake | expert
    confidence_score  = Column(Integer, default=0)
    emergency_flagged = Column(Boolean, default=False)
    metadata_json     = Column(Text, nullable=True)             # JSON case file
    lead_submitted    = Column(Boolean, default=False)
    created_at        = Column(DateTime, server_default=func.now())
    last_active       = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Message(Base):
    __tablename__ = "messages"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    session_id     = Column(String, ForeignKey("sessions.id"), nullable=False)
    role           = Column(String, nullable=False)             # user | assistant
    content        = Column(Text, nullable=False)
    input_type     = Column(String, default="text")             # text | voice
    citations_json = Column(Text, nullable=True)                # JSON array
    agent_used     = Column(String, nullable=True)              # intake | expert
    tokens_used    = Column(Integer, nullable=True)
    response_ms    = Column(Integer, nullable=True)             # response time
    created_at     = Column(DateTime, server_default=func.now())

class LegalLead(Base):
    __tablename__ = "legal_leads"
    id                   = Column(Integer, primary_key=True, autoincrement=True)
    session_id           = Column(String, nullable=True)
    name                 = Column(String, nullable=True)
    phone                = Column(String, nullable=False)
    district             = Column(String, nullable=True)
    state                = Column(String, nullable=True)
    issue_type           = Column(String, nullable=True)
    urgency_level        = Column(String, nullable=True)        # low|medium|high|emergency
    conversation_summary = Column(Text, nullable=True)
    status               = Column(String, default="pending")    # pending|assigned|resolved
    assigned_lawyer      = Column(String, nullable=True)
    created_at           = Column(DateTime, server_default=func.now())

class MedicalLead(Base):
    __tablename__ = "medical_leads"
    id                   = Column(Integer, primary_key=True, autoincrement=True)
    session_id           = Column(String, nullable=True)
    name                 = Column(String, nullable=True)
    phone                = Column(String, nullable=False)
    district             = Column(String, nullable=True)
    state                = Column(String, nullable=True)
    symptom_summary      = Column(Text, nullable=True)
    red_flag_detected    = Column(Boolean, default=False)
    conversation_summary = Column(Text, nullable=True)
    status               = Column(String, default="pending")
    assigned_doctor      = Column(String, nullable=True)
    created_at           = Column(DateTime, server_default=func.now())
