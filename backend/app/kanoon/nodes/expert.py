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
    Keeps content, strips ━━━ BLOCK X: LABEL ━━━ markers in all variants.
    """
    import re
    # Remove all ━━━ ... ━━━ lines (catches all block header variants)
    response = re.sub(r'━+[^━\n]*━+\n?', '', response)
    # Remove leading bullet/asterisk from lines
    response = re.sub(r'^\*\s+', '', response, flags=re.MULTILINE)
    # Collapse 3+ blank lines into 2
    response = re.sub(r'\n{3,}', '\n\n', response)
    return response.strip()


def build_expert_prompt(state: KanoonState) -> tuple[str, int]:
    """Build the expert system prompt from frozen template."""
    lang = state.get("language", "hi")
    lang_instr = LANG_INSTRUCTION.get(lang, LANG_INSTRUCTION["en"])
    crime_type = state.get("crime_type", "other")

    # Build rich case file from all collected fields
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

    history = state.get("history", [])
    history_text = "\n".join([
        f"{'User' if m['role']=='user' else 'Sakhi'}: {m['content']}"
        for m in history[-8:] if m.get("content")
    ])

    system = EXPERT_SYSTEM.format(
        lang_instruction=lang_instr,
        case_file=json.dumps(case_file, ensure_ascii=False, indent=2),
        crime_guidance=CRIME_GUIDANCE.get(crime_type, CRIME_GUIDANCE["other"]),
        rag_context=state.get("rag_context", "No specific legal context retrieved."),
        history=history_text,
        timeline=TIMELINE_FORMAT.get(lang, TIMELINE_FORMAT["en"]),
        lang_name={"hi": "Devanagari Hindi", "en": "English", "bn": "Bengali"}.get(lang, "English"),
    )

    # Follow-up mode: short answer
    last_user = ""
    for m in reversed(history):
        if m.get("role") == "user":
            last_user = m.get("content", "")
            break

    is_followup = state.get("phase") == "follow_up"
    max_tokens = 250 if is_followup else 900

    return system, max_tokens


async def expert_node(state: KanoonState) -> dict:
    """
    Non-streaming expert call.
    Graph streams via astream_events — this node just returns the full response.
    """
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
