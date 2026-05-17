"""
Expert Response Node — Streaming
Builds frozen v1.1 prompt from state + RAG context.
Returns full response (streaming handled by graph.py via astream_events).
"""
import json
import requests
from app.kanoon.state import KanoonState
from app.kanoon.prompts import (
    EXPERT_SYSTEM, LANG_INSTRUCTION,
    TIMELINE_FORMAT, CRIME_GUIDANCE
)
from app.config import settings


def clean_response_for_user(response: str) -> str:
    """
    Remove internal block headers before streaming to user.
    Catches all variants: with ━━━, without ━━━, with/without spaces.
    """
    import re
    # Remove ━━━ ... ━━━ lines (standard format)
    response = re.sub(r'━+[^━\n]*━+\n?', '', response)
    # Remove BLOCK N: LABEL lines without ━━━ (model sometimes omits separators)
    response = re.sub(
        r'^(?:━*\s*)?BLOCK\s+\d+[:\s][^\n]*\n?',
        '', response, flags=re.MULTILINE | re.IGNORECASE
    )
    # Remove ब्लॉक N: Hindi headers
    response = re.sub(
        r'^(?:━*\s*)?ब्लॉक\s*[१२३४५\d]+[:\s][^\n]*\n?',
        '', response, flags=re.MULTILINE
    )
    # Remove leading bullet/asterisk
    response = re.sub(r'^\*\s+', '', response, flags=re.MULTILINE)
    # Collapse 3+ blank lines
    response = re.sub(r'\n{3,}', '\n\n', response)
    return response.strip()


def prune_history(history: list, max_turns: int = 4) -> tuple[list, str]:
    """
    Keep last max_turns verbatim.
    Summarize older turns into one line.
    Returns (pruned_history, summary_line)
    """
    if len(history) <= max_turns * 2:
        return history, ""

    # Split into old and recent
    cutoff = len(history) - (max_turns * 2)
    old_turns = history[:cutoff]
    recent_turns = history[cutoff:]

    # Build summary from old turns
    user_msgs = [m["content"][:80] for m in old_turns if m.get("role") == "user"]
    summary = f"[Earlier conversation summary: User mentioned — {' | '.join(user_msgs[:3])}]"

    return recent_turns, summary


def build_expert_prompt(state: KanoonState) -> tuple[str, int]:
    """Build the expert system prompt from frozen template."""
    lang = state.get("language", "hi")
    lang_instr = LANG_INSTRUCTION.get(lang, LANG_INSTRUCTION["en"])
    crime_type = state.get("crime_type", "other")
    lang_name = {"hi": "Devanagari Hindi", "en": "English", "bn": "Bengali"}.get(lang, "English")

    # Detect follow-up mode
    is_followup = state.get("phase") == "follow_up"

    if is_followup:
        # Short focused prompt for follow-up questions
        last_user = state.get("user_message_raw", "")
        for m in reversed(state.get("history", [])):
            if m.get("role") == "user":
                last_user = m.get("content", "")
                break

        system = f"""{lang_instr}

You are Kanoon Sakhi — answering a follow-up question from a woman who already received legal advice.

CASE FILE: {json.dumps({k: state.get(k) for k in ['crime_type','urgency','relationship_to_accused','living_situation','type_of_violence','has_children'] if state.get(k)}, ensure_ascii=False)}
HER QUESTION: {last_user}

Answer ONLY her specific question in 2-4 sentences in {lang_name}.
Do NOT repeat the full legal advice she already received.
If she confirms she has evidence → tell her exactly what to do with it (which officer, what to bring).
If she asks about free lawyer → give NALSA 15100 + 2 steps.
Keep response under 80 words.

{lang_instr}"""
        return system, 200

    # Full expert prompt
    case_fields = [
        "crime_type", "urgency", "relationship_to_accused", "state_india",
        "has_children", "marriage_date", "other_context",
        "living_situation", "house_ownership", "type_of_violence",
        "financial_dependence", "previous_complaints", "medical_evidence",
        "dowry_demand", "witnesses",
        "property_type", "father_alive", "religion", "will_exists",
        "who_blocking", "already_sold",
        "marital_status_current", "husband_income", "your_income",
        "husband_paying_anything", "how_long_separated", "reason_for_separation",
        "company_size", "accused_designation", "incident_type",
        "icc_exists", "evidence_available", "retaliation_happened",
        "grounds", "husband_consent", "maintenance_needed",
        "stalking_medium", "accused_known", "content_type", "screenshots_saved",
        "demand_type", "who_demanding", "violence_with_demand", "stridhan_returned",
        "children_ages", "current_custody", "divorce_status",
    ]
    case_file = {f: state.get(f) for f in case_fields if state.get(f) is not None}

    # Prune history to avoid context overflow
    history = state.get("history", [])
    pruned_history, old_summary = prune_history(history, max_turns=4)

    history_text = ""
    if old_summary:
        history_text = old_summary + "\n\n"
    history_text += "\n".join([
        f"{'User' if m['role']=='user' else 'Sakhi'}: {m['content'][:300]}"
        for m in pruned_history[-6:] if m.get("content")
    ])

    system = EXPERT_SYSTEM.format(
        lang_instruction=lang_instr,
        case_file=json.dumps(case_file, ensure_ascii=False, indent=2),
        crime_guidance=CRIME_GUIDANCE.get(crime_type, CRIME_GUIDANCE["other"]),
        rag_context=state.get("rag_context", "No specific legal context retrieved."),
        history=history_text,
        timeline=TIMELINE_FORMAT.get(lang, TIMELINE_FORMAT["en"]),
        lang_name=lang_name,
    )

    return system, 900


async def expert_node(state: KanoonState) -> dict:
    """
    Non-streaming expert call.
    Graph streams via astream_events — this node just returns the full response.
    """
    import logging
    log = logging.getLogger("strisakhi")
    phase = state.get("phase", "unknown")
    log.info(f"Expert node called — phase={phase}, crime={state.get('crime_type')}")

    system, max_tokens = build_expert_prompt(state)
    history = state.get("history", [])

    last_user = state.get("user_message_raw", "")
    for m in reversed(history):
        if m.get("role") == "user":
            last_user = m.get("content", "")
            break

    full_response = ""
    try:
        r = requests.post(
            f"{settings.ollama_base_url}/v1/chat/completions",
            json={
                "model": "gemma4",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": last_user},
                ],
                "stream": True,
                "temperature": 0.2,
                "max_tokens": max_tokens,
                "top_p": 0.95,
                "chat_template_kwargs": {"enable_thinking": False},
            },
            stream=True,
            timeout=120,
        )
        import json as _json
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
                delta = _json.loads(data_str)["choices"][0]["delta"]
                token = delta.get("content", "") or ""
                if token:
                    full_response += token
            except Exception:
                continue

    except Exception as e:
        lang = state.get("language", "hi")
        fallback = {
            "hi": "माफ करें, फिर से कोशिश करें।",
            "en": "Sorry, please try again.",
            "bn": "দুঃখিত, আবার চেষ্টা করুন।",
        }
        full_response = fallback.get(lang, fallback["en"])

    # Clean headers for user display — keep raw for scoring
    cleaned = clean_response_for_user(full_response)

    return {
        "response": cleaned,           # clean version shown to user
        "response_raw": full_response, # raw version with headers for scoring
        "phase": "follow_up",
    }
