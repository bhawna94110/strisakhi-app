import re
from typing import Tuple, Optional

# Legal emergency keywords — Hindi + English
LEGAL_EMERGENCY_KEYWORDS = [
    "maar dega", "jaan se maar", "jaan ka khatra", "khoon kar dega",
    "maar diya", "maarne ki dhamki", "abhi maar", "hatya",
    "suicide", "khatam kar loon", "marna chahti", "jeena nahi chahti",
    "kidnap", "kidnapping", "uthakar le gaya", "band kar diya",
    "balatkar", "rape", "chhedbaaad",
    "help", "bachao", "madad karo", "please help",
    "emergency", "urgent help", "police bulao",
    "ghar mein band", "bahar nahi jaane de raha",
    "maar pit raha hai", "abhi maar raha hai",
]

# Medical emergency keywords
MEDICAL_EMERGENCY_KEYWORDS = [
    "behosh", "unconscious", "hosh nahi",
    "saans nahi", "breathing nahi", "dam ghut raha",
    "bahut khoon", "bleeding nahi ruk rahi", "blood nahi ruk raha",
    "seene mein dard", "chest pain", "heart attack",
    "pregnancy mein khoon", "baby hil nahi raha", "9 mahine",
    "akdi ja rahi", "convulsion", "fits aa rahe",
    "zeher kha liya", "tablet kha li", "poison",
    "accident", "bahut chot", "haddee toot",
    "bachcha nahi ro raha", "newborn nahi ro raha",
    "stroke", "paralysis", "ek taraf kaam nahi kar raha",
    "emer", "ambulance", "108",
]

def detect_emergency(text: str, tab_type: str = "legal") -> Tuple[bool, Optional[str], str]:
    """
    Returns: (is_emergency, emergency_type, severity)
    emergency_type: 'immediate_danger' | 'self_harm' | 'medical_critical' | None
    severity: 'critical' | 'high' | 'medium' | 'none'
    """
    text_lower = text.lower()

    keywords = LEGAL_EMERGENCY_KEYWORDS if tab_type == "legal" else MEDICAL_EMERGENCY_KEYWORDS

    matched = [kw for kw in keywords if kw in text_lower]

    if not matched:
        return False, None, "none"

    # Determine type and severity
    critical_patterns = [
        "abhi maar", "behosh", "saans nahi", "bahut khoon",
        "seene mein dard", "zeher kha", "fits aa", "unconscious"
    ]
    self_harm_patterns = ["suicide", "marna chahti", "khatam kar loon", "jeena nahi"]

    is_critical = any(p in text_lower for p in critical_patterns)
    is_self_harm = any(p in text_lower for p in self_harm_patterns)

    if is_critical:
        return True, "immediate_danger", "critical"
    elif is_self_harm:
        return True, "self_harm", "critical"
    elif len(matched) >= 2:
        return True, "immediate_danger", "high"
    else:
        return True, "immediate_danger", "medium"

def get_emergency_response(emergency_type: str, tab_type: str, language: str = "hi") -> dict:
    """Returns emergency UI data based on type"""
    if tab_type == "legal":
        return {
            "banner_text": "⚠️ Aapki baat sunkar lagta hai aap khatre mein hain",
            "banner_hindi": "Aapki suraksha sabse pehle hai",
            "actions": [
                {"label": "🚔 Police (100)", "action": "dial", "number": "100"},
                {"label": "🆘 Women Helpline (181)", "action": "dial", "number": "181"},
                {"label": "⚖️ Free Vakeel Se Baat Karein", "action": "lead_form", "type": "legal"},
            ],
            "message": "Kripya abhi safe jagah par jaayein. Police ya Women Helpline 181 pe call karein."
        }
    else:
        return {
            "banner_text": "🚨 Ye Medical Emergency Lagti Hai",
            "banner_hindi": "Turant medical help lein",
            "actions": [
                {"label": "🚑 Ambulance (108)", "action": "dial", "number": "108"},
                {"label": "🏥 Health Helpline (104)", "action": "dial", "number": "104"},
                {"label": "👨‍⚕️ Doctor Se Baat Karein", "action": "lead_form", "type": "medical"},
            ],
            "message": "Kripya turant 108 pe call karein ya nearest hospital jaayein."
        }
