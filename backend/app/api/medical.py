"""
Sehat Sakhi — Simple Direct Medical API v2
Single LLM call, warm ASHA-worker style response.
No intake/expert pipeline.
"""
import json
import requests
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.database.connection import get_db
from app.session.session_manager import (
    get_session_with_history, save_message, get_conversation_history
)
from app.config import settings

router = APIRouter()
LOG = logging.getLogger("strisakhi")

LANG_INSTRUCTION = {
    "hi": "🔴 Sirf Devanagari Hindi mein jawab do. Roman script bilkul nahi.",
    "en": "🔴 Respond ONLY in English.",
    "bn": "🔴 Sudhu Bangla te uttor dao.",
}

SEHAT_PROMPT = """{lang_instruction}

You are Sehat Sakhi — a caring health companion for rural Indian women.
You speak like a trusted older sister who knows medicine and government schemes.
You give practical, warm, actionable advice.

HEALTH KNOWLEDGE:
{rag_context}

CONVERSATION SO FAR:
{history}

RULES:
- NEVER diagnose ("yeh ho sakta hai..." not "aapko X hai")
- NEVER prescribe specific medicine names
- Under 250 words
- If life-threatening symptoms → say hospital IMMEDIATELY as first line
- Always mention one FREE government resource (108, 104, JSY, Ayushman, iCall)
- Be warm and simple — like talking to a village ASHA worker who cares

RESPONSE FORMAT:
1 sentence of empathy.
2-3 sentences explaining what this likely means in simple words.
2-3 practical steps to take today at home.
One free government helpline or scheme relevant to her situation.
End with: offer to explain more.

{lang_instruction}"""

FALLBACK_RAG = """
Pregnancy danger signs: heavy bleeding, fits, severe headache+blurred vision, no fetal movement 12hrs → hospital immediately.
Child danger signs: cannot drink, vomits everything, fits, unconscious, rapid breathing → hospital immediately.
Diarrhoea: give ORS after every loose stool, continue breastfeeding, zinc tablets free at PHC.
Fever in child: sponge with lukewarm water, paracetamol syrup by weight, watch danger signs.
Anaemia: fatigue, pale skin, dizziness → eat palak/dal/gud/til with lemon, free iron tablets at Anganwadi.
Depression after delivery: normal, treatable, call iCall 9152987821 free counselling.
Government help: 108 ambulance free, 102 maternity transport free, 104 health helpline free, Ayushman Bharat free hospital up to 5 lakh.
"""

def get_medical_rag(message: str) -> str:
    try:
        import chromadb
        from chromadb.utils import embedding_functions
        client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        ef = embedding_functions.DefaultEmbeddingFunction()
        col = client.get_collection("medical_documents", embedding_function=ef)
        results = col.query(query_texts=[message], n_results=3)
        docs = results["documents"][0]
        return "\n---\n".join(d[:500] for d in docs if d.strip())
    except Exception as e:
        LOG.warning(f"Medical RAG failed: {e}")
        return FALLBACK_RAG


class ChatRequest(BaseModel):
    session_id: str
    message: str
    input_type: Optional[str] = "text"
    language: Optional[str] = "hi"


@router.post("/chat")
async def medical_chat(req: ChatRequest, db: Session = Depends(get_db)):
    session_data = get_session_with_history(db, req.session_id)
    if not session_data:
        raise HTTPException(404, f"Session {req.session_id} not found")

    language = req.language or "hi"
    lang_instr = LANG_INSTRUCTION.get(language, LANG_INSTRUCTION["en"])

    save_message(db, req.session_id, "user", req.message, req.input_type, agent_used="sehat")

    history = get_conversation_history(db, req.session_id)
    history_text = "\n".join([
        f"{'User' if m['role']=='user' else 'Sehat Sakhi'}: {m['content'][:200]}"
        for m in history[-6:] if m.get("content")
    ])

    rag_context = get_medical_rag(req.message)
    system = SEHAT_PROMPT.format(
        lang_instruction=lang_instr,
        rag_context=rag_context,
        history=history_text,
    )

    return StreamingResponse(
        _stream(db, req.session_id, req.message, system, language),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream(db, session_id, user_message, system, language):
    full_response = ""
    try:
        r = requests.post(
            f"{settings.ollama_base_url}/v1/chat/completions",
            json={
                "model": "gemma4",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
                "stream": True,
                "temperature": 0.3,
                "max_tokens": 500,
                "chat_template_kwargs": {"enable_thinking": False},
            },
            stream=True, timeout=120,
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
                    yield f"data: {json.dumps({'type': 'token', 'token': token, 'agent': 'sehat'})}\n\n"
            except Exception:
                continue
    except Exception as e:
        msg = {"hi": "माफ करें, दोबारा कोशिश करें। Emergency: 108", "en": "Sorry, try again. Emergency: 108"}.get(language, "Sorry, try again.")
        full_response = msg
        yield f"data: {json.dumps({'type': 'token', 'token': msg, 'agent': 'sehat'})}\n\n"

    save_message(db, session_id, "assistant", full_response, agent_used="sehat")

    followups = {
        "hi": ["और बताइए", "अस्पताल कब जाना चाहिए?", "घर पर क्या करें?", "मुफ्त सरकारी मदद?", "बच्चे के लिए क्या करें?"],
        "en": ["Tell me more", "When to go to hospital?", "Home remedies?", "Free government help?", "Is this serious?"],
        "bn": ["আরও বলুন", "কখন হাসপাতাল?", "বাড়িতে কী করব?"],
    }
    yield f"data: {json.dumps({'type': 'done', 'full_response': full_response, 'agent': 'sehat', 'follow_up_questions': followups.get(language, followups['en'])})}\n\n"


@router.get("/test")
async def medical_test():
    return {"status": "Sehat Sakhi v2 ready"}
