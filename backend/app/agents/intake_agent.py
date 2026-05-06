"""
Intake Agent — Gemma 4 E2B via llama.cpp
Uses OpenAI-compatible /v1/chat/completions endpoint.
Thinking disabled via server flag — responses in ~1-3 seconds.
"""
import requests
import json
from app.config import settings
from app.agents.model_router import calculate_confidence
from typing import AsyncGenerator


async def run_intake_stream(
    conversation_history: list,
    metadata: dict,
    tab_type: str,
    language: str = "hi"
) -> AsyncGenerator[dict, None]:

    system_content = build_intake_system(metadata, tab_type, language)

    messages = [{"role": "system", "content": system_content}]
    for msg in conversation_history[-6:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # OpenAI-compatible payload for llama.cpp
    payload = {
        "model": "gemma4",
        "messages": messages,
        "stream": True,
        "temperature": 0.3,
        "max_tokens": 300,
        "top_p": 0.95,
    }

    full_response = ""

    try:
        r = requests.post(
            f"{settings.ollama_base_url}/v1/chat/completions",
            json=payload,
            stream=True,
            timeout=60
        )

        for line in r.iter_lines():
            if not line:
                continue
            line_str = line.decode() if isinstance(line, bytes) else line
            if not line_str.startswith("data: "):
                continue
            data_str = line_str[6:]
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
                token = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "") or ""
                if token:
                    full_response += token
                    yield {"type": "token", "token": token, "agent": "intake"}
            except:
                continue

    except Exception as e:
        yield {"type": "error", "message": str(e)}
        return

    if not full_response.strip():
        full_response = "Aapki baat samajh aayi. Aap kaun se state mein rehti hain?"
        yield {"type": "token", "token": full_response, "agent": "intake"}

    if "EMERGENCY_DETECTED" in full_response:
        yield {"type": "emergency", "flag": True}
        return

    if "READY_FOR_EXPERT" in full_response:
        yield {"type": "phase_change", "from": "intake", "to": "expert"}
        return

    new_metadata = extract_metadata(full_response, metadata, tab_type)
    if new_metadata != metadata:
        new_confidence = calculate_confidence(new_metadata, tab_type)
        yield {
            "type": "metadata_update",
            "metadata": new_metadata,
            "confidence_score": new_confidence
        }

    yield {"type": "done", "full_response": full_response, "agent": "intake"}


def build_intake_system(metadata: dict, tab_type: str, language: str) -> str:
    collected = json.dumps(metadata, ensure_ascii=False) if metadata else "{}"
    if tab_type == "legal":
        return f"""You are Nyay Vani, a compassionate legal intake assistant for rural Indian women.
Ask ONE question at a time. Be warm and brief — 1-2 sentences only.
Respond in Hindi.
If immediate danger: say EMERGENCY_DETECTED
If enough info collected (location, religion, issue): say READY_FOR_EXPERT
Info so far: {collected}"""
    else:
        return f"""You are Nyay Vani, a compassionate medical intake assistant for rural Indian women.
Ask ONE question at a time. Be warm and brief — 1-2 sentences only.
Respond in Hindi.
If red flag symptoms (unconscious, heavy bleeding, fits): say EMERGENCY_DETECTED
Info so far: {collected}"""


def extract_metadata(response: str, existing: dict, tab_type: str) -> dict:
    updated = existing.copy()
    text = response.lower()
    states = ["uttar pradesh","up","maharashtra","rajasthan","bihar","madhya pradesh",
              "mp","west bengal","karnataka","gujarat","andhra pradesh","tamil nadu",
              "telangana","kerala","punjab","haryana","odisha","jharkhand","assam","delhi"]
    for state in states:
        if state in text and not updated.get("location_state"):
            updated["location_state"] = state.title()
            break
    religions = ["hindu","muslim","christian","sikh","buddhist","jain"]
    for religion in religions:
        if religion in text and not updated.get("religion"):
            updated["religion"] = religion
            break
    issue_keywords = {
        "domestic_violence": ["ghar se nikaala","maar","peet","hinsa","violence"],
        "property": ["zameen","property","land","inheritance"],
        "workplace": ["kaam","job","harassment","salary"],
        "divorce": ["talaq","divorce","separation"],
        "maintenance": ["kharcha","maintenance","alimony"],
        "dowry": ["dahej","dowry"],
    }
    for issue, keywords in issue_keywords.items():
        if any(kw in text for kw in keywords) and not updated.get("issue_type"):
            updated["issue_type"] = issue
            break
    return updated

# ── OVERRIDE: replace extract_metadata function ──────────────────
def extract_metadata(response: str, existing: dict, tab_type: str) -> dict:
    updated = existing.copy()
    text = response.lower()

    # States
    states = ["uttar pradesh","up","maharashtra","rajasthan","bihar","madhya pradesh",
              "mp","west bengal","karnataka","gujarat","andhra pradesh","tamil nadu",
              "telangana","kerala","punjab","haryana","odisha","jharkhand","assam","delhi"]
    for state in states:
        if state in text and not updated.get("location_state"):
            updated["location_state"] = state.title()
            break

    # Religion
    religions = ["hindu","muslim","christian","sikh","buddhist","jain"]
    for religion in religions:
        if religion in text and not updated.get("religion"):
            updated["religion"] = religion
            break

    # Issue type — broad keywords from natural speech
    issue_keywords = {
        "domestic_violence": ["maar","peet","thapad","maara","marta","marti",
                              "ghar se nikaala","nikala","hinsa","violence","laat"],
        "property": ["zameen","property","land","makaan","ghar","inheritance","hissa"],
        "workplace": ["kaam","job","office","harassment","salary","naukar","naukri"],
        "divorce": ["talaq","divorce","alag","separation","chod diya"],
        "maintenance": ["kharcha","maintenance","alimony","paisa nahi","paise"],
        "dowry": ["dahej","dowry","demand"],
    }
    for issue, keywords in issue_keywords.items():
        if any(kw in text for kw in keywords) and not updated.get("issue_type"):
            updated["issue_type"] = issue
            break

    # Urgency — detect from natural speech
    urgent_words = ["maar","peet","thapad","khoon","hospital","dara","dhamki",
                    "jaan","marega","marti","roz","har roz","subah sham","daily"]
    if any(w in text for w in urgent_words) and not updated.get("urgency"):
        updated["urgency"] = "high"

    # Duration hints
    duration_words = ["saal","mahine","hafte","din","lambe","bahut time"]
    if any(w in text for w in duration_words) and not updated.get("duration"):
        updated["duration"] = "chronic"

    return updated