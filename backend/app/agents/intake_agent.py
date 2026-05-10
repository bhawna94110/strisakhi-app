"""
StriSakhi Intake Agent — All Three Sakhis
AI-driven intake: LLM decides what to ask next.
Collects 6 universal parameters through natural conversation.
Supports Hindi, English, Bengali, Hinglish.
"""
import requests
import json
import re
from app.config import settings
from app.agents.model_router import calculate_confidence
from typing import AsyncGenerator

# ─── Language Instructions ────────────────────────────────────────────────────
LANGUAGE_INSTRUCTIONS = {
    "hi": (
        "🔴 CRITICAL: Sirf Devanagari lipi mein jawab do. "
        "KABHI BHI Roman/English script mat use karo Hindi ke liye. "
        "Agar user Hinglish mein likhti hai, phir bhi aap Devanagari mein jawab do."
    ),
    "en": (
        "🔴 CRITICAL: Respond ONLY in English. Never use Hindi or Devanagari script."
    ),
    "bn": (
        "🔴 CRITICAL: Sudhu Bangla lipi te uttor dao. "
        "Kokhono Roman ba Hindi lipi byabohar koro na."
    ),
}

# ─── Empathy Phrases per Language ────────────────────────────────────────────
EMPATHY_PHRASES = {
    "hi": [
        "Yeh sunke bahut dukh hua.",
        "Main samajh sakti hoon aap kitni takleef mein hain.",
        "Aap bilkul akeli nahi hain.",
        "Aapne sahi kiya mujhse baat ki.",
    ],
    "en": [
        "I'm so sorry you're going through this.",
        "You are not alone in this.",
        "You were right to reach out.",
        "This takes courage — I'm here with you.",
    ],
    "bn": [
        "Eta shune khub koshto holo.",
        "Apni ekdom eka non.",
        "Ami apnar pashe achi.",
    ],
}

# ─── Universal Parameters per Sakhi ──────────────────────────────────────────
PARAMS_LEGAL = """
Parameters to collect (collect naturally, don't interrogate):
1. crime_type: domestic_violence | dowry | property | rape | divorce | workplace | stalking | acid_attack | custody | trafficking
2. relationship_to_accused: husband | in_laws | employer | colleague | stranger | family | neighbor
3. marital_status: married | unmarried | divorced | widow | separated
4. urgency: immediate_danger | recent | ongoing | historical
5. state: any Indian state (optional — skip if user reluctant)
6. age: minor | young_adult | adult | senior (only ask if relevant to case)
"""

PARAMS_MEDICAL = """
Parameters to collect (collect naturally, don't interrogate):
1. health_issue: pregnancy | child_illness | mental_health | anaemia | reproductive | injury_dv | postpartum | chronic | other
2. urgency: emergency | urgent_today | this_week | general
3. patient: self | child | baby | elder
4. pregnancy_status: pregnant | postpartum | not_pregnant (only if relevant)
5. age_stage: girl_child | adolescent | reproductive_age | menopausal
6. healthcare_access: near_phc | distant | no_access | private_available
"""

PARAMS_SCHEME = """
Parameters to collect (collect naturally, don't interrogate):
1. life_situation: pregnant | widow | farmer | unemployed | student | domestic_violence | homeless | elderly | entrepreneur | general
2. bpl_status: has_bpl_card | poor_no_card | middle | unknown
3. state: any Indian state (PRIORITY — always ask)
4. documents: has_aadhaar | has_ration_card | has_bank_account
5. marital_status: married | widow | unmarried
6. urgency: immediate_need | planning | curious
"""

# ─── System Prompts per Sakhi ─────────────────────────────────────────────────
SYSTEM_PROMPTS = {
    "legal": """{lang_instruction}

You are Kanoon Sakhi — a warm, knowledgeable legal companion for Indian women.
Think of yourself as a trusted didi who knows Indian law inside out.

YOUR GOAL:
Collect these parameters through natural conversation — NOT like filling a form:
{params}

RULES:
- Ask ONE question per turn — NEVER two questions at once
- Always start with empathy before asking anything
- Use one of these empathy phrases when appropriate: {empathy}
- If user shows frustration ("bas karo", "seedha batao", repeated short answers) → write READY_FOR_EXPERT immediately
- If you have crime_type + urgency + at least 2 other params → write READY_FOR_EXPERT
- NEVER ask for info already shared by the user
- Parameters collected so far: {metadata}

EMERGENCY SIGNALS — write EMERGENCY_DETECTED immediately if you see:
Hindi/Hinglish: maar raha, khoon, abhi, bachao, jaan, maarne wala, hospital, behosh, knife
English: hitting me now, bleeding, happening now, kill me, help me please, unconscious
Bengali: maro, ekhoni, rakto, help koro, behosh

CONVERSATION SO FAR:
{history}

REMINDER: {lang_instruction}""",

    "medical": """{lang_instruction}

You are Sehat Sakhi — a caring health guide for Indian women.
You are like a knowledgeable ASHA worker or ANM — warm, practical, non-judgmental.

YOUR GOAL:
Collect these parameters through natural conversation:
{params}

RULES:
- Ask ONE question per turn — NEVER two
- Always start with empathy about their health concern
- Use one of these empathy phrases when appropriate: {empathy}
- If urgency = emergency → write EMERGENCY_DETECTED immediately
- If user shows frustration → write READY_FOR_EXPERT immediately
- If you have health_issue + urgency + patient → write READY_FOR_EXPERT
- NEVER diagnose. NEVER prescribe medicines by name.
- Parameters collected so far: {metadata}

EMERGENCY SIGNALS — write EMERGENCY_DETECTED immediately:
Hindi: behosh, bahut khoon, dauraa, saans nahi aa rahi, hilna band kar diya, aankhon ke aage andhera, bahut tej dard, 9 mahine
English: unconscious, heavy bleeding, not breathing, fitting, baby stopped moving, severe pain, can't see
Bengali: behosh, rokto poRche, nishwas nite parche na, khaanchi

CONVERSATION SO FAR:
{history}

REMINDER: {lang_instruction}""",

    "scheme": """{lang_instruction}

You are Yojana Sakhi — a friendly guide who helps Indian women access government benefits.
You know every government scheme for women and exactly how to apply.

YOUR GOAL:
Collect these parameters through natural conversation:
{params}

RULES:
- Ask ONE question per turn — NEVER two
- Be warm and encouraging — many women don't know they deserve these benefits
- Use one of these empathy phrases when appropriate: {empathy}
- STATE is priority parameter — ask early
- If you have life_situation + state + bpl_status → write READY_FOR_EXPERT
- If user shows frustration → write READY_FOR_EXPERT immediately
- NEVER say "you don't qualify" — always find at least one scheme
- Parameters collected so far: {metadata}

CONVERSATION SO FAR:
{history}

REMINDER: {lang_instruction}"""
}

# ─── Metadata Extraction ─────────────────────────────────────────────────────
def extract_metadata(text: str, existing: dict, tab_type: str) -> dict:
    updated = existing.copy()
    t = text.lower()

    if tab_type in ("legal", "scheme"):
        # Crime type
        crime_map = {
            "domestic_violence": ["maar", "peet", "thapad", "maara", "marta", "hinsa", "violence", "beat", "hit", "abuse", "dv"],
            "property": ["zameen", "property", "land", "makaan", "inheritance", "hissa", "ghar ka haq", "ancestral"],
            "workplace": ["kaam", "job", "office", "harassment", "salary", "naukri", "boss", "colleague"],
            "divorce": ["talaq", "divorce", "alag", "separation", "chhod diya"],
            "maintenance": ["kharcha", "maintenance", "alimony", "paise nahi deta"],
            "dowry": ["dahej", "dowry", "demand", "maang raha"],
            "rape": ["rape", "sexual", "jabardasti", "dushkarm"],
            "stalking": ["stalk", "peecha", "online", "cyber", "phone", "message"],
            "custody": ["bacche", "custody", "children", "le gaya"],
        }
        for crime, kws in crime_map.items():
            if any(k in t for k in kws) and not updated.get("crime_type"):
                updated["crime_type"] = crime
                break

        # Marital status
        if any(w in t for w in ["pati", "husband", "shaadi", "married", "wife", "biwi"]):
            updated.setdefault("marital_status", "married")
        if any(w in t for w in ["widow", "vidhwa", "pati guzar gaye", "husband died"]):
            updated.setdefault("marital_status", "widow")

        # Urgency
        urgent = ["maar", "peet", "abhi", "aaj", "roz", "daily", "beat", "hitting", "now", "today", "khoon"]
        if any(w in t for w in urgent) and not updated.get("urgency"):
            updated["urgency"] = "high"

        # Relationship
        if any(w in t for w in ["pati", "husband"]):
            updated.setdefault("relationship_to_accused", "husband")
        if any(w in t for w in ["saas", "sasur", "in-laws", "devar"]):
            updated.setdefault("relationship_to_accused", "in_laws")
        if any(w in t for w in ["boss", "manager", "office", "employer"]):
            updated.setdefault("relationship_to_accused", "employer")

    elif tab_type == "medical":
        # Health issue
        health_map = {
            "pregnancy": ["pregnant", "garbhavati", "pregnancy", "9 mahine", "delivery", "prasav"],
            "child_illness": ["baccha", "baby", "child", "bukhar", "fever", "diarrhea", "dast"],
            "mental_health": ["depression", "udaas", "anxious", "dar", "neend", "anxiety", "stress", "tension"],
            "anaemia": ["anaemia", "anemia", "kamzor", "thakan", "fatigue", "pale", "khoon ki kami"],
            "reproductive": ["period", "maasik", "menstrual", "pcod", "pcos", "contraception"],
        }
        for issue, kws in health_map.items():
            if any(k in t for k in kws) and not updated.get("health_issue"):
                updated["health_issue"] = issue
                break

        # Patient
        if any(w in t for w in ["baccha", "child", "baby", "mere bete", "meri beti", "son", "daughter"]):
            updated.setdefault("patient", "child")
        elif any(w in t for w in ["mujhe", "meri", "main", "i have", "i am", "myself"]):
            updated.setdefault("patient", "self")

    # States (universal)
    states = {
        "uttar pradesh": "Uttar Pradesh", "up": "Uttar Pradesh",
        "maharashtra": "Maharashtra", "rajasthan": "Rajasthan",
        "bihar": "Bihar", "madhya pradesh": "Madhya Pradesh",
        "west bengal": "West Bengal", "karnataka": "Karnataka",
        "gujarat": "Gujarat", "andhra pradesh": "Andhra Pradesh",
        "tamil nadu": "Tamil Nadu", "telangana": "Telangana",
        "kerala": "Kerala", "punjab": "Punjab", "haryana": "Haryana",
        "delhi": "Delhi", "odisha": "Odisha", "assam": "Assam",
        "jharkhand": "Jharkhand", "chhattisgarh": "Chhattisgarh",
    }
    for k, v in states.items():
        if k in t and not updated.get("state"):
            updated["state"] = v
            break

    return updated


# ─── Main Intake Function ─────────────────────────────────────────────────────
async def run_intake_stream(
    conversation_history: list,
    metadata: dict,
    tab_type: str,
    language: str = "hi"
) -> AsyncGenerator[dict, None]:

    lang_instruction = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["en"])
    empathy = " / ".join(EMPATHY_PHRASES.get(language, EMPATHY_PHRASES["en"])[:3])
    params = {"legal": PARAMS_LEGAL, "medical": PARAMS_MEDICAL, "scheme": PARAMS_SCHEME}.get(
        tab_type, PARAMS_LEGAL
    )
    prompt_key = tab_type if tab_type in SYSTEM_PROMPTS else "legal"

    history_text = "\n".join([
        f"{'User' if m['role']=='user' else 'Sakhi'}: {m.get('content','')}"
        for m in conversation_history[-8:]
        if m.get("content")
    ])

    system = SYSTEM_PROMPTS[prompt_key].format(
        lang_instruction=lang_instruction,
        params=params,
        empathy=empathy,
        metadata=json.dumps(metadata, ensure_ascii=False),
        history=history_text,
    )

    messages = [{"role": "system", "content": system}]
    for m in conversation_history[-6:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})

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
            if not line:
                continue
            line_str = line.decode() if isinstance(line, bytes) else line
            if not line_str.startswith("data: "):
                continue
            data_str = line_str[6:]
            if data_str == "[DONE]":
                break
            try:
                token = json.loads(data_str)["choices"][0]["delta"].get("content", "") or ""
                if token:
                    full_response += token
                    yield {"type": "token", "token": token, "agent": "intake"}
            except Exception:
                continue
    except Exception as e:
        yield {"type": "error", "message": str(e)}
        return

    if not full_response.strip():
        fallbacks = {
            "hi": "Aapki baat samajh aayi. Aap kis state mein hain?",
            "en": "I understand. Which state are you in?",
            "bn": "Ami bujhechi. Apni kon rajye achen?",
        }
        full_response = fallbacks.get(language, "Please tell me more.")
        yield {"type": "token", "token": full_response, "agent": "intake"}

    # Update metadata from this response + conversation
    last_user = next(
        (m["content"] for m in reversed(conversation_history) if m.get("role") == "user"),
        ""
    )
    new_metadata = extract_metadata(last_user, metadata, tab_type)
    if new_metadata != metadata:
        new_conf = calculate_confidence(new_metadata, tab_type)
        yield {"type": "metadata_update", "metadata": new_metadata, "confidence_score": new_conf}

    # Check for trigger words in response
    if "EMERGENCY_DETECTED" in full_response:
        yield {"type": "emergency", "flag": True}
        return
    if "READY_FOR_EXPERT" in full_response:
        yield {"type": "phase_change", "from": "intake", "to": "expert"}
        return

    yield {"type": "done", "full_response": full_response, "agent": "intake"}
