"""
StriSakhi — Readiness Score + Field Priority
Determines when intake has enough info to route to expert.
Also tracks which fields are still pending per crime type.
"""
from typing import Optional


# ─── Field priority per crime type ───────────────────────────────────────────
# Order matters — intake asks in this order
# (field_name, score_points, tier)
# tier 1 = mandatory, tier 2 = important, tier 3 = optional

CRIME_FIELD_PRIORITY = {
    "domestic_violence": [
        ("urgency",               20, 1),
        ("relationship_to_accused", 20, 1),
        ("type_of_violence",      10, 2),
        ("living_situation",       10, 2),
        ("has_children",            5, 2),
        ("financial_dependence",    5, 2),
        ("previous_complaints",     5, 2),
        ("house_ownership",         5, 2),
        ("medical_evidence",        3, 3),
        ("dowry_demand",            3, 3),
        ("witnesses",               2, 3),
        ("state_india",             5, 3),
        ("other_context",           5, 3),
    ],
    "property": [
        ("urgency",               10, 1),
        ("relationship_to_accused", 10, 1),
        ("property_type",         15, 1),
        ("father_alive",          15, 1),
        ("religion",              10, 2),
        ("will_exists",           10, 2),
        ("who_blocking",           5, 2),
        ("already_sold",           5, 2),
        ("property_registered",    5, 2),
        ("documents_available",    3, 3),
        ("state_india",            5, 3),
        ("other_context",          5, 3),
    ],
    "maintenance": [
        ("urgency",               10, 1),
        ("relationship_to_accused", 10, 1),
        ("marital_status_current", 20, 1),
        ("husband_income",         15, 1),
        ("has_children",           10, 2),
        ("your_income",             5, 2),
        ("husband_paying_anything", 5, 2),
        ("how_long_separated",      5, 2),
        ("reason_for_separation",   5, 2),
        ("previous_court_order",    3, 3),
        ("state_india",             5, 3),
        ("other_context",           5, 3),
    ],
    "workplace": [
        ("urgency",               10, 1),
        ("company_size",          15, 1),
        ("accused_designation",   15, 1),
        ("incident_type",         15, 1),
        ("icc_exists",            10, 2),
        ("evidence_available",    10, 2),
        ("retaliation_happened",   5, 2),
        ("reported_to_hr",         5, 2),
        ("state_india",            5, 3),
        ("other_context",          5, 3),
    ],
    "dowry": [
        ("urgency",               10, 1),
        ("relationship_to_accused", 10, 1),
        ("demand_type",           15, 1),
        ("who_demanding",         15, 1),
        ("violence_with_demand",  10, 2),
        ("stridhan_returned",      5, 2),
        ("written_evidence",       5, 2),
        ("marriage_date",          5, 2),
        ("state_india",            5, 3),
        ("other_context",          5, 3),
    ],
    "divorce": [
        ("urgency",               10, 1),
        ("grounds",               20, 1),
        ("religion",              15, 1),
        ("husband_consent",       10, 2),
        ("has_children",          10, 2),
        ("marriage_registered",    5, 2),
        ("maintenance_needed",     5, 2),
        ("separation_duration",    5, 2),
        ("state_india",            5, 3),
        ("other_context",          5, 3),
    ],
    "stalking": [
        ("urgency",               10, 1),
        ("stalking_medium",       20, 1),
        ("accused_known",         15, 1),
        ("content_type",          10, 2),
        ("screenshots_saved",     10, 2),
        ("threats_to_share",       5, 2),
        ("state_india",            5, 3),
        ("other_context",          5, 3),
    ],
    "rape": [
        # Minimal intake — go to expert immediately after 2 questions
        ("urgency",               50, 1),
        ("accused_known",         40, 1),
        ("other_context",          5, 3),
    ],
    "acid_attack": [
        ("urgency",               90, 1),
        ("other_context",          5, 3),
    ],
    "trafficking": [
        ("urgency",               90, 1),
        ("other_context",          5, 3),
    ],
    "custody": [
        ("urgency",               10, 1),
        ("children_ages",         20, 1),
        ("current_custody",       20, 1),
        ("divorce_status",        15, 2),
        ("father_behaviour",       5, 2),
        ("has_children",           5, 2),
        ("state_india",            5, 3),
        ("other_context",          5, 3),
    ],
    "other": [
        ("urgency",               20, 1),
        ("relationship_to_accused", 20, 1),
        ("state_india",           10, 3),
        ("other_context",         10, 3),
    ],
}

# Crimes that go to expert after minimal intake
IMMEDIATE_EXPERT_CRIMES = {"rape", "acid_attack", "trafficking"}


def calculate_score(state: dict) -> int:
    """
    Calculate readiness score from state.
    Base 30 pts for crime_type detection.
    Remaining 70 pts from crime-specific fields.
    """
    score = 0

    crime_type = state.get("crime_type")
    if not crime_type:
        return 0

    # Base: crime_type detected = 30 pts
    score += 30

    # Crime-specific field scores
    fields = CRIME_FIELD_PRIORITY.get(crime_type, CRIME_FIELD_PRIORITY["other"])
    for field_name, points, _ in fields:
        val = state.get(field_name)
        if val is not None and val != "" and val != []:
            score += points

    return min(score, 100)


def get_next_field(state: dict) -> Optional[str]:
    """
    Return the name of the next field to collect.
    Returns None if all important fields are collected.
    Skips already-collected fields.
    """
    crime_type = state.get("crime_type")
    if not crime_type:
        return None

    collected = set(state.get("fields_collected", []))
    fields = CRIME_FIELD_PRIORITY.get(crime_type, CRIME_FIELD_PRIORITY["other"])

    # Always collect tier 1 and tier 2 fields in order
    for field_name, _, tier in fields:
        if tier <= 2 and field_name not in collected:
            val = state.get(field_name)
            if val is None or val == "":
                return field_name

    # Then tier 3 if turns remain
    for field_name, _, tier in fields:
        if tier == 3 and field_name not in collected:
            val = state.get(field_name)
            if val is None or val == "":
                return field_name

    return None  # All fields collected


def get_pending_fields(state: dict) -> list:
    """Return list of all uncollected important field names."""
    crime_type = state.get("crime_type")
    if not crime_type:
        return []

    pending = []
    fields = CRIME_FIELD_PRIORITY.get(crime_type, CRIME_FIELD_PRIORITY["other"])
    for field_name, _, tier in fields:
        if tier <= 2:
            val = state.get(field_name)
            if val is None or val == "":
                pending.append(field_name)
    return pending


def should_route_to_expert(state: dict, turn_count: int, max_turns: int) -> tuple[bool, str]:
    """
    Routing logic — designed for 4-5 turn intake conversations.

    turn_count = number of user messages sent SO FAR (before current response)
    turn_count=0: first message just received
    turn_count=1: second message just received
    turn_count=2: third message just received

    Routing rules (in priority order):
    1. Sensitive crimes (rape/acid/trafficking) → expert after turn 1
    2. Score >= 90 AND turn >= 2 → expert (all mandatory fields + some optional)
    3. Score >= 70 AND turn >= 3 → expert (good info, enough turns)
    4. Score >= 60 AND turn >= 4 → expert (minimum info, many turns)
    5. turn >= max_turns → force expert
    6. frustrated → expert immediately
    """
    crime_type = state.get("crime_type", "")
    score = calculate_score(state)

    # Rule 1: Sensitive crimes — minimal intake
    if crime_type in IMMEDIATE_EXPERT_CRIMES and turn_count >= 1:
        return True, f"Sensitive crime ({crime_type}) — go to expert immediately"

    # Rule 2: Frustration — always go immediately
    if state.get("frustrated"):
        return True, "User frustrated — routing to expert"

    # Rule 3: All fields collected with enough turns
    if score >= 90 and turn_count >= 2:
        return True, f"Score {score}/100 — all fields collected (turn {turn_count + 1})"

    # Rule 4: Very high score regardless (user gave everything in 2 messages)
    if score >= 95:
        return True, f"Score {score}/100 — excellent context, routing early"

    # Rule 5: Good score after 3 turns
    if score >= 70 and turn_count >= 3:
        return True, f"Score {score}/100 — sufficient context at turn {turn_count + 1}"

    # Rule 6: Minimum viable after 4 turns
    if score >= 60 and turn_count >= 4:
        return True, f"Score {score}/100 — routing after {turn_count + 1} turns"

    # Rule 7: Hard limit
    if turn_count >= max_turns:
        return True, f"Max turns ({max_turns}) reached — forcing expert"

    return False, f"Score {score}/100 — collecting (turn {turn_count + 1} of {max_turns})"
