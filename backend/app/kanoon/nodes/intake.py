"""
Intake Node — Core of the pipeline
Two modes:
1. crime_type unknown → detect crime + extract as much as possible
2. crime_type known → extract next pending field + ask next question

Uses structured LLM output via json_object response_format.
Robust JSON extraction via regex fallback.
"""
import json
import re
import httpx
from app.kanoon.state import KanoonState
from app.kanoon.score import (
    calculate_score, get_next_field,
    get_pending_fields, should_route_to_expert
)
from app.kanoon.prompts import LANG_INSTRUCTION, INTAKE_QUESTIONS
from app.config import settings

# ─── Prompt builders ──────────────────────────────────────────────────────────

def _build_crime_detection_prompt(state: KanoonState) -> str:
    lang = state.get("language", "hi")
    lang_instr = LANG_INSTRUCTION.get(lang, LANG_INSTRUCTION["en"])
    message = state.get("user_message_processed", "")
    history = state.get("history", [])
    history_text = "\n".join([
        f"{'User' if m['role']=='user' else 'Sakhi'}: {m['content']}"
        for m in history[-4:] if m.get("content")
    ])

    lang_name = "Devanagari Hindi only — never Roman/English script for Hindi words" if lang == "hi" else "English only" if lang == "en" else "Bengali script only"

    return f"""{lang_instr}

You are Kanoon Sakhi's intake specialist — a warm, patient listener.
Your job: understand what legal problem this woman has and extract key details.

CONVERSATION SO FAR:
{history_text}

CURRENT MESSAGE: {message}

Extract what you can from this message. Respond in JSON only:
{{
  "crime_type": "domestic_violence|property|dowry|rape|divorce|maintenance|workplace|stalking|acid_attack|trafficking|custody|other",
  "confidence": 0.0-1.0,
  "urgency": "immediate|recent|ongoing|historical|null",
  "relationship_to_accused": "extracted value or null",
  "other_context": "any other important detail mentioned or null",
  "empathy_message": "1 warm sentence acknowledging her pain — write in {lang_name}",
  "first_question": "the most important missing question to ask next — write in {lang_name}"
}}

crime_type options:
- domestic_violence: husband/family beating, abuse, threats, eviction by husband/inlaws
- property: land/house from father/ancestors, inheritance, brother denying share (NOT eviction by husband)
- dowry: dowry demands, harassment for dowry, stridhan not returned
- maintenance: wants money from husband without or after divorce
- divorce: wants to end marriage, separation
- workplace: boss/colleague harassment, POSH Act issues
- stalking: being followed, online harassment, threatening messages
- rape: sexual assault
- custody: child custody dispute
- other: if unclear

IMPORTANT: husband beating + evicting from home → domestic_violence (NOT property)
IMPORTANT: Adultery by husband + violence → domestic_violence

{lang_instr}"""


def _build_field_extraction_prompt(
    state: KanoonState,
    next_field: str,
) -> str:
    lang = state.get("language", "hi")
    lang_instr = LANG_INSTRUCTION.get(lang, LANG_INSTRUCTION["en"])
    message = state.get("user_message_processed", "")
    crime_type = state.get("crime_type", "")
    history = state.get("history", [])
    history_text = "\n".join([
        f"{'User' if m['role']=='user' else 'Sakhi'}: {m['content']}"
        for m in history[-4:] if m.get("content")
    ])

    # Get the next question from question bank
    next_q_data = INTAKE_QUESTIONS.get(next_field)
    if next_q_data:
        next_q = next_q_data[1] if lang == "hi" else next_q_data[2]  # hi or en
        next_q_why = next_q_data[3]
    else:
        next_q = "Kya aap aur kuch batana chahti hain?"
        next_q_why = "additional context"

    # Already collected fields summary
    collected = state.get("fields_collected", [])
    case_summary = {f: state.get(f) for f in collected if state.get(f)}

    lang_name = "Devanagari Hindi" if lang == "hi" else "English" if lang == "en" else "Bengali"

    return f"""{lang_instr}

You are Kanoon Sakhi's intake specialist.
Crime type identified: {crime_type}
Case file so far: {json.dumps(case_summary, ensure_ascii=False)}

CONVERSATION:
{history_text}

LATEST USER MESSAGE: {message}

TASK:
1. Extract the value of field "{next_field}" from the user's message if present
2. Also check if the user mentioned anything about other fields
3. Detect if user seems frustrated (short angry replies, "bas karo", CAPS, one word answers repeatedly)

Respond in JSON only:
{{
  "extracted_field": "{next_field}",
  "extracted_value": "the extracted value or null if not mentioned",
  "confidence": 0.0-1.0,
  "also_mentioned": {{
    "field_name": "value"
  }},
  "frustrated": false,
  "other_context_addition": "any new important detail NOT captured in above fields or null",
  "next_question_{lang}": "{next_q}",
  "next_question_why": "{next_q_why}"
}}

Important: extracted_value must be the actual answer (e.g. "ongoing", "husband", "yes"),
not a description. If user did not answer this field, set extracted_value to null.

{lang_instr}"""


# ─── Main intake node ─────────────────────────────────────────────────────────

async def intake_node(state: KanoonState) -> dict:
    """
    Core intake logic:
    - If no crime_type: detect it + extract what we can
    - If crime_type known: extract next field + ask next question
    - Always recalculate score and check routing
    """
    lang = state.get("language", "hi")
    crime_type = state.get("crime_type")
    turn_count = state.get("turn_count", 0)
    max_turns = state.get("max_turns", 10)
    fields_collected = list(state.get("fields_collected", []))
    updates = {}

    # ── Mode 1: Detect crime type ─────────────────────────────────────────────
    if not crime_type:
        prompt = _build_crime_detection_prompt(state)
        result = await _llm_json_call(prompt)

        if result:
            detected_crime = result.get("crime_type", "other")
            confidence = result.get("confidence", 0.5)

            updates["crime_type"] = detected_crime
            if result.get("urgency") and result["urgency"] != "null":
                updates["urgency"] = result["urgency"]
                if "urgency" not in fields_collected:
                    fields_collected.append("urgency")
            if result.get("relationship_to_accused"):
                updates["relationship_to_accused"] = result["relationship_to_accused"]
                if "relationship_to_accused" not in fields_collected:
                    fields_collected.append("relationship_to_accused")
            if result.get("other_context"):
                updates["other_context"] = result.get("other_context")
                if "other_context" not in fields_collected:
                    fields_collected.append("other_context")

            # Build empathy + first question message
            # Keys are now "empathy_message" and "first_question" (simplified)
            empathy = (
                result.get("empathy_message") or
                result.get(f"empathy_message_{lang}") or ""
            )
            first_q = (
                result.get("first_question") or
                result.get(f"first_question_{lang}") or ""
            )

            if not first_q:
                # Fallback: get next field from question bank
                merged = {**state, **updates, "fields_collected": fields_collected}
                next_field = get_next_field(merged)
                if next_field and next_field in INTAKE_QUESTIONS:
                    qdata = INTAKE_QUESTIONS[next_field]
                    first_q = qdata[1] if lang == "hi" else qdata[2]

            message = f"{empathy}\n\n{first_q}".strip() if empathy else first_q
            updates["current_question"] = message

        else:
            # LLM failed — ask generic opening question
            fallback = {
                "hi": "मुझे समझ आई। क्या आप मुझे बताएंगी कि यह किस तरह की समस्या है — घरेलू हिंसा, संपत्ति, कार्यस्थल, या कुछ और?",
                "en": "I understand. Can you tell me what kind of problem this is — domestic violence, property, workplace, or something else?",
                "bn": "বুঝলাম। এটা কি ধরনের সমস্যা — পারিবারিক হিংসা, সম্পত্তি, কর্মক্ষেত্র?",
            }
            updates["current_question"] = fallback.get(lang, fallback["en"])

    # ── Mode 2: Extract next field ────────────────────────────────────────────
    else:
        # Merge current updates into state snapshot for scoring
        current_state = {**state, **updates, "fields_collected": fields_collected}
        next_field = get_next_field(current_state)

        if next_field:
            prompt = _build_field_extraction_prompt(state, next_field)
            result = await _llm_json_call(prompt)

            if result:
                # Extract the target field
                extracted_val = result.get("extracted_value")
                if extracted_val and extracted_val != "null":
                    updates[next_field] = extracted_val
                    if next_field not in fields_collected:
                        fields_collected.append(next_field)

                # Extract any bonus fields mentioned
                also_mentioned = result.get("also_mentioned", {})
                for bonus_field, bonus_val in also_mentioned.items():
                    if bonus_val and bonus_val != "null" and bonus_field in state:
                        updates[bonus_field] = bonus_val
                        if bonus_field not in fields_collected:
                            fields_collected.append(bonus_field)

                # Append to other_context if new info
                oc_addition = result.get("other_context_addition")
                if oc_addition:
                    existing_oc = state.get("other_context", "") or ""
                    updates["other_context"] = (existing_oc + " " + oc_addition).strip()

                # Frustration detection
                if result.get("frustrated"):
                    updates["frustrated"] = True

                # Next question to ask
                q_key = f"next_question_{lang}"
                next_q = result.get(q_key, "")
                if not next_q:
                    # Fallback to question bank
                    merged2 = {**state, **updates, "fields_collected": fields_collected}
                    nf2 = get_next_field(merged2)
                    if nf2 and nf2 in INTAKE_QUESTIONS:
                        qdata = INTAKE_QUESTIONS[nf2]
                        next_q = qdata[1] if lang == "hi" else qdata[2]

                updates["current_question"] = next_q

        else:
            # All fields collected — go to expert
            updates["go_to_expert"] = True

    # ── Update fields_collected + score ───────────────────────────────────────
    updates["fields_collected"] = fields_collected

    merged_state = {**state, **updates}
    new_score = calculate_score(merged_state)
    updates["readiness_score"] = new_score
    updates["fields_pending"] = get_pending_fields(merged_state)

    # ── Check routing ─────────────────────────────────────────────────────────
    should_expert, reason = should_route_to_expert(merged_state, turn_count, max_turns)
    if should_expert:
        updates["go_to_expert"] = True

    return updates


async def _llm_json_call(prompt: str) -> dict:
    """Make LLM call and robustly extract JSON from response."""
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            r = await client.post(
                f"{settings.ollama_base_url}/v1/chat/completions",
                json={
                    "model": "gemma4",
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "temperature": 0.3,
                    "max_tokens": 500,
                    "chat_template_kwargs": {"enable_thinking": False},
                    "response_format": {"type": "json_object"},
                }
            )
        raw = r.json()["choices"][0]["message"]["content"].strip()

        # Robust JSON extraction
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {}

    except Exception as e:
        import logging
        logging.getLogger("strisakhi").warning(f"Intake LLM call failed: {e}")
        return {}
