"""
Intake Agent — Uses Gemma 4 E2B
Uses requests library with /api/generate exactly like the working Streamlit script.
"""
import requests
from app.config import settings
from app.utils.prompt_builder import build_intake_prompt
from app.agents.model_router import calculate_confidence
from typing import AsyncGenerator


async def run_intake_stream(
    conversation_history: list,
    metadata: dict,
    tab_type: str,
    language: str = "hi"
) -> AsyncGenerator[dict, None]:

    # Build prompt using same format as working Streamlit script
    system_prompt = build_intake_system_prompt(metadata, tab_type, language)
    
    # Get last user message
    last_user_msg = ""
    for msg in reversed(conversation_history):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    full_prompt = f"{system_prompt}\nUser: {last_user_msg}\nNyay Vani:"

    payload = {
        "model": settings.intake_model,
        "prompt": full_prompt,
        "stream": False
    }

    try:
        response = requests.post(
            f"{settings.ollama_base_url}/api/generate",
            json=payload,
            timeout=180
        )
        full_response = response.json().get("response", "") or ""
    except Exception as e:
        yield {"type": "error", "message": str(e)}
        return

    if not full_response.strip():
        full_response = "Aapki baat samajh aayi. Kya aap mujhe bata sakti hain aap kaun se state mein rehti hain?"

    # Stream word by word for frontend animation
    for word in full_response.split(" "):
        yield {"type": "token", "token": word + " ", "agent": "intake"}

    # Check special signals
    if "EMERGENCY_DETECTED" in full_response:
        yield {"type": "emergency", "flag": True}
        return

    if "READY_FOR_EXPERT" in full_response:
        yield {"type": "phase_change", "from": "intake", "to": "expert"}
        return

    # Extract metadata
    new_metadata = extract_metadata_from_response(full_response, metadata, tab_type)
    if new_metadata != metadata:
        new_confidence = calculate_confidence(new_metadata, tab_type)
        yield {
            "type": "metadata_update",
            "metadata": new_metadata,
            "confidence_score": new_confidence
        }

    yield {"type": "done", "full_response": full_response, "agent": "intake"}


def build_intake_system_prompt(metadata: dict, tab_type: str, language: str) -> str:
    import json
    if tab_type == "legal":
        return f"""You are Nyay Vani, a compassionate legal intake assistant for rural Indian women.
Your ONLY job is to gently understand the woman's situation before connecting her to legal guidance.
Ask ONE question at a time. Be warm and gentle like a trusted older sister.
Never give legal advice. Respond in Hindi.
If immediate danger, say: EMERGENCY_DETECTED
If enough info collected, say: READY_FOR_EXPERT
Info collected: {json.dumps(metadata, ensure_ascii=False)}"""
    else:
        return f"""You are Nyay Vani, a compassionate medical intake assistant for rural Indian women.
Your ONLY job is to understand symptoms through gentle conversation.
Ask ONE question at a time. Be warm and calm like a caring nurse.
Never diagnose or suggest medicines. Respond in Hindi.
If red flag symptoms (unconscious, not breathing, heavy bleeding), say: EMERGENCY_DETECTED
Info collected: {json.dumps(metadata, ensure_ascii=False)}"""


def extract_metadata_from_response(response: str, existing: dict, tab_type: str) -> dict:
    updated = existing.copy()
    text = response.lower()

    states = [
        "uttar pradesh", "up", "maharashtra", "rajasthan", "bihar",
        "madhya pradesh", "mp", "west bengal", "karnataka", "gujarat",
        "andhra pradesh", "tamil nadu", "telangana", "kerala", "punjab",
        "haryana", "odisha", "jharkhand", "assam", "delhi"
    ]
    for state in states:
        if state in text and not updated.get("location_state"):
            updated["location_state"] = state.title()
            break

    religions = ["hindu", "muslim", "christian", "sikh", "buddhist", "jain"]
    for religion in religions:
        if religion in text and not updated.get("religion"):
            updated["religion"] = religion
            break

    issue_keywords = {
        "domestic_violence": ["ghar se nikaala", "maar", "peet", "hinsa", "violence", "evict"],
        "property": ["zameen", "property", "land", "inheritance", "succession"],
        "workplace": ["kaam", "job", "employer", "harassment", "salary", "wages"],
        "divorce": ["talaq", "divorce", "separation", "alag"],
        "maintenance": ["kharcha", "maintenance", "alimony", "nafqa"],
        "dowry": ["dahej", "dowry"],
    }
    for issue, keywords in issue_keywords.items():
        if any(kw in text for kw in keywords) and not updated.get("issue_type"):
            updated["issue_type"] = issue
            break

    return updated