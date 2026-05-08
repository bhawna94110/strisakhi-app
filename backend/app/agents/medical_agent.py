"""
Medical Expert Agent — language-aware
"""
import requests
import json
from app.config import settings
from app.rag.medical_rag import get_medical_context
from typing import AsyncGenerator

LANGUAGE_INSTRUCTIONS = {
    "hi": "Respond ONLY in Hindi using Devanagari script. Never use Roman/English script for Hindi words.",
    "en": "Respond ONLY in English.",
    "bn": "Respond ONLY in Bengali using Bengali script.",
}

FOLLOWUP_WORDS = ["han","haan","yes","okay","ok","kaise","aur","batao","explain","next"]


async def run_medical_expert_stream(
    case_file: dict,
    conversation_history: list,
    language: str = "hi"
) -> AsyncGenerator[dict, None]:

    rag_context, citations = get_medical_context(case_file)
    yield {"type": "rag_retrieved", "citations": citations, "chunk_count": len(citations)}

    lang_instruction = LANGUAGE_INSTRUCTIONS.get(language, "Respond in the user's language.")

    last_user_msg = ""
    for msg in reversed(conversation_history):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    is_followup = (
        any(w in last_user_msg.lower() for w in FOLLOWUP_WORDS)
        and len(last_user_msg.strip()) < 40
    )

    history_text = "\n".join([
        f"{'User' if m['role']=='user' else 'Sakhi'}: {m['content']}"
        for m in conversation_history[-6:]
        if m.get("content")
    ])

    if is_followup:
        system = f"""You are Sehat Sakhi from StriSakhi, a health assistant for Indian women.
{lang_instruction}
Answer ONLY the follow-up question in 2-4 sentences.

CONVERSATION: {history_text}
CASE: {json.dumps(case_file, ensure_ascii=False)}"""
        max_tokens = 200
    else:
        system = f"""You are Sehat Sakhi from StriSakhi, a compassionate medical assistant for Indian women.
{lang_instruction}
Cite source: [Source: Guideline Name]

Structure:
1) One empathy sentence
2) What symptoms suggest
3) Action today
4) When to go to hospital
5) Free government scheme if relevant

End with: free doctor offer (in {language} language)
NEVER prescribe specific medicines.

MEDICAL GUIDELINES: {rag_context}
CASE: {json.dumps(case_file, ensure_ascii=False)}
CONVERSATION: {history_text}"""
        max_tokens = 600

    payload = {
        "model": "gemma4",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": last_user_msg}
        ],
        "stream": True,
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "top_p": 0.95,
    }

    full_response = ""
    try:
        r = requests.post(
            f"{settings.ollama_base_url}/v1/chat/completions",
            json=payload, stream=True, timeout=120
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
                    yield {"type": "token", "token": token, "agent": "expert"}
            except: continue
    except Exception as e:
        yield {"type": "error", "message": str(e)}
        return

    if not full_response.strip():
        full_response = {"hi": "माफ़ करें, दोबारा कोशिश करें।", "en": "Sorry, please try again."}.get(language, "Please try again.")
        yield {"type": "token", "token": full_response, "agent": "expert"}

    yield {"type": "done", "full_response": full_response, "citations": citations, "agent": "expert"}
