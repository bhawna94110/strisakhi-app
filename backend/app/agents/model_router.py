"""
StriSakhi — State Machine Router
Clean 4-state machine: INTAKE → EXPERT → FOLLOW_UP (EMERGENCY from any state)
Admin-configurable via config_runtime.json
"""
from enum import Enum
from typing import Literal

# ─── States ──────────────────────────────────────────────────────────────────
class AgentState(str, Enum):
    INTAKE    = "intake"
    EXPERT    = "expert"
    FOLLOW_UP = "follow_up"
    EMERGENCY = "emergency"

# Keep RouteDecision as alias for backward compat
class RouteDecision(str, Enum):
    INTAKE    = "intake"
    EXPERT    = "expert"
    EMERGENCY = "emergency"
    FOLLOW_UP = "follow_up"

# ─── Runtime Config (read from config_runtime.json via settings) ──────────────
def get_runtime_config() -> dict:
    """Read live config. Falls back to defaults if file missing."""
    try:
        from app.runtime_config import get_config
        return get_config()
    except Exception:
        return {
            "intake_max_turns": 10,
            "intake_min_score": 60,
            "temperature": 0.2,
            "expert_max_tokens": 700,
        }

# ─── Readiness Score ──────────────────────────────────────────────────────────
def calculate_readiness_score(metadata: dict) -> int:
    """
    Score 0-100 based on collected parameters.
    Mandatory params (30pts each): crime_type, urgency, relationship_to_accused
    Optional params (5pts each): state, has_children, duration,
                                 others_involved, previous_complaints, other_context
    """
    score = 0

    # Mandatory — 30 pts each (max 90)
    if metadata.get("crime_type"):              score += 30
    if metadata.get("urgency"):                 score += 30
    if metadata.get("relationship_to_accused"): score += 30

    # Optional — 5 pts each (max 30, but capped at 100 total)
    optional = [
        "state", "has_children", "duration",
        "others_involved", "previous_complaints", "other_context"
    ]
    for field in optional:
        if metadata.get(field) is not None:
            score += 5

    return min(score, 100)

# ─── Immediate Expert Crimes ──────────────────────────────────────────────────
# These bypass extended intake — too sensitive for long questioning
IMMEDIATE_EXPERT_CRIMES = {"rape", "acid_attack", "trafficking"}

# ─── Main Route Function ──────────────────────────────────────────────────────
def route(
    agent_phase: str,
    confidence_score: int,      # kept for backward compat
    emergency_flagged: bool,
    metadata: dict,
    tab_type: str,
    user_turn_count: int = 0,
) -> tuple[RouteDecision, str, str]:
    """
    Returns: (decision, model_name, reason)

    State machine transitions:
    EMERGENCY (from any state)  → emergency handler
    INTAKE  → EXPERT when score >= 60 AND turn >= 2
    INTAKE  → EXPERT when score >= 90 (immediately)
    INTAKE  → EXPERT when turn >= intake_max_turns
    INTAKE  → EXPERT when frustration detected (set in metadata)
    INTAKE  → EXPERT when crime is rape/acid_attack/trafficking after turn 1
    EXPERT  → stays EXPERT
    FOLLOW_UP → stays FOLLOW_UP
    """
    cfg = get_runtime_config()
    intake_max_turns = cfg.get("intake_max_turns", 10)
    intake_min_score = cfg.get("intake_min_score", 60)
    model_name = ""

    # ── Rule 1: Emergency — only on the turn it fires, not permanently ────────
    # emergency_flagged in DB just means it happened once.
    # After emergency response is sent, conversation should continue normally.
    # The legal.py emergency handler runs BEFORE route() is called,
    # so by the time route() is called, it's NOT an emergency turn.
    # This rule is now intentionally disabled — emergency is handled upstream.
    # if emergency_flagged:
    #     return RouteDecision.EMERGENCY, model_name, "Emergency flagged"

    # ── Rule 2: Already in expert or follow_up — stay there ───────────────────
    if agent_phase == "expert":
        return RouteDecision.EXPERT, model_name, "Session in expert phase"
    if agent_phase == "follow_up":
        return RouteDecision.FOLLOW_UP, model_name, "Session in follow_up phase"

    # ── Rule 3: Frustration — skip to expert immediately ─────────────────────
    if metadata.get("frustrated"):
        return RouteDecision.EXPERT, model_name, "Frustration detected — skipping to expert"

    # ── Rule 4: Severe crime — expert after 1 turn ────────────────────────────
    crime_type = metadata.get("crime_type", "")
    if crime_type in IMMEDIATE_EXPERT_CRIMES and user_turn_count >= 1:
        return RouteDecision.EXPERT, model_name, f"Severe crime ({crime_type}) — minimal intake"

    # ── Rule 5: Readiness score ───────────────────────────────────────────────
    score = calculate_readiness_score(metadata)

    if score >= 90:
        return RouteDecision.EXPERT, model_name, f"Score {score}/100 — all mandatory params collected"

    if score >= intake_min_score and user_turn_count >= 2:
        return RouteDecision.EXPERT, model_name, f"Score {score}/100 >= {intake_min_score} and turn {user_turn_count} >= 2"

    # ── Rule 6: Hard turn limit ────────────────────────────────────────────────
    if user_turn_count >= intake_max_turns:
        return RouteDecision.EXPERT, model_name, f"Turn limit {intake_max_turns} reached — forcing expert"

    # ── Default: stay in intake ────────────────────────────────────────────────
    return RouteDecision.INTAKE, model_name, f"Score {score}/100 — still collecting (turn {user_turn_count})"


# Backward compat alias
INTAKE_MAX_TURNS = 10

def calculate_confidence(metadata: dict, tab_type: str = "legal") -> int:
    return calculate_readiness_score(metadata)
