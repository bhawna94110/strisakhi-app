"""
Legal Expert Agent — Gemma 4 E2B/E4B via llama.cpp
OpenAI-compatible streaming. Fast responses with Metal GPU.
Handles both new queries and follow-up questions correctly.
"""
import requests
import json
from app.config import settings
from app.rag.legal_rag import get_legal_context
from typing import AsyncGenerator


async def run_legal_expert_stream(
    case_file: dict,
    conversation_history: list,
    language: str = "hi"
) -> AsyncGenerator[dict, None]:

    # Step 1: Get RAG context from ChromaDB
    rag_context, citations = get_legal_context(case_file)
    yield {"type": "rag_retrieved", "citations": citations, "chunk_count": len(citations)}

    # Step 2: Get last user message
    last_user_msg = ""
    for msg in reversed(conversation_history):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    # Step 3: Detect follow-up vs new query
    followup_words = ["han", "haan", "yes", "okay", "ok", "theek hai", "acha",
                      "kaise", "aur", "phir", "batao", "nahi samjha", "dobara",
                      "explain", "matlab", "next", "phir kya"]
    is_followup = (
        any(w in last_user_msg.lower() for w in followup_words) and
        len(last_user_msg.strip()) < 40
    )

    # Step 4: Build conversation history string
    history_text = ""
    for msg in conversation_history[-8:]:
        role = "User" if msg.get("role") == "user" else "Nyay Vani"
        content = msg.get("content", "").strip()
        if content:
            history_text += f"{role}: {content}\n"

    # Step 5: Different prompts for follow-up vs new query
    if is_followup:
        system_content = f"""You are Nyay Vani, a compassionate legal advocate for Indian women.
The user is responding to your previous message. Answer ONLY their specific follow-up.
Do NOT repeat the full legal advice. Be brief — 3-5 sentences max. "Respond in the SAME language the user is using. If user writes in Hindi, respond in Hindi. If Bengali, respond in Bengali. If English, respond in English."

.

Special cases:
- If user says "han/haan/yes" to your offer of a free lawyer:
  Tell them to call NALSA: 15100 (free, all Indian languages)
  Give exact 3 steps to reach a lawyer today
- If user asks about a specific law or term: explain briefly in simple Hindi
- If user asks "kya karoon": give ONE specific next action

CONVERSATION SO FAR:
{history_text}

CASE:
{json.dumps(case_file, ensure_ascii=False)}"""

    else:
        system_content = f"""You are Nyay Vani, a confident legal advocate for Indian women.
Respond in simple Hindi. Be warm, direct, and practical.
Cite specific laws: [Source: Act Name, Section X]

Structure EXACTLY:
1) One empathy sentence (acknowledge her pain)
2) Her 2-3 most important rights with law citations
3) What to do TODAY — 3 numbered steps
4) One free helpline with number

End ALWAYS with: "Kya aap ek free vakeel se baat karna chahti hain?"

RULES:
- Only use information from LEGAL CONTEXT below
- Never make up section numbers
- Under 300 words total
- Simple Hindi, not legal jargon

LEGAL CONTEXT:
{rag_context}

CASE:
{json.dumps(case_file, ensure_ascii=False)}

CONVERSATION HISTORY:
{history_text}"""

    # Step 6: Build payload
    payload = {
        "model": "gemma4",
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": last_user_msg}
        ],
        "stream": True,
        "temperature": 0.2,
        "max_tokens": 150 if is_followup else 600,
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
            if not line:
                continue
            line_str = line.decode() if isinstance(line, bytes) else line
            if not line_str.startswith("data: "):
                continue
            data_str = line_str[6:]
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
                token = chunk["choices"][0]["delta"].get("content", "") or ""
                if token:
                    full_response += token
                    yield {"type": "token", "token": token, "agent": "expert"}
            except:
                continue

    except Exception as e:
        yield {"type": "error", "message": str(e)}
        return

    if not full_response.strip():
        full_response = "Maafi chahti hoon, abhi dobara try karein."
        yield {"type": "token", "token": full_response, "agent": "expert"}

    yield {
        "type": "done",
        "full_response": full_response,
        "citations": citations,
        "agent": "expert"
    }