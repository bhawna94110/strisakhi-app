"""
Intake Agent — language-aware, uses session language for prompts
"""
import requests
import json
from app.config import settings
from app.agents.model_router import calculate_confidence
from typing import AsyncGenerator

LANGUAGE_INSTRUCTIONS = {
    "hi": "Respond ONLY in Hindi using Devanagari script. Never use Roman/English script for Hindi words.",
    "en": "Respond ONLY in English.",
    "bn": "Respond ONLY in Bengali using Bengali script.",
    "ta": "Respond ONLY in Tamil using Tamil script.",
    "te": "Respond ONLY in Telugu using Telugu script.",
}

def get_lang_instruction(lang: str) -> str:
    return LANGUAGE_INSTRUCTIONS.get(lang, "Respond in the user's language.")


async def run_intake_stream(
    conversation_history: list,
    metadata: dict,
    tab_type: str,
    language: str = "hi"
) -> AsyncGenerator[dict, None]:

    lang_instruction = get_lang_instruction(language)
    collected = json.dumps(metadata, ensure_ascii=False) if metadata else "{}"

    if tab_type in ("legal", "scheme"):
        system = f"""You are StriSakhi's Kanoon Sakhi, a compassionate legal intake assistant for Indian women.
{lang_instruction}
Ask ONE question at a time. Be warm and brief — 1-2 sentences only.
If immediate danger detected: respond with EMERGENCY_DETECTED
If enough info collected (location, issue type, urgency): respond with READY_FOR_EXPERT
Info collected so far: {collected}"""
    else:
        system = f"""You are StriSakhi's Sehat Sakhi, a compassionate medical intake assistant for Indian women.
{lang_instruction}
Ask ONE question at a time. Be warm and brief — 1-2 sentences only.
If red flag symptoms (unconscious, heavy bleeding, fits): respond with EMERGENCY_DETECTED
Info collected so far: {collected}"""

    messages = [{"role": "system", "content": system}]
    for msg in conversation_history[-6:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

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
            json=payload, stream=True, timeout=60
        )
        for line in r.iter_lines():
            if not line: continue
            line_str = line.decode() if isinstance(line, bytes) else line
            if not line_str.startswith("data: "): continue
            data_str = line_str[6:]
            if data_str == "[DONE]": break
            try:
                token = json.loads(data_str)["choices"][0]["delta"].get("content", "") or ""
                if token:
                    full_response += token
                    yield {"type": "token", "token": token, "agent": "intake"}
            except: continue
    except Exception as e:
        yield {"type": "error", "message": str(e)}
        return

    if not full_response.strip():
        fallback = {
            "hi": "आपकी बात समझ आई। आप किस राज्य में रहती हैं?",
            "en": "I understand. Which state do you live in?",
            "bn": "আমি বুঝতে পেরেছি। আপনি কোন রাজ্যে থাকেন?",
        }
        full_response = fallback.get(language, "Please tell me more.")
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
        yield {"type": "metadata_update", "metadata": new_metadata, "confidence_score": new_confidence}

    yield {"type": "done", "full_response": full_response, "agent": "intake"}


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
        "domestic_violence": ["maar","peet","thapad","maara","marta","hinsa","violence","beat","hit","abuse"],
        "property": ["zameen","property","land","makaan","inheritance","hissa"],
        "workplace": ["kaam","job","office","harassment","salary","naukri"],
        "divorce": ["talaq","divorce","alag","separation"],
        "maintenance": ["kharcha","maintenance","alimony","paise"],
        "dowry": ["dahej","dowry"],
    }
    for issue, keywords in issue_keywords.items():
        if any(kw in text for kw in keywords) and not updated.get("issue_type"):
            updated["issue_type"] = issue
            break
    urgent = ["maar","peet","thapad","khoon","hospital","dara","dhamki","roz","daily","subah sham","beat","hit"]
    if any(w in text for w in urgent) and not updated.get("urgency"):
        updated["urgency"] = "high"
    return updated
