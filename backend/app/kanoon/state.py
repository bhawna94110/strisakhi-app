"""
StriSakhi — Kanoon Sakhi State
Single source of truth for entire LangGraph pipeline.
All case fields stored in English regardless of user language.
"""
from typing import Optional, Any, Literal
from typing_extensions import TypedDict
from pydantic import BaseModel, Field


# ─── Pydantic models — every LLM call returns one of these ───────────────────

class CrimeDetection(BaseModel):
    """Returned by intake node on first message or when crime_type unknown."""
    crime_type: Literal[
        "domestic_violence", "property", "dowry", "rape",
        "divorce", "maintenance", "workplace", "stalking",
        "acid_attack", "trafficking", "custody", "other"
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    urgency: Optional[Literal[
        "immediate", "recent", "ongoing", "historical"
    ]] = None
    relationship_to_accused: Optional[str] = None
    other_context: Optional[str] = None


class FieldExtraction(BaseModel):
    """Returned by intake node when extracting a specific field."""
    field_name: str
    field_value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    other_context: Optional[str] = None
    frustrated: bool = False


class IntakeQuestion(BaseModel):
    """Next question to ask the user."""
    question_hi: str    # Devanagari Hindi
    question_en: str    # English
    empathy_hi: Optional[str] = None   # empathy prefix for turn 1
    empathy_en: Optional[str] = None


class EmergencyCheck(BaseModel):
    """Returned by emergency node."""
    is_emergency: bool
    severity: Literal["critical", "warning", "none"]
    reason: str


class FollowUpQuestions(BaseModel):
    """Returned by followup node."""
    questions: list[str] = Field(min_length=3, max_length=5)


# ─── Main state ───────────────────────────────────────────────────────────────

class KanoonState(TypedDict):

    # ── Session ──────────────────────────────────────────────────────────────
    session_id: str
    language: str           # "hi" | "en" | "bn"
    turn_count: int
    phase: str              # "intake" | "expert" | "follow_up"
    max_turns: int          # from admin config (default 10)

    # ── Message ──────────────────────────────────────────────────────────────
    user_message_raw: str           # exactly what user typed/spoke
    user_message_processed: str     # Bengali→EN translated; others unchanged

    # ── Universal case fields (always English values) ─────────────────────────
    crime_type: Optional[str]
    urgency: Optional[str]
    relationship_to_accused: Optional[str]
    state_india: Optional[str]      # Indian state (UP, Bihar, Maharashtra...)
    has_children: Optional[str]     # "yes_with_me" | "yes_with_husband" | "no"
    marriage_date: Optional[str]
    other_context: Optional[str]    # free text, always sent to expert

    # ── Domestic violence specific ────────────────────────────────────────────
    living_situation: Optional[str]
    house_ownership: Optional[str]
    type_of_violence: Optional[str]
    financial_dependence: Optional[str]
    previous_complaints: Optional[str]
    medical_evidence: Optional[str]
    dowry_demand: Optional[str]
    witnesses: Optional[str]

    # ── Property specific ─────────────────────────────────────────────────────
    property_type: Optional[str]
    father_alive: Optional[bool]
    religion: Optional[str]
    will_exists: Optional[str]
    who_blocking: Optional[str]
    already_sold: Optional[str]
    property_registered: Optional[str]
    documents_available: Optional[str]

    # ── Maintenance specific ──────────────────────────────────────────────────
    marital_status_current: Optional[str]
    husband_income: Optional[str]
    your_income: Optional[str]
    husband_paying_anything: Optional[str]
    how_long_separated: Optional[str]
    reason_for_separation: Optional[str]
    previous_court_order: Optional[str]

    # ── Workplace specific ────────────────────────────────────────────────────
    company_size: Optional[str]
    accused_designation: Optional[str]
    incident_type: Optional[str]
    icc_exists: Optional[str]
    evidence_available: Optional[str]
    retaliation_happened: Optional[str]
    reported_to_hr: Optional[str]

    # ── Divorce specific ──────────────────────────────────────────────────────
    grounds: Optional[str]
    husband_consent: Optional[str]
    maintenance_needed: Optional[str]
    separation_duration: Optional[str]
    marriage_registered: Optional[str]

    # ── Stalking specific ─────────────────────────────────────────────────────
    stalking_medium: Optional[str]
    accused_known: Optional[str]
    content_type: Optional[str]
    screenshots_saved: Optional[str]
    threats_to_share: Optional[str]

    # ── Dowry specific ────────────────────────────────────────────────────────
    demand_type: Optional[str]
    who_demanding: Optional[str]
    violence_with_demand: Optional[str]
    stridhan_returned: Optional[str]
    written_evidence: Optional[str]

    # ── Custody specific ──────────────────────────────────────────────────────
    children_ages: Optional[str]
    current_custody: Optional[str]
    divorce_status: Optional[str]
    father_behaviour: Optional[str]

    # ── Scoring & routing ─────────────────────────────────────────────────────
    readiness_score: int
    fields_collected: list      # field names already answered
    fields_pending: list        # field names still needed

    # ── Flags ─────────────────────────────────────────────────────────────────
    emergency_detected: bool
    emergency_enabled: bool     # admin toggle
    frustrated: bool
    go_to_expert: bool          # set True when ready

    # ── RAG ───────────────────────────────────────────────────────────────────
    rag_context: str
    citations: list

    # ── Output ────────────────────────────────────────────────────────────────
    current_question: str       # question being streamed to user
    response: str               # expert response
    follow_up_questions: list

    # ── Conversation history ──────────────────────────────────────────────────
    history: list               # [{role, content}] last 8 turns

    # ── Error ─────────────────────────────────────────────────────────────────
    error: Optional[str]


def initial_state(
    session_id: str,
    language: str,
    user_message: str,
    history: list,
    emergency_enabled: bool = True,
    max_turns: int = 10,
    existing_metadata: Optional[dict] = None,
) -> KanoonState:
    """
    Create initial state for a new message.
    Restores case fields from existing session metadata.
    """
    meta = existing_metadata or {}

    return KanoonState(
        session_id=session_id,
        language=language,
        turn_count=len([m for m in history if m.get("role") == "user"]),
        phase=meta.get("phase", "intake"),
        max_turns=max_turns,

        user_message_raw=user_message,
        user_message_processed=user_message,  # may be updated by translate node

        # Restore all case fields from metadata
        crime_type=meta.get("crime_type"),
        urgency=meta.get("urgency"),
        relationship_to_accused=meta.get("relationship_to_accused"),
        state_india=meta.get("state_india"),
        has_children=meta.get("has_children"),
        marriage_date=meta.get("marriage_date"),
        other_context=meta.get("other_context"),

        # DV
        living_situation=meta.get("living_situation"),
        house_ownership=meta.get("house_ownership"),
        type_of_violence=meta.get("type_of_violence"),
        financial_dependence=meta.get("financial_dependence"),
        previous_complaints=meta.get("previous_complaints"),
        medical_evidence=meta.get("medical_evidence"),
        dowry_demand=meta.get("dowry_demand"),
        witnesses=meta.get("witnesses"),

        # Property
        property_type=meta.get("property_type"),
        father_alive=meta.get("father_alive"),
        religion=meta.get("religion"),
        will_exists=meta.get("will_exists"),
        who_blocking=meta.get("who_blocking"),
        already_sold=meta.get("already_sold"),
        property_registered=meta.get("property_registered"),
        documents_available=meta.get("documents_available"),

        # Maintenance
        marital_status_current=meta.get("marital_status_current"),
        husband_income=meta.get("husband_income"),
        your_income=meta.get("your_income"),
        husband_paying_anything=meta.get("husband_paying_anything"),
        how_long_separated=meta.get("how_long_separated"),
        reason_for_separation=meta.get("reason_for_separation"),
        previous_court_order=meta.get("previous_court_order"),

        # Workplace
        company_size=meta.get("company_size"),
        accused_designation=meta.get("accused_designation"),
        incident_type=meta.get("incident_type"),
        icc_exists=meta.get("icc_exists"),
        evidence_available=meta.get("evidence_available"),
        retaliation_happened=meta.get("retaliation_happened"),
        reported_to_hr=meta.get("reported_to_hr"),

        # Divorce
        grounds=meta.get("grounds"),
        husband_consent=meta.get("husband_consent"),
        maintenance_needed=meta.get("maintenance_needed"),
        separation_duration=meta.get("separation_duration"),
        marriage_registered=meta.get("marriage_registered"),

        # Stalking
        stalking_medium=meta.get("stalking_medium"),
        accused_known=meta.get("accused_known"),
        content_type=meta.get("content_type"),
        screenshots_saved=meta.get("screenshots_saved"),
        threats_to_share=meta.get("threats_to_share"),

        # Dowry
        demand_type=meta.get("demand_type"),
        who_demanding=meta.get("who_demanding"),
        violence_with_demand=meta.get("violence_with_demand"),
        stridhan_returned=meta.get("stridhan_returned"),
        written_evidence=meta.get("written_evidence"),

        # Custody
        children_ages=meta.get("children_ages"),
        current_custody=meta.get("current_custody"),
        divorce_status=meta.get("divorce_status"),
        father_behaviour=meta.get("father_behaviour"),

        # Scoring
        readiness_score=meta.get("readiness_score", 0),
        fields_collected=meta.get("fields_collected", []),
        fields_pending=meta.get("fields_pending", []),

        # Flags
        emergency_detected=False,
        emergency_enabled=emergency_enabled,
        frustrated=False,
        go_to_expert=False,

        # RAG
        rag_context="",
        citations=[],

        # Output
        current_question="",
        response="",
        follow_up_questions=[],

        # History
        history=history[-8:],

        error=None,
    )


def state_to_metadata(state: KanoonState) -> dict:
    """
    Extract all case fields from state for saving to SQLite metadata_json.
    Called by save node after each turn.
    """
    fields = [
        "crime_type", "urgency", "relationship_to_accused", "state_india",
        "has_children", "marriage_date", "other_context",
        "living_situation", "house_ownership", "type_of_violence",
        "financial_dependence", "previous_complaints", "medical_evidence",
        "dowry_demand", "witnesses",
        "property_type", "father_alive", "religion", "will_exists",
        "who_blocking", "already_sold", "property_registered", "documents_available",
        "marital_status_current", "husband_income", "your_income",
        "husband_paying_anything", "how_long_separated", "reason_for_separation",
        "previous_court_order",
        "company_size", "accused_designation", "incident_type", "icc_exists",
        "evidence_available", "retaliation_happened", "reported_to_hr",
        "grounds", "husband_consent", "maintenance_needed", "separation_duration",
        "marriage_registered",
        "stalking_medium", "accused_known", "content_type",
        "screenshots_saved", "threats_to_share",
        "demand_type", "who_demanding", "violence_with_demand",
        "stridhan_returned", "written_evidence",
        "children_ages", "current_custody", "divorce_status", "father_behaviour",
        "readiness_score", "fields_collected", "fields_pending", "phase",
    ]
    return {f: state.get(f) for f in fields if state.get(f) is not None}
