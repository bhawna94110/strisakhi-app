"""
StriSakhi Emergency Detector — backend/app/emergency/detector.py
LLM-based detection using JSON schema output.
Guaranteed YES/NO via response_format — no keyword lists.
Fast: temperature=0, max_tokens=60, thinking OFF.
"""
import json
import httpx
from app.config import settings

# ─── Emergency Response Data (shown in frontend overlay) ─────────────────────
EMERGENCY_RESPONSES = {
    "legal": {
        "hi": {
            "message": "आप सुरक्षित रहें। अभी तुरंत मदद लें:",
            "helplines": [
                {"number": "181", "label": "महिला हेल्पलाइन (24 घंटे, FREE)"},
                {"number": "100", "label": "पुलिस"},
                {"number": "1091", "label": "महिला संकट"},
                {"number": "15100", "label": "मुफ्त कानूनी सहायता"},
            ]
        },
        "en": {
            "message": "Please stay safe. Get help RIGHT NOW:",
            "helplines": [
                {"number": "181", "label": "Women Helpline (24 hrs, FREE)"},
                {"number": "100", "label": "Police"},
                {"number": "1091", "label": "Women in Distress"},
                {"number": "15100", "label": "Free Legal Aid"},
            ]
        },
        "bn": {
            "message": "আপনি নিরাপদ থাকুন। এখনই সাহায্য নিন:",
            "helplines": [
                {"number": "181", "label": "মহিলা হেল্পলাইন (24 ঘণ্টা, FREE)"},
                {"number": "100", "label": "পুলিশ"},
            ]
        }
    },
    "medical": {
        "hi": {
            "message": "यह EMERGENCY है। तुरंत:",
            "helplines": [
                {"number": "108", "label": "Ambulance (FREE)"},
                {"number": "102", "label": "Maternity Emergency"},
                {"number": "181", "label": "Women Helpline"},
            ]
        },
        "en": {
            "message": "This is a MEDICAL EMERGENCY. Call immediately:",
            "helplines": [
                {"number": "108", "label": "Ambulance (FREE)"},
                {"number": "102", "label": "Maternity Emergency"},
            ]
        },
        "bn": {
            "message": "এটি জরুরি অবস্থা। এখনই ফোন করুন:",
            "helplines": [
                {"number": "108", "label": "অ্যাম্বুলেন্স (FREE)"},
            ]
        }
    },
    "scheme": {
        "hi": {
            "message": "तुरंत मदद लें:",
            "helplines": [
                {"number": "181", "label": "Women Helpline (FREE)"},
                {"number": "1800-419-8588", "label": "Anti-Trafficking"},
                {"number": "1098", "label": "CHILDLINE"},
            ]
        },
        "en": {
            "message": "Immediate help available:",
            "helplines": [
                {"number": "181", "label": "Women Helpline (FREE)"},
                {"number": "1800-419-8588", "label": "Anti-Trafficking"},
            ]
        },
        "bn": {
            "message": "তাৎক্ষণিক সাহায্য:",
            "helplines": [
                {"number": "181", "label": "মহিলা হেল্পলাইন"},
            ]
        }
    }
}

# ─── LLM-based Emergency Detection ──────────────────────────────────────────
EMERGENCY_SCHEMA = {
    "type": "object",
    "properties": {
        "is_emergency": {"type": "boolean"},
        "severity": {"type": "string", "enum": ["critical", "warning", "none"]},
        "reason": {"type": "string"}
    },
    "required": ["is_emergency", "severity", "reason"]
}

EMERGENCY_SYSTEM = (
    "You are a safety classifier for a women's crisis helpline in India. "
    "Determine if the message describes danger happening RIGHT NOW — not past events. "
    "\n\nMark as emergency (YES) ONLY if: "
    "violence is actively happening at this moment, "
    "weapon is present right now, "
    "person cannot escape right now, "
    "or someone is bleeding/injured right now. "
    "\n\nDo NOT mark as emergency (NO) if: "
    "the person is describing past violence ('maara tha', 'maarte hain' = general habit), "
    "asking for legal advice, "
    "describing ongoing situation from a safe place, "
    "or using words like 'mujhe madad chahiye'. "
    "\n\nExamples of YES: 'abhi maar raha hai', 'wo aaj maar raha hai', 'help me he is hitting me now', 'bleeding'. "
    "Examples of NO: 'pati mujhe maarta hai', 'mujhe madad chahiye', 'mera pati mujhe marta hai'."
)


async def detect_emergency_llm(message: str, tab_type: str = "legal") -> dict:
    """
    LLM-based emergency detection.
    Uses YES/NO plain text — response_format caused empty responses.
    Returns: {"is_emergency": bool, "severity": str, "reason": str}
    Fast: temperature=0, max_tokens=10, thinking OFF.
    """
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(
                f"{settings.ollama_base_url}/v1/chat/completions",
                json={
                    "model": "gemma4",
                    "messages": [
                        {"role": "system", "content": EMERGENCY_SYSTEM},
                        {"role": "user", "content": (
                            f"Message: {message}\n\n"
                            "Reply with ONLY one word: YES or NO"
                        )}
                    ],
                    "stream": False,
                    "temperature": 0.0,
                    "max_tokens": 10,
                    "chat_template_kwargs": {"enable_thinking": False},
                }
            )
        raw = r.json()["choices"][0]["message"]["content"].strip().upper()
        is_emergency = raw.startswith("YES")
        return {
            "is_emergency": is_emergency,
            "severity": "critical" if is_emergency else "none",
            "reason": "LLM detected immediate danger" if is_emergency else "no immediate danger"
        }
    except Exception as e:
        return {"is_emergency": False, "severity": "none", "reason": f"detection failed: {e}"}


def get_emergency_response(emergency_type: str, tab_type: str, language: str = "hi") -> dict:
    """Get helplines and message for the emergency overlay."""
    responses = EMERGENCY_RESPONSES.get(tab_type, EMERGENCY_RESPONSES["legal"])
    lang_response = responses.get(language, responses.get("en", {}))
    return {
        "type": emergency_type,
        "message": lang_response.get("message", "Please call for help immediately."),
        "helplines": lang_response.get("helplines", [{"number": "181", "label": "Women Helpline"}]),
        "tab_type": tab_type,
    }


# Keep sync version for backward compat (used in old code)
def detect_emergency(text: str, tab_type: str = "legal") -> tuple[bool, str, str]:
    """Sync wrapper — only used as fallback. Prefer detect_emergency_llm."""
    import re
    # Minimal keyword check as fallback only
    urgent = ["bachao", "maar raha", "khoon", "help me now", "killing me",
              "hitting me now", "bleeding now", "abhi maar"]
    text_lower = text.lower()
    for w in urgent:
        if w in text_lower:
            return True, tab_type, "critical"
    return False, "", "none"
