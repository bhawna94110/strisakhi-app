"""
Medical Expert Agent — Uses Gemma 4 E2B
Uses requests library with /api/generate exactly like working Streamlit script.
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

    # Get RAG context
    rag_context, citations = get_medical_context(case_file)
    yield {"type": "rag_retrieved", "citations": citations, "chunk_count": len(citations)}

    # Get last user message
    last_user_msg = ""
    for msg in reversed(conversation_history):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    system_prompt = f"""You are Nyay Vani, a compassionate medical information assistant for Indian women.
Use the following official MEDICAL GUIDELINES to help the user.
Respond clearly and simply in Hindi. Give actionable steps.
Always cite source: [Source: Guideline Name]
If danger signs present, strongly recommend hospital immediately.
NEVER prescribe specific medicines.
End with: "Kya aap ek free doctor se baat karna chahti hain?"

MEDICAL GUIDELINES:
{rag_context}

Patient case: {json.dumps(case_file, ensure_ascii=False)}"""

    full_prompt = f"{system_prompt}\nUser: {last_user_msg}\nNyay Vani Medical Expert:"

    payload = {
        "model": settings.expert_model,
        "prompt": full_prompt,
        "stream": False
    }

    try:
        response = requests.post(
            f"{settings.ollama_base_url}/api/generate",
            json=payload,
            timeout=240
        )
        full_response = response.json().get("response", "") or ""
    except Exception as e:
        yield {"type": "error", "message": str(e)}
        return

    if not full_response.strip():
        full_response = "Maafi chahti hoon, abhi response mein dikkat aa rahi hai. Kripya dobara try karein."

    # Stream word by word
    for word in full_response.split(" "):
        yield {"type": "token", "token": word + " ", "agent": "expert"}

    yield {
        "type": "done",
        "full_response": full_response,
        "citations": citations,
        "agent": "expert"
    }