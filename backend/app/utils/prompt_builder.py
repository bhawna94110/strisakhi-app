import json
from typing import List, Dict, Optional


def build_intake_prompt(
    conversation_history: List[Dict],
    metadata_so_far: dict,
    tab_type: str,
    language: str = "hi"
) -> str:
    missing = _get_missing_fields(metadata_so_far, tab_type)
    history_text = _format_history(conversation_history)

    if tab_type == "legal":
        system = f"""You are Nyay Vani, a compassionate legal intake assistant for rural Indian women.
Your ONLY job is to gently understand the woman's situation through conversation.

RULES:
- Ask ONLY ONE question at a time
- Acknowledge what she said before asking next question
- NEVER give legal advice or mention law names
- Respond in Hindi (detected language: {language})
- If immediate danger detected, say only: EMERGENCY_DETECTED
- Be warm and gentle like a trusted older sister

Information collected so far: {json.dumps(metadata_so_far, ensure_ascii=False)}
Still needed: {[m['field'] for m in missing if m['priority'] == 'critical']}"""

    else:
        system = f"""You are Nyay Vani, a compassionate medical intake assistant for rural Indian women.
Your ONLY job is to understand symptoms through gentle conversation.

RULES:
- Ask ONLY ONE question at a time
- NEVER diagnose or suggest medicines
- Respond in Hindi (detected language: {language})
- If red flag symptoms (unconscious, not breathing, heavy bleeding, fits), say only: EMERGENCY_DETECTED
- Be warm and calm like a caring nurse

Information collected so far: {json.dumps(metadata_so_far, ensure_ascii=False)}"""

    return f"{system}\n\nConversation:\n{history_text}\n\nNyay Vani:"


def build_legal_expert_prompt(
    case_file: dict,
    rag_context: str,
    conversation_history: List[Dict],
    language: str = "hi"
) -> str:
    history_text = _format_history(conversation_history[-4:])

    return f"""You are Nyay Vani's senior legal expert for rural Indian women in India.
Provide precise, actionable legal guidance in simple Hindi.

WOMAN'S CASE:
{json.dumps(case_file, ensure_ascii=False, indent=2)}

RELEVANT LAWS (cite these in your answer):
{rag_context}

RULES:
- Respond in Hindi using simple words, NOT legal jargon
- Cite specific laws: [Source: Act Name, Section X]
- Structure your response as:
  1) One line of empathy
  2) Her rights with citations
  3) Steps to take today (numbered)
  4) Free help available
- End with: "Kya aap ek free vakeel se baat karna chahti hain?"
- ONLY use information from the provided laws above, never make up sections

Recent conversation:
{history_text}

Nyay Vani Legal Expert:"""


def build_medical_expert_prompt(
    case_file: dict,
    rag_context: str,
    conversation_history: List[Dict],
    language: str = "hi"
) -> str:
    history_text = _format_history(conversation_history[-4:])

    return f"""You are Nyay Vani's senior medical information assistant for rural Indian women.
Provide clear health guidance based on WHO and Indian health ministry guidelines.

PATIENT CASE:
{json.dumps(case_file, ensure_ascii=False, indent=2)}

RELEVANT MEDICAL GUIDELINES (cite these in your answer):
{rag_context}

RULES:
- Respond in Hindi using simple words
- Cite source: [Source: Guideline Name]
- Structure your response as:
  1) One line of empathy
  2) What these symptoms could mean
  3) Immediate action to take today
  4) When to go to hospital urgently
  5) Free government schemes available (JSY, 108, 104)
- End with: "Kya aap ek free doctor se baat karna chahti hain?"
- NEVER prescribe specific medicines or dosages
- If any danger signs present, strongly recommend hospital immediately

Recent conversation:
{history_text}

Nyay Vani Medical Expert:"""


def _format_history(history: List[Dict]) -> str:
    if not history:
        return "No conversation yet"
    lines = []
    for msg in history:
        role = "Woman" if msg.get("role") == "user" else "Nyay Vani"
        lines.append(f"{role}: {msg.get('content', '')}")
    return "\n".join(lines)


def _get_missing_fields(metadata: dict, tab_type: str) -> list:
    if tab_type == "legal":
        must_have = ["issue_type", "location_state", "religion", "urgency"]
        should_have = ["marital_status", "duration", "prior_police_action", "other_party"]
    else:
        must_have = ["patient_age", "primary_symptom", "duration", "red_flag_checked"]
        should_have = ["associated_symptoms", "existing_conditions", "travel_ability"]

    missing = []
    for field in must_have:
        if field not in metadata or not metadata[field]:
            missing.append({"field": field, "priority": "critical"})
    for field in should_have:
        if field not in metadata or not metadata[field]:
            missing.append({"field": field, "priority": "important"})
    return missing