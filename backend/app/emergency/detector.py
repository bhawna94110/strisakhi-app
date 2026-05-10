"""
StriSakhi Emergency Detector — backend/app/emergency/detector.py
Multilingual emergency keyword detection for all three Sakhis.
Three severity levels: none, warning, critical.
"""
import re

# ─── Emergency Keywords per Sakhi + Language ─────────────────────────────────
EMERGENCY_KEYWORDS = {
    "legal": {
        "critical": [
            # Hindi/Hinglish
            "maar raha hai", "peet raha hai", "jaan se maar", "maarne ki koshish",
            "khoon aa raha", "chaku", "knife", "pistol", "gun", "abhi maar",
            "bachao", "help me", "jaan khatre mein", "bhag nahi sakti",
            "bahut maar", "behosh", "hospital",
            # English
            "hitting me now", "killing me", "threatening to kill", "has a knife",
            "has a weapon", "bleeding now", "can't escape", "locked me in",
            # Bengali
            "maro", "marlo", "khun", "chhuri", "bachao", "help koro",
        ],
        "warning": [
            "roz marta", "roz peeta", "daily abuse", "aaj phir",
            "police bula", "FIR", "ghar se nikaala", "nikaalne ki dhamki",
        ]
    },
    "medical": {
        "critical": [
            # Hindi
            "behosh", "hosh nahi", "bahut khoon", "dauraa pada", "saans nahi aa rahi",
            "hilna band", "aankhon ke aage andhera", "naak se khoon",
            "9 mahine", "dard bahut tej", "baccha nahi hil raha",
            # English
            "unconscious", "not breathing", "heavy bleeding", "fitting", "seizure",
            "baby stopped moving", "can't wake up", "severe chest pain",
            "can't see", "vomiting blood",
            # Bengali
            "behosh", "rokto poRche", "nishwas nite parche na", "khaanchi",
            "shishu nochRache na",
        ],
        "warning": [
            "bahut dard", "bukhar bahut", "ulti band nahi", "dast band nahi",
            "severe pain", "high fever", "can't keep water down",
        ]
    },
    "scheme": {
        "critical": [
            "bhookh", "kuch khane ko nahi", "homeless", "ghar nahi", "raat ko kahin nahi",
            "starving", "no food", "no shelter", "sleeping outside",
            "trafficking", "forced marriage", "kidnap",
        ],
        "warning": []
    }
}

# Emergency response data per Sakhi + language
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
                {"number": "181", "label": "মহিলা হেল্পলাইন (24 ঘণ্টা, বিনামূল্যে)"},
                {"number": "100", "label": "পুলিশ"},
                {"number": "1091", "label": "মহিলা সংকট"},
            ]
        }
    },
    "medical": {
        "hi": {
            "message": "यह EMERGENCY है। तुरंत:",
            "helplines": [
                {"number": "108", "label": "Ambulance (FREE)"},
                {"number": "102", "label": "Maternity Emergency"},
                {"number": "104", "label": "Health Helpline"},
                {"number": "181", "label": "Women Helpline"},
            ]
        },
        "en": {
            "message": "This is a MEDICAL EMERGENCY. Call immediately:",
            "helplines": [
                {"number": "108", "label": "Ambulance (FREE)"},
                {"number": "102", "label": "Maternity Emergency"},
                {"number": "104", "label": "Health Helpline"},
            ]
        },
        "bn": {
            "message": "এটি জরুরি অবস্থা। এখনই ফোন করুন:",
            "helplines": [
                {"number": "108", "label": "অ্যাম্বুলেন্স (বিনামূল্যে)"},
                {"number": "102", "label": "মাতৃত্ব জরুরি"},
            ]
        }
    },
    "scheme": {
        "hi": {
            "message": "আপনি নিরাপদ থাকুন। তাৎক্ষণিক সাহায্য:",
            "helplines": [
                {"number": "181", "label": "Women Helpline (FREE)"},
                {"number": "1800-419-8588", "label": "Anti-Trafficking Helpline"},
                {"number": "1098", "label": "CHILDLINE"},
            ]
        },
        "en": {
            "message": "Immediate help available:",
            "helplines": [
                {"number": "181", "label": "Women Helpline (FREE)"},
                {"number": "1800-419-8588", "label": "Anti-Trafficking"},
                {"number": "1098", "label": "CHILDLINE"},
            ]
        },
        "bn": {
            "message": "তাৎক্ষণিক সাহায্য:",
            "helplines": [
                {"number": "181", "label": "মহিলা হেল্পলাইন"},
                {"number": "1800-419-8588", "label": "মানব পাচার বিরোধী"},
            ]
        }
    }
}


def detect_emergency(text: str, tab_type: str = "legal") -> tuple[bool, str, str]:
    """
    Returns (is_emergency, emergency_type, severity)
    severity: "critical" | "warning" | "none"
    """
    text_lower = text.lower()
    keywords = EMERGENCY_KEYWORDS.get(tab_type, EMERGENCY_KEYWORDS["legal"])

    for word in keywords.get("critical", []):
        if word in text_lower:
            return True, tab_type, "critical"

    for word in keywords.get("warning", []):
        if word in text_lower:
            return True, tab_type, "warning"

    return False, "", "none"


def get_emergency_response(emergency_type: str, tab_type: str, language: str = "hi") -> dict:
    """Get the appropriate emergency response data."""
    responses = EMERGENCY_RESPONSES.get(tab_type, EMERGENCY_RESPONSES["legal"])
    lang_response = responses.get(language, responses.get("en", {}))
    return {
        "type": emergency_type,
        "message": lang_response.get("message", "Please call for help immediately."),
        "helplines": lang_response.get("helplines", [{"number": "181", "label": "Women Helpline"}]),
        "tab_type": tab_type,
    }
