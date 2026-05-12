"""
StriSakhi Intake Agent — Kanoon Sakhi
Structured JSON output via response_format schema.
LLM extracts parameters + decides readiness in one call.
Supports Hindi, English, Bengali, Hinglish.
"""
import json
import httpx
from app.config import settings
from app.agents.model_router import calculate_readiness_score
from typing import AsyncGenerator

# ─── Language Config ──────────────────────────────────────────────────────────
LANGUAGE_CONFIG = {
    "hi": {
        "instruction": (
            "🔴 CRITICAL LANGUAGE RULE: "
            "Sirf Devanagari lipi mein jawab do. "
            "KABHI BHI Roman/English script mat use karo Hindi shabdon ke liye. "
            "Agar user Hinglish mein likhti hai, aap phir bhi Devanagari mein jawab do."
        ),
    },
    "en": {
        "instruction": (
            "🔴 CRITICAL LANGUAGE RULE: "
            "Respond ONLY in English. "
            "Never use Hindi, Devanagari, or any other script."
        ),
    },
    "bn": {
        "instruction": (
            "🔴 CRITICAL LANGUAGE RULE: "
            "Sudhu Bangla lipi te uttor dao. "
            "Roman ba Hindi lipi kokhono byabohar koro na."
        ),
    },
}

# ─── Crime-specific Layer 3 parameters ───────────────────────────────────────
CRIME_EXTRA_PARAMS = {
    "domestic_violence": "marriage_date, has_children (bool), living_situation (joint/separate), financial_dependence (bool)",
    "dowry":             "marriage_date, has_children (bool), living_situation, financial_dependence (bool)",
    "property":          "property_type (agricultural/residential/ancestral), father_alive (bool), religion, will_exists (bool/unknown)",
    "divorce":           "marriage_date, has_children (bool), husband_income_estimate, grounds (cruelty/desertion/adultery/other)",
    "maintenance":       "marriage_date, has_children (bool), husband_income_estimate",
    "workplace":         "company_size_over_10 (bool), accused_designation (boss/colleague/client), incident_type (physical/verbal/other)",
    "rape":              "time_of_incident, relationship_to_accused — ONLY these 2, then ready_for_expert=true",
    "acid_attack":       "time_of_incident — ONLY this, then ready_for_expert=true immediately",
    "trafficking":       "time_of_incident — ONLY this, then ready_for_expert=true immediately",
    "stalking":          "medium (online/physical/both), duration, previous_complaints (bool)",
    "custody":           "marriage_date, children_ages, current_custody_arrangement",
}

# ─── Response schema (guaranteed via response_format) ─────────────────────────
INTAKE_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {
            "type": "string",
            "description": "What to say to the user — warm, one question only"
        },
        "extracted": {
            "type": "object",
            "properties": {
                "crime_type":              {"type": ["string", "null"]},
                "urgency":                 {"type": ["string", "null"]},
                "relationship_to_accused": {"type": ["string", "null"]},
                "state":                   {"type": ["string", "null"]},
                "has_children":            {"type": ["boolean", "null"]},
                "duration":                {"type": ["string", "null"]},
                "others_involved":         {"type": ["boolean", "null"]},
                "previous_complaints":     {"type": ["boolean", "null"]},
                "other_context":           {"type": ["string", "null"]},
                "marriage_date":           {"type": ["string", "null"]},
                "property_type":           {"type": ["string", "null"]},
                "company_size_over_10":    {"type": ["boolean", "null"]},
            },
        },
        "ready_for_expert": {"type": "boolean"},
        "frustrated":        {"type": "boolean"},
        "readiness_score":   {"type": "integer"},
    },
    "required": ["message", "extracted", "ready_for_expert", "frustrated", "readiness_score"]
}

# ─── Build system prompt ──────────────────────────────────────────────────────
def build_intake_system(language: str, metadata: dict, turn: int, max_turns: int) -> str:
    lang = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["en"])
    lang_instruction = lang["instruction"]
    crime_type = metadata.get("crime_type", "")
    extra = CRIME_EXTRA_PARAMS.get(crime_type, "")
    extra_section = f"\nCRIME-SPECIFIC PARAMETERS (since crime_type={crime_type}):\n{extra}" if extra else ""
    score = calculate_readiness_score(metadata)

    return f"""{lang_instruction}

You are Kanoon Sakhi's intake specialist — a warm, patient listener.
Your ONLY job: collect information through gentle conversation.
Do NOT give legal advice. Do NOT mention specific laws or sections.
Think of yourself as a trusted older sister who listens carefully
before calling the right expert to help.

PARAMETERS TO COLLECT:
- crime_type: domestic_violence | property | dowry | rape | divorce |
              maintenance | workplace | stalking | acid_attack | trafficking | other
- urgency: immediate | recent | ongoing | historical
- relationship_to_accused: husband | in_laws | employer | colleague | stranger | family | other
- state: which Indian state
- has_children: true | false
- duration: how long this has been happening
- others_involved: are others besides primary accused involved
- previous_complaints: has she complained to police/court before
- other_context: anything else important{extra_section}

CURRENT CASE FILE (already collected — do NOT ask again):
{json.dumps(metadata, ensure_ascii=False)}

TURN: {turn} of {max_turns} | READINESS SCORE: {score}/100

READY FOR EXPERT WHEN:
- score >= 90 (all 3 mandatory: crime_type + urgency + relationship)
- score >= 60 AND turn >= 2
- turn >= {max_turns}
- user shows frustration (short angry replies, "bas karo", CAPS, repeated same answer)
- crime_type is rape, acid_attack, or trafficking (go after turn 1)

RULES:
- Ask ONE question per turn — never two
- Turn 1: start with ONE empathy sentence acknowledging her pain, then ask the most important MISSING mandatory parameter
- If user is vague — ask ONE gentle clarifying question
- NEVER ask for info already in the case file above

OUTPUT MUST BE VALID JSON AND NOTHING ELSE — NO MARKDOWN, NO EXPLANATION, NO CODE FENCES.
RESPOND IN THIS EXACT JSON FORMAT:
{{
  "message": "what to say to user in their language",
  "extracted": {{
    "crime_type": null,
    "urgency": null,
    "relationship_to_accused": null,
    "state": null,
    "has_children": null,
    "duration": null,
    "others_involved": null,
    "previous_complaints": null,
    "other_context": null,
    "marriage_date": null,
    "property_type": null,
    "company_size_over_10": null
  }},
  "ready_for_expert": false,
  "frustrated": false,
  "readiness_score": 0
}}

FINAL REMINDER: {lang_instruction}"""


# ─── Main intake function ─────────────────────────────────────────────────────
async def run_intake(
    conversation_history: list,
    metadata: dict,
    language: str = "hi",
    turn: int = 1,
    max_turns: int = 10,
) -> dict:
    """
    Single non-streaming intake call.
    Returns parsed dict with: message, extracted params, ready_for_expert, frustrated, readiness_score
    """
    system = build_intake_system(language, metadata, turn, max_turns)

    # Build messages from history (last 6 turns only)
    messages = [{"role": "system", "content": system}]
    for m in conversation_history[-6:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            r = await client.post(
                f"{settings.ollama_base_url}/v1/chat/completions",
                json={
                    "model": "gemma4",
                    "messages": messages,
                    "stream": False,
                    "temperature": 0.3,
                    "max_tokens": 400,
                    "chat_template_kwargs": {"enable_thinking": False},
                    # json_object is softer than json_schema — forces JSON without schema
                    # If this still returns empty, the regex fallback below handles it
                    "response_format": {"type": "json_object"},
                }
            )
        raw = r.json()["choices"][0]["message"]["content"].strip()

        # Robust JSON extraction — finds first { ... } regardless of wrapping
        # Handles: plain JSON, ```json...```, "Here is the JSON:\n{...}", etc.
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object found in response: {raw[:100]}")
        result = json.loads(match.group())

        # Merge extracted params into metadata (only non-null values)
        extracted = result.get("extracted", {})
        updated_metadata = {**metadata}
        for k, v in extracted.items():
            if v is not None:
                updated_metadata[k] = v

        # Recalculate score with updated metadata
        score = calculate_readiness_score(updated_metadata)
        result["readiness_score"] = score
        result["updated_metadata"] = updated_metadata
        return result

    except Exception as e:
        # Log what the model actually returned so we can debug
        import logging
        logging.getLogger("strisakhi").warning(
            f"Intake JSON parse failed: {type(e).__name__}: {e}"
        )
        fallbacks = {
            "hi": "समझ गई। क्या आप बता सकती हैं कि यह कब से हो रहा है?",
            "en": "I understand. Can you tell me how long this has been happening?",
            "bn": "বুঝলাম। এটি কতদিন ধরে হচ্ছে?",
        }
        return {
            "message": fallbacks.get(language, fallbacks["en"]),
            "extracted": {},
            "ready_for_expert": False,
            "frustrated": False,
            "readiness_score": calculate_readiness_score(metadata),
            "updated_metadata": metadata,
            "error": str(e),
        }


# ─── Streaming wrapper (for SSE compatibility with legal.py) ─────────────────
async def run_intake_stream(
    conversation_history: list,
    metadata: dict,
    tab_type: str,
    language: str = "hi",
    turn: int = 1,
    max_turns: int = 10,
) -> AsyncGenerator[dict, None]:
    """
    Streaming wrapper around run_intake for SSE compatibility.
    Yields token events then metadata_update and phase_change events.
    """
    result = await run_intake(
        conversation_history, metadata, language, turn, max_turns
    )

    message = result.get("message", "")
    updated_metadata = result.get("updated_metadata", metadata)
    score = result.get("readiness_score", 0)
    ready = result.get("ready_for_expert", False)
    frustrated = result.get("frustrated", False)

    # Stream message token by token
    for char in message:
        yield {"type": "token", "token": char, "agent": "intake"}

    # Always emit metadata update
    yield {
        "type": "metadata_update",
        "metadata": updated_metadata,
        "confidence_score": score,
    }

    # Phase change if ready
    if ready or frustrated:
        yield {
            "type": "phase_change",
            "from": "intake",
            "to": "expert",
            "reason": "frustrated" if frustrated else f"score {score}",
        }

    yield {
        "type": "done",
        "full_response": message,
        "agent": "intake",
    }
