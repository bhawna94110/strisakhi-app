"""
Medical Expert Agent — Gemma 4 E2B via llama.cpp
OpenAI-compatible streaming. Fast responses with Metal GPU.
"""
import requests
import json
from app.config import settings
from app.rag.medical_rag import get_medical_context
from typing import AsyncGenerator


async def run_medical_expert_stream(
    case_file: dict,
    conversation_history: list,
    language: str = "hi"
) -> AsyncGenerator[dict, None]:

    rag_context, citations = get_medical_context(case_file)
    yield {"type": "rag_retrieved", "citations": citations, "chunk_count": len(citations)}

    system_content = f"""You are Nyay Vani, a compassionate medical assistant for Indian women.
Respond in simple Hindi. Be helpful and clear.
Cite source: [Source: Guideline Name]
Structure: 1) Empathy 2) Symptoms 3) Action today 4) Hospital if needed 5) Free schemes
End with: Kya aap ek free doctor se baat karna chahti hain?
NEVER prescribe medicines.

MEDICAL GUIDELINES:
{rag_context}

CASE: {json.dumps(case_file, ensure_ascii=False)}"""

    last_user_msg = ""
    for msg in reversed(conversation_history):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    payload = {
        "model": "gemma4",
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": last_user_msg}
        ],
        "stream": True,
        "temperature": 0.2,
        "max_tokens": 600,
        "top_p": 0.95,
    }

    full_response = ""

    try:
        r = requests.post(
            f"{settings.ollama_base_url}/v1/chat/completions",
            json=payload,
            stream=True,
            timeout=120
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
        full_response = "Maafi chahti hoon, dobara try karein."
        yield {"type": "token", "token": full_response, "agent": "expert"}

    yield {"type": "done", "full_response": full_response, "citations": citations, "agent": "expert"}