"""
StriSakhi — Readiness Score + Field Priority
Designed for 4-5 turn intake conversations.
"""
from typing import Optional


CRIME_FIELD_PRIORITY = {
    "domestic_violence": [
        ("urgency",                 20, 1),
        ("relationship_to_accused", 20, 1),
        ("type_of_violence",        10, 2),
        ("living_situation",        10, 2),
        ("has_children",             5, 2),
        ("financial_dependence",     5, 2),
        ("previous_complaints",      5, 2),
        ("house_ownership",          5, 2),
        ("medical_evidence",         3, 3),
        ("dowry_demand",             3, 3),
        ("witnesses",                2, 3),
        ("state_india",              5, 3),
        ("other_context",            5, 3),
    ],
    "property": [
        ("urgency",                 10, 1),
        ("relationship_to_accused", 10, 1),
        ("property_type",           15, 1),
        ("father_alive",            15, 1),
        ("religion",                10, 2),
        ("will_exists",             10, 2),
        ("who_blocking",             5, 2),
        ("already_sold",             5, 2),
        ("property_registered",      5, 2),
        ("documents_available",      3, 3),
        ("state_india",              5, 3),
        ("other_context",            5, 3),
    ],
    "maintenance": [
        ("urgency",                 10, 1),
        ("relationship_to_accused", 10, 1),
        ("marital_status_current",  20, 1),
        ("husband_income",          15, 1),
        ("has_children",            10, 2),
        ("your_income",              5, 2),
        ("husband_paying_anything",  5, 2),
        ("how_long_separated",       5, 2),
        ("reason_for_separation",    5, 2),
        ("previous_court_order",     3, 3),
        ("state_india",              5, 3),
        ("other_context",            5, 3),
    ],
    "workplace": [
        ("urgency",                 10, 1),
        ("company_size",            15, 1),
        ("accused_designation",     15, 1),
        ("incident_type",           15, 1),
        ("icc_exists",              10, 2),
        ("evidence_available",      10, 2),
        ("retaliation_happened",     5, 2),
        ("reported_to_hr",           5, 2),
        ("state_india",              5, 3),
        ("other_context",            5, 3),
    ],
    "dowry": [
        ("urgency",                 10, 1),
        ("relationship_to_accused", 10, 1),
        ("demand_type",             15, 1),
        ("who_demanding",           15, 1),
        ("violence_with_demand",    10, 2),
        ("stridhan_returned",        5, 2),
        ("written_evidence",         5, 2),
        ("marriage_date",            5, 2),
        ("state_india",              5, 3),
        ("other_context",            5, 3),
    ],
    "divorce": [
        ("urgency",                 10, 1),
        ("grounds",                 20, 1),
        ("religion",                15, 1),
        ("husband_consent",         10, 2),
        ("has_children",            10, 2),
        ("marriage_registered",      5, 2),
        ("maintenance_needed",       5, 2),
        ("separation_duration",      5, 2),
        ("state_india",              5, 3),
        ("other_context",            5, 3),
    ],
    "stalking": [
        ("urgency",                 10, 1),
        ("stalking_medium",         20, 1),
        ("accused_known",           15, 1),
        ("content_type",            10, 2),
        ("screenshots_saved",       10, 2),
        ("threats_to_share",         5, 2),
        ("state_india",              5, 3),
        ("other_context",            5, 3),
    ],
    "rape": [
        ("urgency",                 50, 1),
        ("accused_known",           40, 1),
        ("other_context",            5, 3),
    ],
    "acid_attack": [
        ("urgency",                 90, 1),
        ("other_context",            5, 3),
    ],
    "trafficking": [
        ("urgency",                 90, 1),
        ("other_context",            5, 3),
    ],
    "custody": [
        ("urgency",                 10, 1),
        ("children_ages",           20, 1),
        ("current_custody",         20, 1),
        ("divorce_status",          15, 2),
        ("father_behaviour",         5, 2),
        ("has_children",             5, 2),
        ("state_india",              5, 3),
        ("other_context",            5, 3),
    ],
    "other": [
        ("urgency",                 20, 1),
        ("relationship_to_accused", 20, 1),
        ("state_india",             10, 3),
        ("other_context",           10, 3),
    ],
}

IMMEDIATE_EXPERT_CRIMES = {"rape", "acid_attack", "trafficking"}


def calculate_score(state: dict) -> int:
    """Score 0-100. Base 30 for crime detection + field scores."""
    crime_type = state.get("crime_type")
    if not crime_type:
        return 0

    score = 30  # base for crime_type detection

    fields = CRIME_FIELD_PRIORITY.get(crime_type, CRIME_FIELD_PRIORITY["other"])
    for field_name, points, _ in fields:
        val = state.get(field_name)
        if val is not None and val != "" and val != []:
            score += points

    return min(score, 100)


def get_next_field(state: dict) -> Optional[str]:
    """Return next unanswered field name, in priority order."""
    crime_type = state.get("crime_type")
    if not crime_type:
        return None

    collected = set(state.get("fields_collected", []))
    fields = CRIME_FIELD_PRIORITY.get(crime_type, CRIME_FIELD_PRIORITY["other"])

    # Tier 1 and 2 first
    for field_name, _, tier in fields:
        if tier <= 2 and field_name not in collected:
            if not state.get(field_name):
                return field_name

    # Then tier 3
    for field_name, _, tier in fields:
        if tier == 3 and field_name not in collected:
            if not state.get(field_name):
                return field_name

    return None


def get_pending_fields(state: dict) -> list:
    """Return uncollected important field names."""
    crime_type = state.get("crime_type")
    if not crime_type:
        return []

    pending = []
    fields = CRIME_FIELD_PRIORITY.get(crime_type, CRIME_FIELD_PRIORITY["other"])
    for field_name, _, tier in fields:
        if tier <= 2 and not state.get(field_name):
            pending.append(field_name)
    return pending


def should_route_to_expert(
    state: dict, turn_count: int, max_turns: int
) -> tuple[bool, str]:
    """
    Routing logic for 4-5 turn intake conversations.

    turn_count = messages sent BEFORE this response
    0 = first message, 1 = second message, etc.

    Target: expert on turn 4-5 for demo (turn_count 3-4).
    """
    crime_type = state.get("crime_type", "")
    score = calculate_score(state)

    # Immediate crimes — expert after 1 question
    if crime_type in IMMEDIATE_EXPERT_CRIMES and turn_count >= 1:
        return True, f"Sensitive crime ({crime_type})"

    # Frustration — always route immediately
    if state.get("frustrated"):
        return True, "User frustrated"

    # Perfect score — route (minimum 2 turns)
    if score >= 95 and turn_count >= 2:
        return True, f"Score {score} — complete case file (turn {turn_count + 1})"

    # Very high score — route after 3 turns
    if score >= 85 and turn_count >= 3:
        return True, f"Score {score} — strong context at turn {turn_count + 1}"

    # Good score — route after 4 turns
    if score >= 70 and turn_count >= 4:
        return True, f"Score {score} — sufficient at turn {turn_count + 1}"

    # Minimum viable — route after 5 turns
    if score >= 60 and turn_count >= 5:
        return True, f"Score {score} — routing after {turn_count + 1} turns"

    # Hard limit
    if turn_count >= max_turns:
        return True, f"Max turns ({max_turns}) reached"

    return False, f"Score {score} — collecting turn {turn_count + 1}"
