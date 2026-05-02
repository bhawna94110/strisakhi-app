"""
ModelRouter — Cactus Prize Component
Intelligently routes between Gemma 4 E2B (intake) and E4B (expert)
based on session phase, confidence score, and emergency detection.
"""
from enum import Enum
from app.config import settings

class RouteDecision(str, Enum):
    INTAKE    = "intake"
    EXPERT    = "expert"
    EMERGENCY = "emergency"

# These constants are documented explicitly for Cactus prize
INTAKE_MODEL = settings.intake_model   # gemma3n:e2b — lightweight, conversational
EXPERT_MODEL = settings.expert_model   # gemma3n:e4b — powerful, RAG-enabled

CONFIDENCE_THRESHOLD = 14   # out of 24 — minimum to invoke expert
MUST_HAVE_FIELDS_LEGAL = ["issue_type", "location_state", "religion", "urgency"]
MUST_HAVE_FIELDS_MEDICAL = ["patient_age", "primary_symptom", "duration", "red_flag_checked"]

def route(
    agent_phase: str,
    confidence_score: int,
    emergency_flagged: bool,
    metadata: dict,
    tab_type: str
) -> tuple[RouteDecision, str, str]:
    """
    Returns: (decision, model_name, reason)
    
    Routing logic:
    1. Emergency → emergency handler (no LLM)
    2. Phase=intake + confidence < threshold → E2B intake agent
    3. Phase=intake + confidence >= threshold + all must-haves → E4B expert
    4. Phase=expert → E4B expert always
    """
    # Rule 1: Emergency override — no LLM needed
    if emergency_flagged:
        return RouteDecision.EMERGENCY, "", "Emergency flagged — bypass LLM"

    # Rule 2: Already in expert phase
    if agent_phase == "expert":
        return RouteDecision.EXPERT, EXPERT_MODEL, "Session in expert phase"

    # Rule 3: Intake phase — check if ready for expert
    must_haves = MUST_HAVE_FIELDS_LEGAL if tab_type == "legal" else MUST_HAVE_FIELDS_MEDICAL
    all_must_haves = all(
        metadata.get(field) for field in must_haves
    )

    if confidence_score >= CONFIDENCE_THRESHOLD and all_must_haves:
        return RouteDecision.EXPERT, EXPERT_MODEL, f"Confidence {confidence_score}/24 — ready for expert"

    # Rule 4: Stay in intake
    return RouteDecision.INTAKE, INTAKE_MODEL, f"Confidence {confidence_score}/24 — still gathering info"

def calculate_confidence(metadata: dict, tab_type: str) -> int:
    """Calculate confidence score from collected metadata"""
    score = 0

    if tab_type == "legal":
        must_have = {
            "issue_type": 4, "location_state": 4,
            "religion": 4, "urgency": 4
        }
        should_have = {
            "marital_status": 2, "duration": 2,
            "prior_police_action": 2, "other_party": 2
        }
        nice_to_have = {
            "children_involved": 1, "has_medical_reports": 1,
            "has_witnesses": 1, "property_involved": 1
        }
    else:
        must_have = {
            "patient_age": 4, "primary_symptom": 4,
            "duration": 4, "red_flag_checked": 4
        }
        should_have = {
            "associated_symptoms": 2, "existing_conditions": 2,
            "travel_ability": 2, "pregnancy_status": 2
        }
        nice_to_have = {
            "current_medications": 1, "prior_diagnosis": 1,
            "distance_to_hospital": 1
        }

    for field, points in must_have.items():
        if metadata.get(field):
            score += points
    for field, points in should_have.items():
        if metadata.get(field):
            score += points
    for field, points in nice_to_have.items():
        if metadata.get(field):
            score += points

    return score
