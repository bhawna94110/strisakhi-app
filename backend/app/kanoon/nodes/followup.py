"""
Follow-up Questions Node
Generates 5 contextual chips after expert response.
Separate quick LLM call — non-blocking relative to expert streaming.
"""
import json
import re
import httpx
from app.kanoon.state import KanoonState
from app.kanoon.prompts import LANG_INSTRUCTION, FOLLOWUP_PROMPT
from app.config import settings

LANG_NAMES = {"hi": "Devanagari Hindi", "en": "English", "bn": "Bengali"}

FALLBACK_QUESTIONS = {
    "domestic_violence": {
        "hi": [
            "Protection order कैसे मिलेगा?",
            "FIR कैसे दर्ज करें?",
            "मुफ्त वकील कहाँ मिलेगा?",
            "घर में रहने का अधिकार क्या है?",
            "बच्चों की custody के बारे में बताएं",
        ],
        "en": [
            "How do I get a protection order?",
            "How do I file an FIR?",
            "Where can I get a free lawyer?",
            "What are my rights to stay in the home?",
            "What about child custody?",
        ],
    },
    "property": {
        "hi": [
            "Partition suit कैसे file करें?",
            "मुफ्त वकील कहाँ मिलेगा?",
            "Vineeta Sharma case क्या है?",
            "कौन से documents चाहिए?",
            "कितने समय में decision होगा?",
        ],
        "en": [
            "How do I file a partition suit?",
            "Where can I get a free lawyer?",
            "What documents do I need?",
            "What if my brother tries to sell the property?",
            "How long does the court process take?",
        ],
    },
    "maintenance": {
        "hi": [
            "Application कैसे file करें?",
            "कितने पैसे मिल सकते हैं?",
            "60 दिन में क्या होगा?",
            "मुफ्त वकील कहाँ मिलेगा?",
            "अगर पति नहीं देता तो क्या करें?",
        ],
        "en": [
            "How do I file the application?",
            "How much maintenance can I get?",
            "What happens in 60 days?",
            "Where can I get a free lawyer?",
            "What if husband refuses to pay?",
        ],
    },
}

DEFAULT_FALLBACK = {
    "hi": [
        "मुफ्त वकील कैसे मिलेगा?",
        "NALSA से कैसे contact करें?",
        "क्या documents चाहिए?",
        "कितना समय लगेगा?",
        "पुलिस नहीं सुने तो क्या करें?",
    ],
    "en": [
        "Where can I get a free lawyer?",
        "How do I contact NALSA?",
        "What documents do I need?",
        "How long will this take?",
        "What if police don't help?",
    ],
}


async def followup_node(state: KanoonState) -> dict:
    """Generate 5 follow-up question chips."""
    lang = state.get("language", "hi")
    crime_type = state.get("crime_type", "other")
    lang_instr = LANG_INSTRUCTION.get(lang, LANG_INSTRUCTION["en"])

    case_summary = f"Crime: {crime_type}, State: {state.get('state_india', 'unknown')}"
    if state.get("other_context"):
        case_summary += f", Context: {state['other_context']}"

    prompt = FOLLOWUP_PROMPT.format(
        lang_instruction=lang_instr,
        crime_type=crime_type,
        language=lang,
        case_summary=case_summary,
        lang_name=LANG_NAMES.get(lang, "English"),
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                f"{settings.ollama_base_url}/v1/chat/completions",
                json={
                    "model": "gemma4",
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "temperature": 0.4,
                    "max_tokens": 200,
                    "chat_template_kwargs": {"enable_thinking": False},
                }
            )
        text = r.json()["choices"][0]["message"]["content"].strip()
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        if match:
            questions = json.loads(match.group())[:5]
            if questions:
                return {"follow_up_questions": questions}
    except Exception:
        pass

    # Fallback to hardcoded
    crime_fallbacks = FALLBACK_QUESTIONS.get(crime_type, {})
    lang_fallbacks = crime_fallbacks.get(lang, DEFAULT_FALLBACK.get(lang, DEFAULT_FALLBACK["en"]))
    return {"follow_up_questions": lang_fallbacks}
