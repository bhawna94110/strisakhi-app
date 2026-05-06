"""
ModelRouter — Cactus Prize Component
Routes between intake and expert agents based on:
1. Turn count (most reliable)
2. Confidence score from metadata
3. Emergency detection
"""
from enum import Enum
from app.config import settings

class RouteDecision(str, Enum):
    INTAKE    = "intake"
    EXPERT    = "expert"
    EMERGENCY = "emergency"

INTAKE_MODEL = settings.intake_model
EXPERT_MODEL = settings.expert_model

# Lower threshold — just need to know the issue type
CONFIDENCE_THRESHOLD = 4
MUST_HAVE_FIELDS_LEGAL   = ["issue_type"]  # just needs problem identified
MUST_HAVE_FIELDS_MEDICAL = ["primary_symptom"]

# Turn count threshold — switch to expert after this many user messages
INTAKE_MAX_TURNS = 3

def route(
    agent_phase: str,
    confidence_score: int,
    emergency_flagged: bool,
    metadata: dict,
    tab_type: str,
    user_turn_count: int = 0          # NEW parameter
) -> tuple[RouteDecision, str, str]:
    """
    Returns: (decision, model_name, reason)
    Priority:
    1. Emergency → emergency handler
    2. Already expert → stay expert
    3. Turn count >= 3 → force expert
    4. Confidence + must-haves met → expert
    5. Default → intake
    """
    # Rule 1: Emergency override
    if emergency_flagged:
        return RouteDecision.EMERGENCY, "", "Emergency flagged"

    # Rule 2: Already in expert phase
    if agent_phase == "expert":
        return RouteDecision.EXPERT, EXPERT_MODEL, "Session in expert phase"

    # Rule 3: Turn count exceeded — force expert
    if user_turn_count >= INTAKE_MAX_TURNS:
        return RouteDecision.EXPERT, EXPERT_MODEL, f"Turn limit reached ({user_turn_count} turns) — switching to expert"

    # Rule 4: Confidence threshold met
    must_haves = MUST_HAVE_FIELDS_LEGAL if tab_type == "legal" else MUST_HAVE_FIELDS_MEDICAL
    all_must_haves = all(metadata.get(field) for field in must_haves)

    if confidence_score >= CONFIDENCE_THRESHOLD and all_must_haves:
        return RouteDecision.EXPERT, EXPERT_MODEL, f"Confidence {confidence_score}/24 — ready for expert"

    # Rule 5: Stay in intake
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
        if metadata.get(field): score += points
    for field, points in should_have.items():
        if metadata.get(field): score += points
    for field, points in nice_to_have.items():
        if metadata.get(field): score += points

    return score