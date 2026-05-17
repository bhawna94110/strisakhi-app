"""
Yojana Sakhi — Simple Direct Scheme API v2
Single LLM call. No intake/expert pipeline. No routing.
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

SCHEMES = """
PM AWAS YOJANA (Free/Subsidised House):
Benefit: Rs 1.2-1.3 lakh for construction. Eligibility: BPL family, homeless or kutcha house.
Apply TODAY: Go to Gram Panchayat with Aadhaar + BPL card + land proof.

AYUSHMAN BHARAT (Free Health Insurance up to Rs 5 lakh/year):
Check eligibility: pmjay.gov.in or call 14555. Eligibility: BPL families.
Apply: Show Aadhaar at any empanelled hospital OR get Ayushman card at CSC.

JANANI SURAKSHA YOJANA (Cash for Hospital Delivery):
Benefit: Rs 1400 (rural) / Rs 1000 (urban) for delivery at govt hospital.
Apply: Tell ASHA worker or PHC before delivery. Documents: Aadhaar + BPL card.

PM MATRU VANDANA YOJANA (Rs 5000 for First Pregnancy):
Eligibility: First pregnancy, age 19+. Apply: Anganwadi centre.
Documents: Aadhaar + MCP card + bank account.

PM JAN DHAN (Free Zero-Balance Bank Account + Insurance):
Apply: Any bank with Aadhaar + 1 photo. Gets Rs 2 lakh accident insurance free.
IMPORTANT: Get Jan Dhan account FIRST — needed for all other scheme benefits.

UJJWALA YOJANA (Free LPG Gas Connection):
Eligibility: BPL women. Apply: Nearest LPG distributor (HP/Indane/Bharat Gas).
Documents: Aadhaar + ration card.

MGNREGS (100 Days Paid Work, Rs 200-300/day):
Apply: Gram Panchayat for Job Card. Women get 33% reservation.

PM KAUSHAL VIKAS (Free Skill Training + Job Help):
Any Indian age 15-45, no education needed. Apply: pmkvyofficial.org or nearest CSC.

MUDRA LOAN (Business Loan No Collateral, up to Rs 10 lakh):
Apply: Any bank. Women get priority and lower interest.

ONE STOP CENTRE SAKHI (Emergency Shelter + Legal + Medical FREE):
For any woman in distress. Call 181. No documents needed in emergency.

SUKANYA SAMRIDDHI (Savings for Girl Child, ~7.6% tax-free):
Open at post office for girl under 10. Min Rs 250/year.

WIDOW PENSION (Rs 300/month for BPL widows age 40-79):
Apply: Gram Panchayat with death certificate + BPL card + Aadhaar.

NALSA FREE LEGAL AID: Call 15100 (Mon-Sat, Hindi) for free lawyer.
CSC (Common Service Centre): In every village, helps apply for all schemes digitally.
"""

YOJANA_PROMPT = """{lang_instruction}

You are Yojana Sakhi — a friendly guide who helps Indian women get government benefits they deserve.
You are like a helpful neighbor who knows every government scheme and exactly how to apply.

GOVERNMENT SCHEMES DATABASE:
{schemes}

CONVERSATION SO FAR:
{history}

TASK: Based on what the user said, tell her:
1. The 1-2 most relevant schemes for her specific situation
2. Exact eligibility in 1 sentence
3. WHERE to apply TODAY and WHAT documents to bring
4. Mention Jan Dhan account if she doesn't have a bank account
5. One action she can take RIGHT NOW

RULES:
- Under 200 words
- Be specific — give exact apply location (Gram Panchayat / Anganwadi / PHC / Bank / CSC)
- List exact documents needed
- NEVER say "you don't qualify" — find at least one scheme for everyone
- If she needs legal help: mention NALSA 15100 free
- End with: ask if she wants details on any specific scheme

{lang_instruction}"""


class ChatRequest(BaseModel):
    session_id: str
    message: str
    input_type: Optional[str] = "text"
    language: Optional[str] = "hi"


@router.post("/chat")
async def scheme_chat(req: ChatRequest, db: Session = Depends(get_db)):
    session_data = get_session_with_history(db, req.session_id)
    if not session_data:
        raise HTTPException(404, f"Session {req.session_id} not found")

    language = req.language or "hi"
    lang_instr = LANG_INSTRUCTION.get(language, LANG_INSTRUCTION["en"])

    save_message(db, req.session_id, "user", req.message, req.input_type, agent_used="yojana")

    history = get_conversation_history(db, req.session_id)
    history_text = "\n".join([
        f"{'User' if m['role']=='user' else 'Yojana Sakhi'}: {m['content'][:200]}"
        for m in history[-4:] if m.get("content")
    ])

    system = YOJANA_PROMPT.format(
        lang_instruction=lang_instr,
        schemes=SCHEMES,
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
                "temperature": 0.2,
                "max_tokens": 400,
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
                    yield f"data: {json.dumps({'type': 'token', 'token': token, 'agent': 'yojana'})}\n\n"
            except Exception:
                continue
    except Exception as e:
        msg = {"hi": "माफ करें, दोबारा कोशिश करें।", "en": "Sorry, try again."}.get(language, "Sorry.")
        full_response = msg
        yield f"data: {json.dumps({'type': 'token', 'token': msg, 'agent': 'yojana'})}\n\n"

    save_message(db, session_id, "assistant", full_response, agent_used="yojana")

    followups = {
        "hi": ["कौन से documents चाहिए?", "Aadhaar नहीं है तो?", "CSC कहाँ मिलेगा?", "और कोई योजना?", "पैसे कब मिलेंगे?"],
        "en": ["What documents needed?", "Where exactly to apply?", "How long does it take?", "Any other schemes?", "What if no Aadhaar?"],
        "bn": ["কাগজপত্র কী লাগবে?", "কোথায় আবেদন?", "আর কোনো প্রকল্প?"],
    }
    yield f"data: {json.dumps({'type': 'done', 'full_response': full_response, 'agent': 'yojana', 'follow_up_questions': followups.get(language, followups['en'])})}\n\n"


@router.get("/test")
async def scheme_test():
    return {"status": "Yojana Sakhi v2 ready"}
